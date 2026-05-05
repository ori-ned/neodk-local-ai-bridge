"""
=======================================================
  GÉNÉRATEUR DE PATTERNS TRIPHASE v2.3
  - Ajout axes e1/e2/e3 (intensité par électrode)
  - Ajout vib1_strength/vib1_frequency (vibration layer)
  - Vrais cercles via déphasage 120° sur e1/e2/e3
  - pulse_freq max 120Hz
=======================================================
"""

import math
import random

ELECTRODES = {
    "A"      : ( 0.90,  0.00),
    "B"      : (-0.50,  0.80),
    "C"      : (-0.50, -0.80),
    "center" : ( 0.00,  0.00),
}

def to_vol(intensity: float, scale: float = 1.0) -> int:
    v = 15 + (max(0, min(100, intensity)) / 100.0) * 45 * scale
    return max(15, min(60, int(v)))

def to_norm(val: float) -> float:
    """Normalise 0.0-1.0"""
    return round(max(0.0, min(1.0, float(val))), 3)

SPEED_MS = {
    "slow"    : {"short": 800,  "medium": 1500, "long": 2500},
    "medium"  : {"short": 350,  "medium": 700,  "long": 1400},
    "fast"    : {"short": 180,  "medium": 350,  "long": 700},
    "frantic" : {"short": 150,  "medium": 220,  "long": 400},
}

MOOD = {
    "soft"     : {"pf_lo": 8,   "pf_hi": 25,   "cf_lo": 550,  "cf_hi": 900,  "pw": 5},
    "tease"    : {"pf_lo": 18,  "pf_hi": 55,   "cf_lo": 750,  "cf_hi": 1200, "pw": 7},
    "intense"  : {"pf_lo": 35,  "pf_hi": 85,   "cf_lo": 950,  "cf_hi": 1600, "pw": 9},
    "dominant" : {"pf_lo": 55,  "pf_hi": 120,  "cf_lo": 1100, "cf_hi": 2000, "pw": 11},
}

def mk(vol, alpha, beta, pf, pw, cf, ms,
       e1=None, e2=None, e3=None,
       vib_freq=None, vib_strength=None) -> dict:
    """Crée un step complet avec tous les axes disponibles"""
    s = {
        "volume"      : max(15, min(60, int(vol))),
        "alpha"       : round(max(-1.0, min(1.0, float(alpha))), 2),
        "beta"        : round(max(-1.0, min(1.0, float(beta))), 2),
        "pulse_freq"  : max(5, min(120, int(pf))),
        "pulse_width" : max(3, min(15, int(pw))),
        "carrier_freq": max(500, min(2000, int(cf))),
        "ms"          : max(150, min(3000, int(ms))),
    }
    # Intensités par électrode (0.0-1.0)
    if e1 is not None: s["e1"] = to_norm(e1)
    if e2 is not None: s["e2"] = to_norm(e2)
    if e3 is not None: s["e3"] = to_norm(e3)
    # Vibration layer
    if vib_freq     is not None: s["vib1_frequency"] = max(0, min(100, int(vib_freq)))
    if vib_strength is not None: s["vib1_strength"]  = to_norm(vib_strength)
    return s

# ════════════════════════════════════════════════════
#  CERCLE PARFAIT via déphasage 120° sur e1/e2/e3
# ════════════════════════════════════════════════════
def gen_circle(intensity, speed, mood, n, shape, ms_val):
    """
    Vrai cercle continu — chaque électrode suit une sinusoïde
    déphasée de 120° par rapport aux autres.
    Plus n est grand, plus le cercle est fluide.
    """
    md = MOOD[mood]
    steps = []
    vol = to_vol(intensity)
    pf  = md["pf_lo"] + (md["pf_hi"] - md["pf_lo"]) * 0.5
    cf  = md["cf_lo"] + (md["cf_hi"] - md["cf_lo"]) * 0.4

    for i in range(n):
        t = i / n  # 0 à 1 sur un cycle complet
        angle = 2 * math.pi * t

        # Déphasage 120° entre les 3 électrodes
        e1 = (math.sin(angle) + 1) / 2
        e2 = (math.sin(angle + 2 * math.pi / 3) + 1) / 2
        e3 = (math.sin(angle + 4 * math.pi / 3) + 1) / 2

        # alpha/beta suivent aussi le cercle pour coïncider
        alpha = 0.7 * math.cos(angle)
        beta  = 0.7 * math.sin(angle)

        steps.append(mk(vol, alpha, beta, pf, md["pw"], cf, ms_val,
                        e1=e1, e2=e2, e3=e3))
    return steps

