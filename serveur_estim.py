"""
=======================================================
  SERVEUR ESTIM  —  WebSocket bridge ST → ReStim
=======================================================
Tourne en arrière-plan.
SillyTavern envoie les commandes via WS sur port 5001.
Le serveur les exécute sur ReStim en temps réel.

Prérequis :  pip install websockets
=======================================================
"""

import asyncio
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
try:
    from pattern_generator import generate_pattern
    GENERATOR_AVAILABLE = True
except ImportError:
    GENERATOR_AVAILABLE = False
    print("[WARN] pattern_generator.py non trouvé — mode JSON direct uniquement")
import json
import re
import sys

try:
    import websockets
    from websockets.server import serve
except ImportError:
    print("[ERREUR] pip install websockets")
    sys.exit(1)

# ── Config ───────────────────────────────────────────
RESTIM_WS_URL  = "ws://localhost:12346/tcode"
LISTEN_PORT    = 5001          # ST se connecte ici

# Calibration volume
# L'IA parle en 0-100 mais la plage utile reelle est differente.
# VOL_MIN : volume minimum envoye (en dessous = rien ressenti)
# VOL_MAX : volume maximum safe (ne jamais depasser)
# ReStim a 100% -> VOL_MIN=30, VOL_MAX=60
# ReStim a 50%  -> VOL_MIN=30, VOL_MAX=85
VOL_MIN = 15   # en dessous = rien ressenti
VOL_MAX = 90   # à 100% ReStim / 5V

def remap_volume(vol_ia: float) -> float:
    """Remappe le volume IA (0-100) vers la plage utile reelle."""
    vol_ia = max(0, min(100, float(vol_ia)))
    if vol_ia == 0:
        return 0  # silence total toujours respecte
    return VOL_MIN + (vol_ia / 100.0) * (VOL_MAX - VOL_MIN)

# ── Couleurs ─────────────────────────────────────────
GREEN  = "\033[92m"
RED    = "\033[91m"
YELLOW = "\033[93m"
CYAN   = "\033[96m"
MAGENTA= "\033[95m"
RESET  = "\033[0m"
BOLD   = "\033[1m"

def log(msg, color=RESET):
    print(f"{color}{msg}{RESET}", flush=True)

# ════════════════════════════════════════════════════
#  T-Code builders
# ════════════════════════════════════════════════════
def pct_to_tcode(val_norm: float, min_v: float, max_v: float) -> int:
    ratio = (val_norm - min_v) / (max_v - min_v)
    return max(0, min(999, int(ratio * 999)))

def step_to_tcodes(step) -> str:
    if isinstance(step, (int, float)):
        step = {"volume": float(step), "alpha": 0.0, "beta": 0.0, "pulse_freq": 20, "pulse_width": 6, "carrier_freq": 900, "ms": 800}
    cmds = []
    dur = int(step.get("ms", 1000))

    # Volume V0
    vol_ia = max(0, min(100, float(step.get("v", step.get("volume", 0)))))
    vol = remap_volume(vol_ia)
    cmds.append(f"V0{int(vol/100*999):03d}I{dur}")

    # Alpha L0 / Beta L1
    alpha = max(-1.0, min(1.0, float(step.get("alpha", 0.0))))
    cmds.append(f"L0{pct_to_tcode(alpha, -1.0, 1.0):03d}I{dur}")
    beta = max(-1.0, min(1.0, float(step.get("beta", 0.0))))
    cmds.append(f"L1{pct_to_tcode(beta, -1.0, 1.0):03d}I{dur}")

    # Pulse frequency P0 (max 120Hz)
    pf = max(1, min(120, int(step.get("pf", step.get("pulse_freq", 20)))))
    cmds.append(f"P0{int(pf/120*999):03d}I{dur}")

    # Pulse width P1
    pw = max(3, min(15, int(step.get("pulse_width", 5))))
    cmds.append(f"P1{pct_to_tcode(pw, 3, 15):03d}I{dur}")

    # Carrier frequency C0 (etendu a 2000Hz)
    cf = max(500, min(2000, int(step.get("carrier_freq", 1000))))
    cmds.append(f"C0{pct_to_tcode(cf, 500, 2000):03d}I{dur}")

    # Intensites par electrode e1/e2/e3
    for t_axis, key in [("E0", "e1"), ("E1", "e2"), ("E2", "e3")]:
        if key in step and step[key] is not None:
            val = max(0.0, min(1.0, float(step[key])))
            cmds.append(f"{t_axis}{int(val*999):03d}I{dur}")

    # Vibration layer
    if "vib1_frequency" in step and step["vib1_frequency"] is not None:
        vf = max(0, min(100, int(step["vib1_frequency"])))
        cmds.append(f"V1{int(vf/100*999):03d}I{dur}")
    if "vib1_strength" in step and step["vib1_strength"] is not None:
        vs = max(0.0, min(1.0, float(step["vib1_strength"])))
        cmds.append(f"V2{int(vs*999):03d}I{dur}")

    return " ".join(cmds)