def gen_circle_in(intensity, speed, mood, n, ms_val):
    """Cercle qui se rapproche du centre progressivement"""
    md = MOOD[mood]
    steps = []
    for i in range(n):
        t = i / n
        angle = 2 * math.pi * t
        radius = 0.8 - 0.6 * (i / (n-1))  # 0.8 → 0.2

        e1 = (math.sin(angle) + 1) / 2
        e2 = (math.sin(angle + 2 * math.pi / 3) + 1) / 2
        e3 = (math.sin(angle + 4 * math.pi / 3) + 1) / 2

        vol = to_vol(intensity * (0.4 + 0.6 * (i / (n-1))))
        pf  = md["pf_lo"] + (md["pf_hi"] - md["pf_lo"]) * (i / (n-1))
        cf  = md["cf_lo"] + (md["cf_hi"] - md["cf_lo"]) * (i / (n-1)) * 0.6

        alpha = radius * math.cos(angle)
        beta  = radius * math.sin(angle)

        steps.append(mk(vol, alpha, beta, pf, md["pw"], cf, ms_val,
                        e1=e1, e2=e2, e3=e3))
    return steps

# ════════════════════════════════════════════════════
#  HELPERS
# ════════════════════════════════════════════════════
def get_position(focus, step_idx, total, curve=0.5):
    t = step_idx / max(1, total - 1)
    radius = max(0.10, min(0.90, 0.85 - curve * 0.73))
    if focus in ELECTRODES:
        a, b = ELECTRODES[focus]
        return (a * radius + random.uniform(-0.04, 0.04),
                b * radius + random.uniform(-0.04, 0.04))
    elif focus == "rotate":
        a, b = ELECTRODES[["A","B","C"][step_idx % 3]]
        return (a * radius + random.uniform(-0.04, 0.04),
                b * radius + random.uniform(-0.04, 0.04))
    elif focus == "center":
        r = max(0.05, radius * 0.35)
        angle = 2 * math.pi * t * 0.5
        return (r * math.cos(angle), r * math.sin(angle))
    else:
        angle = 2 * math.pi * t + random.uniform(-0.2, 0.2)
        return (radius * math.cos(angle), radius * math.sin(angle))

def shape_curve(shape, t, i):
    if shape == "up"    : return t ** 0.8
    elif shape == "down": return (1 - t) ** 0.8
    elif shape == "wave": return 0.5 + 0.5 * math.sin(math.pi * t)
    elif shape == "pulse": return 0.85 if i % 2 == 0 else 0.25
    elif shape == "spike":
        return max(0.15, 1.0 - abs(t - 0.67) * 3)
    elif shape == "hold": return 0.7
    else: return 0.5 + 0.5 * math.sin(math.pi * t)

def shape_ms(shape, t, sp, ss):
    base = sp[ss]
    if shape == "up"    : return max(150, int(base * (1.2 - 0.4 * t)))
    elif shape == "down": return max(150, int(base * (0.8 + 0.4 * t)))
    elif shape == "wave": return max(150, int(base * (0.8 + 0.4 * abs(math.sin(math.pi * t)))))
    elif shape == "spike": return max(150, int(base * (0.5 + abs(t - 0.67))))
    else: return base

def apply_type(type_name, t, i, md):
    if type_name == "caresse":
        pf = md["pf_lo"] + (md["pf_hi"] - md["pf_lo"]) * 0.25
        cf = md["cf_lo"] + 100 * math.sin(math.pi * t)
        pw = md["pw"]
    elif type_name == "tease":
        pf = md["pf_lo"] + (md["pf_hi"] - md["pf_lo"]) * (0.4 + 0.6 * abs(math.sin(math.pi * t * 2.3)))
        cf = md["cf_lo"] + (md["cf_hi"] - md["cf_lo"]) * 0.4 * abs(math.cos(math.pi * t * 1.7))
        pw = md["pw"] + int(2 * abs(math.sin(math.pi * t * 3)))
    elif type_name == "vague":
        pf = md["pf_lo"] + (md["pf_hi"] - md["pf_lo"]) * t
        cf = md["cf_lo"] + (md["cf_hi"] - md["cf_lo"]) * t
        pw = md["pw"] + int(t * 4)
    elif type_name == "frisson":
        pf = md["pf_hi"] * (0.7 + 0.3 * math.sin(math.pi * i * 1.5))
        cf = md["cf_hi"] * (0.8 + 0.2 * math.cos(math.pi * i * 1.2))
        pw = md["pw"] + 2
    elif type_name == "rotation":
        pf = md["pf_lo"] + (md["pf_hi"] - md["pf_lo"]) * t
        cf = md["cf_lo"] + (md["cf_hi"] - md["cf_lo"]) * t * 0.7
        pw = md["pw"]
    elif type_name == "climax":
        pf = md["pf_lo"] + (md["pf_hi"] - md["pf_lo"]) * (t ** 1.5)
        cf = md["cf_lo"] + (md["cf_hi"] - md["cf_lo"]) * (t ** 1.3)
        pw = md["pw"] + int(t * 4)
    elif type_name == "decompression":
        pf = md["pf_hi"] - (md["pf_hi"] - md["pf_lo"]) * t
        cf = md["cf_hi"] - (md["cf_hi"] - md["cf_lo"]) * t
        pw = md["pw"] + int((1 - t) * 3)
    elif type_name == "onde":
        pf = md["pf_lo"] + (md["pf_hi"] - md["pf_lo"]) * (0.5 + 0.5 * math.sin(2 * math.pi * t))
        cf = md["cf_lo"] + 200 * math.sin(math.pi * t)
        pw = md["pw"]
    elif type_name == "pulsation":
        pf = md["pf_hi"] * 0.8 if i % 2 == 0 else md["pf_lo"] * 1.2
        cf = md["cf_lo"] + 200 if i % 2 == 0 else md["cf_lo"]
        pw = md["pw"]
    elif type_name == "tremblement":
        pf = md["pf_lo"] + (md["pf_hi"] - md["pf_lo"]) * 0.5 + random.uniform(-5, 5)
        cf = md["cf_lo"] + 150 + random.uniform(-50, 50)
        pw = md["pw"]
    elif type_name == "respiration":
        breath = math.sin(math.pi * t)
        pf = md["pf_lo"] + (md["pf_hi"] - md["pf_lo"]) * breath * 0.5
        cf = md["cf_lo"] + 300 * breath
        pw = md["pw"]
    elif type_name == "spirale":
        pf = md["pf_lo"] + (md["pf_hi"] - md["pf_lo"]) * t * 0.8
        cf = md["cf_lo"] + (md["cf_hi"] - md["cf_lo"]) * t * 0.7
        pw = md["pw"] + int(t * 3)
    elif type_name == "chaos":
        pf = random.uniform(md["pf_lo"], md["pf_hi"])
        cf = random.uniform(md["cf_lo"], md["cf_hi"])
        pw = random.randint(md["pw"] - 1, md["pw"] + 3)
    elif type_name == "spike":
        is_peak = abs(t - 0.67) < 0.15
        pf = md["pf_hi"] if is_peak else md["pf_lo"]
        cf = md["cf_hi"] if is_peak else md["cf_lo"]
        pw = md["pw"] + 3 if is_peak else md["pw"]
    elif type_name == "buzz":
        buzz = 0.5 + 0.5 * math.sin(2 * math.pi * t * 4)
        pf = md["pf_lo"] * 0.8 + (md["pf_hi"] - md["pf_lo"]) * buzz
        cf = md["cf_lo"] + (md["cf_hi"] - md["cf_lo"]) * 0.6
        pw = md["pw"] + 1
    elif type_name == "edge":
        pf = md["pf_hi"] * (0.85 + 0.15 * math.sin(math.pi * t * 3))
        cf = md["cf_hi"] * (0.80 + 0.15 * math.cos(math.pi * t * 2))
        pw = md["pw"] + 3
    elif type_name == "stay":
        pf = md["pf_lo"] * (1.2 + 0.3 * math.sin(math.pi * t * 1.5))
        cf = md["cf_lo"] + 100
        pw = md["pw"]
    elif type_name == "cum":
        if t < 0.7:
            pf = md["pf_lo"] + (md["pf_hi"] - md["pf_lo"]) * (t / 0.7) ** 1.5
            cf = md["cf_lo"] + (md["cf_hi"] - md["cf_lo"]) * (t / 0.7)
            pw = md["pw"] + int((t / 0.7) * 5)
        else:
            decay = (t - 0.7) / 0.3
            pf = md["pf_hi"] * (1 - decay * 0.4)
            cf = md["cf_hi"] * (1 - decay * 0.3)
            pw = md["pw"] + int((1 - decay) * 4)
    elif type_name == "slow_stroke":
        pf = md["pf_lo"] + (md["pf_hi"] - md["pf_lo"]) * 0.3
        cf = md["cf_lo"] + (md["cf_hi"] - md["cf_lo"]) * 0.3
        pw = md["pw"] + 1
    elif type_name == "fast_stroke":
        pf = md["pf_lo"] + (md["pf_hi"] - md["pf_lo"]) * 0.7
        cf = md["cf_lo"] + (md["cf_hi"] - md["cf_lo"]) * 0.6
        pw = md["pw"] + 2
    else:
        pf = md["pf_lo"] + (md["pf_hi"] - md["pf_lo"]) * 0.5
        cf = md["cf_lo"] + (md["cf_hi"] - md["cf_lo"]) * 0.5
        pw = md["pw"]

    return (max(5, min(120, int(pf))),
            max(500, min(2000, int(cf))),
            max(3, min(15, int(pw))))