# ════════════════════════════════════════════════════
#  Pattern runner (boucle arrière-plan)
# ════════════════════════════════════════════════════
class PatternRunner:
    def __init__(self):
        self.restim_ws = None
        self._task: asyncio.Task | None = None
        self._stop_event = asyncio.Event()

    async def connect_restim(self):
        try:
            self.restim_ws = await websockets.connect(RESTIM_WS_URL, open_timeout=5)
            log(f"  {GREEN}✔  Connecté à ReStim{RESET}")
            await self.restim_ws.send("V0000I300")
            return True
        except Exception as e:
            log(f"  {RED}✗  ReStim inaccessible : {e}{RESET}")
            return False

    async def set_pattern(self, pattern: dict):
        await self._stop()
        self._stop_event.clear()
        self._task = asyncio.create_task(self._run(pattern))
        log(f"  {MAGENTA}⚡ Pattern : {BOLD}{pattern.get('note','')}{RESET}  "
            f"{YELLOW}({len(pattern['pattern'])} steps){RESET}")

    async def stop(self):
        await self._stop()
        if self.restim_ws:
            try:
                await self.restim_ws.send("V0000I300")
            except Exception:
                pass

    async def _stop(self):
        if self._task and not self._task.done():
            self._stop_event.set()
            try:
                await asyncio.wait_for(self._task, timeout=2.0)
            except (asyncio.TimeoutError, asyncio.CancelledError):
                self._task.cancel()

    async def _run(self, pattern: dict):
        steps  = pattern["pattern"]
        repeat = pattern.get("repeat", True)
        try:
            while not self._stop_event.is_set():
                for step in steps:
                    if self._stop_event.is_set():
                        break
                    tcode = step_to_tcodes(step)
                    try:
                        await self.restim_ws.send(tcode)
                    except Exception:
                        return
                    dur_ms = int(step.get("ms", 1000))
                    elapsed = 0
                    while elapsed < dur_ms and not self._stop_event.is_set():
                        await asyncio.sleep(0.05)
                        elapsed += 50
                if not repeat:
                    break
        except asyncio.CancelledError:
            pass

# ════════════════════════════════════════════════════
#  Handler WebSocket — reçoit les commandes de ST
# ════════════════════════════════════════════════════
runner = PatternRunner()

async def handle_st_client(websocket):
    client = websocket.remote_address
    log(f"  {CYAN}→  ST connecté depuis {client}{RESET}")
    try:
        async for message in websocket:
            try:
                data = json.loads(message)
                action = data.get("action", "pattern")

                if action == "stop":
                    await runner.stop()
                    log(f"  {YELLOW}→  Stop reçu{RESET}")
                    await websocket.send(json.dumps({"status": "stopped"}))

                elif action == "pattern":
                    pattern = data.get("pattern")
                    if pattern and "pattern" in pattern:
                        await runner.set_pattern(pattern)
                        await websocket.send(json.dumps({"status": "ok"}))
                    else:
                        log(f"  {RED}✗  Pattern invalide reçu{RESET}")
                        await websocket.send(json.dumps({"status": "error", "msg": "invalid pattern"}))

                elif action == "generate":
                    if GENERATOR_AVAILABLE:
                        pattern = generate_pattern(
                            pattern_type = data.get("type", "caresse"),
                            intensity    = data.get("intensity", 50),
                            speed        = data.get("speed", "medium"),
                            mood         = data.get("mood", "tease"),
                            count        = data.get("count", 8),
                            shape        = data.get("shape", "wave"),
                            focus        = data.get("focus", "rotate"),
                        )
                        await runner.set_pattern(pattern)
                        log(f"  {MAGENTA}⚡ Généré : {BOLD}{pattern['note']}{RESET}")
                        await websocket.send(json.dumps({"status": "ok", "note": pattern["note"]}))
                    else:
                        await websocket.send(json.dumps({"status": "error", "msg": "generator not available"}))

                elif action == "ping":
                    await websocket.send(json.dumps({"status": "pong"}))

            except json.JSONDecodeError:
                log(f"  {RED}✗  JSON invalide : {message[:100]}{RESET}")

    except websockets.exceptions.ConnectionClosed:
        log(f"  {YELLOW}→  ST déconnecté{RESET}")

# ════════════════════════════════════════════════════
#  MAIN
# ════════════════════════════════════════════════════
async def main():
    print(f"\n{BOLD}{'═'*52}")
    print(f"   SERVEUR ESTIM  —  ST → ReStim → NeoDK")
    print(f"{'═'*52}{RESET}")

    ok = await runner.connect_restim()
    if not ok:
        print(f"  {RED}Lance ReStim d'abord puis relance ce script.{RESET}\n")
        return

    print(f"  {GREEN}✔  Serveur WebSocket démarré sur ws://localhost:{LISTEN_PORT}{RESET}")
    print(f"  {YELLOW}En attente de SillyTavern...{RESET}")
    print(f"  {YELLOW}Ctrl+C pour arrêter{RESET}\n")

    async with serve(handle_st_client, "localhost", LISTEN_PORT):
        try:
            await asyncio.Future()  # tourne indéfiniment
        except asyncio.CancelledError:
            pass

    await runner.stop()
    print(f"\n  {GREEN}✔  Serveur arrêté proprement.{RESET}\n")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print(f"\n  {YELLOW}→  Arrêt demandé.{RESET}\n")