def resolve_count(count):
    if isinstance(count, int): return max(2, min(24, count))
    mapping = {"short": random.randint(2,4), "court": random.randint(2,4),
               "medium": random.randint(4,8), "moyen": random.randint(4,8),
               "long": random.randint(8,12), "extra": random.randint(12,16)}
    return mapping.get(str(count).lower(), 8)

def resolve_step_size(speed, count):
    if count <= 4  : return "short" if speed in ("fast","frantic") else "medium"
    elif count <= 8: return "medium"
    else           : return "long" if speed in ("slow","medium") else "medium"

# ════════════════════════════════════════════════════
#  GÉNÉRATION avec e1/e2/e3 selon le type
# ════════════════════════════════════════════════════
def compute_electrodes(type_name, t, i, n, curve):
    """
    Retourne (e1, e2, e3) selon le type de pattern.
    None = on n'envoie pas cet axe (ReStim garde sa valeur)
    """
    angle = 2 * math.pi * t

    if type_name == "circle":
        # Vrai cercle — déphasage 120°
        e1 = (math.sin(angle) + 1) / 2
        e2 = (math.sin(angle + 2*math.pi/3) + 1) / 2
        e3 = (math.sin(angle + 4*math.pi/3) + 1) / 2
        return e1, e2, e3

    elif type_name == "circle_in":
        # Cercle qui se resserre vers le centre
        intensity_scale = 0.3 + 0.7 * curve
        e1 = intensity_scale * (math.sin(angle) + 1) / 2
        e2 = intensity_scale * (math.sin(angle + 2*math.pi/3) + 1) / 2
        e3 = intensity_scale * (math.sin(angle + 4*math.pi/3) + 1) / 2
        return e1, e2, e3

    elif type_name == "rotation":
        # Rotation séquentielle A→B→C avec fondu
        phase = (i % 3) / 3 * 2 * math.pi
        e1 = max(0, math.cos(phase)) ** 2
        e2 = max(0, math.cos(phase + 2*math.pi/3)) ** 2
        e3 = max(0, math.cos(phase + 4*math.pi/3)) ** 2
        return e1, e2, e3

    elif type_name in ("fast_stroke", "slow_stroke"):
        # Balayage A→B→C
        idx = i % 3
        e1 = 0.9 if idx == 0 else 0.1
        e2 = 0.9 if idx == 1 else 0.1
        e3 = 0.9 if idx == 2 else 0.1
        return e1, e2, e3

    elif type_name == "frisson":
        # Sauts aléatoires entre électrodes
        vals = [random.uniform(0.1, 0.9),
                random.uniform(0.1, 0.9),
                random.uniform(0.1, 0.9)]
        return vals[0], vals[1], vals[2]

    elif type_name == "pulsation":
        # Alternance centre/bord
        if i % 2 == 0:
            return 0.8, 0.8, 0.8  # toutes allumées
        else:
            return 0.15, 0.15, 0.15  # toutes atténuées

    elif type_name == "edge":
        # Maintien élevé avec micro-variations
        base = 0.7 + 0.2 * curve
        e1 = base + 0.1 * math.sin(angle * 1.3)
        e2 = base + 0.1 * math.sin(angle * 1.3 + 2*math.pi/3)
        e3 = base + 0.1 * math.sin(angle * 1.3 + 4*math.pi/3)
        return to_norm(e1), to_norm(e2), to_norm(e3)

    elif type_name == "cum":
        # Montée simultanée toutes électrodes
        e_val = curve ** 1.5
        return to_norm(e_val), to_norm(e_val), to_norm(e_val)

    elif type_name == "vague":
        # Vague qui traverse A→B→C
        e1 = (math.sin(angle - math.pi/6) + 1) / 2 * curve
        e2 = (math.sin(angle - math.pi/6 + 2*math.pi/3) + 1) / 2 * curve
        e3 = (math.sin(angle - math.pi/6 + 4*math.pi/3) + 1) / 2 * curve
        return to_norm(e1), to_norm(e2), to_norm(e3)

    else:
        # Par défaut : pas d'e1/e2/e3 (ReStim gère)
        return None, None, None

# ════════════════════════════════════════════════════
#  GÉNÉRATEUR PRINCIPAL
# ════════════════════════════════════════════════════
def generate_pattern(
    pattern_type : str   = "caresse",
    intensity    : float = 50,
    speed        : str   = "medium",
    mood         : str   = "tease",
    count                = 8,
    shape        : str   = "wave",
    focus        : str   = "rotate",
) -> dict:

    pattern_type = str(pattern_type).lower().strip()
    speed   = str(speed).lower().strip()
    mood    = str(mood).lower().strip()
    shape   = str(shape).lower().strip()
    focus   = str(focus).lower().strip()
    intensity = max(1.0, min(100.0, float(intensity)))

    if speed not in SPEED_MS : speed = "medium"
    if mood  not in MOOD     : mood  = "tease"

    # Cas spéciaux circle
    if pattern_type in ("circle", "circle_in"):
        n = resolve_count(count)
        sp = SPEED_MS[speed]
        ss = resolve_step_size(speed, n)
        ms_val = sp[ss]
        if pattern_type == "circle":
            steps = gen_circle(intensity, speed, mood, n, shape, ms_val)
        else:
            steps = gen_circle_in(intensity, speed, mood, n, ms_val)
        return {
            "pattern"  : steps,
            "repeat"   : True,
            "note"     : f"{pattern_type}|i={int(intensity)}|{speed}|{mood}|{n}st",
            "generated": True,
        }

    n  = resolve_count(count)
    sp = SPEED_MS[speed]
    md = MOOD[mood]
    ss = resolve_step_size(speed, n)
    steps = []

    for i in range(n):
        t = i / max(1, n - 1)
        curve = shape_curve(shape, t, i)
        vol   = to_vol(intensity * (0.25 + 0.75 * curve))
        alpha, beta = get_position(focus, i, n, curve)
        pf, cf, pw  = apply_type(pattern_type, t, i, md)
        ms          = shape_ms(shape, t, sp, ss)
        e1, e2, e3  = compute_electrodes(pattern_type, t, i, n, curve)

        # Vibration layer pour buzz et edge
        vib_freq = vib_strength = None
        if pattern_type == "buzz":
            vib_freq     = 15 + int(curve * 35)
            vib_strength = to_norm(0.3 + 0.4 * curve)
        elif pattern_type == "edge":
            vib_freq     = 10
            vib_strength = to_norm(0.15 + 0.1 * curve)

        steps.append(mk(vol, alpha, beta, pf, pw, cf, ms,
                        e1=e1, e2=e2, e3=e3,
                        vib_freq=vib_freq, vib_strength=vib_strength))

    return {
        "pattern"  : steps,
        "repeat"   : True,
        "note"     : f"{pattern_type}|{shape}|i={int(intensity)}|{speed}|{mood}|{n}st",
        "generated": True,
    }

# ── Test ─────────────────────────────────────────────
if __name__ == "__main__":
    tests = [
        ("circle",      60, "medium", "tease",    12, "wave",  "rotate"),
        ("circle_in",   75, "fast",   "intense",  12, "up",    "rotate"),
        ("rotation",    55, "medium", "tease",     9, "wave",  "rotate"),
        ("vague",       65, "fast",   "dominant",  8, "up",    "rotate"),
        ("edge",        80, "medium", "dominant",  8, "hold",  "rotate"),
        ("frisson",     70, "fast",   "intense",   8, "spike", "free"),
        ("buzz",        60, "fast",   "intense",   6, "wave",  "center"),
        ("cum",         90, "frantic","dominant", 12, "up",    "free"),
    ]
    print("=== Test générateur v2.3 — axes e1/e2/e3 ===\n")
    for t in tests:
        p = generate_pattern(*t)
        s0 = p["pattern"][0]
        has_e = "e1" in s0
        has_v = "vib1_strength" in s0
        print(f"[{t[0]:12s}] {len(p['pattern']):2d}st "
              f"vol={s0['volume']:2d} pf={s0['pulse_freq']:3d} "
              f"e1/e2/e3={'✔' if has_e else '✗'} "
              f"vib={'✔' if has_v else '✗'} "
              f"| {p['note']}")
        if has_e:
            print(f"             e1={s0['e1']:.2f} e2={s0['e2']:.2f} e3={s0['e3']:.2f}")
    print("\n✔ Générateur v2.3 OK")
