-stm# NeoDK AI Bridge — LMStudio + SillyTavern + ReStim

> Control a NeoDK e-stim box in real time using a local AI during roleplay sessions.

## What it does

A local LLM (via LMStudio) runs inside SillyTavern and generates e-stim patterns on the fly during a roleplay conversation. The AI decides what kind of stimulation to apply based on the narrative context — intensity, speed, electrode focus, waveform shape — and the patterns are sent in real time to ReStim, which drives the NeoDK box.

```
SillyTavern (roleplay UI)
    ↓  AI generates <estim>{...}</estim> tags
SillyTavern Extension (JS)
    ↓  extracts command, sends via WebSocket
Python Bridge (serveur_estim.py)
    ↓  generates full pattern via pattern_generator.py
ReStim (ws://localhost:12346/tcode)
    ↓  T-Code commands
NeoDK box → electrodes
```

## Hardware requirements

- **NeoDK** box flashed with [diglet48's firmware fork](https://github.com/diglet48/NeoDK) (required for 3-phase on PC)
- USB connection to PC
- Windows 10/11

## Software requirements

- [ReStim](https://github.com/diglet48/restim) — must be running with WebSocket server enabled (port 12346)
- [LMStudio](https://lmstudio.ai/) — local LLM server, compatible OpenAI API on port 1234
- [SillyTavern](https://github.com/SillyTavern/SillyTavern) — roleplay interface
- Python 3.10+ with `websockets` package

```
pip install websockets
```

## Installation

### 1. Flash your NeoDK

Follow the instructions on [diglet48/NeoDK](https://github.com/diglet48/NeoDK) to flash the 3-phase firmware. You'll need STM32CubeProgrammer and a USB-to-serial cable.

### 2. Configure ReStim

In ReStim → Preferences → Network:
- Enable **WebSocket server** on port `12346`

In ReStim → Preferences → NeoStim:
- Select your COM port

### 3. Install the SillyTavern extension

Copy the `sillytavern-extension/` folder into:
```
SillyTavern/public/scripts/extensions/third-party/estim-bridge/
```
Then in SillyTavern → Extensions → enable **Estim Bridge**.

### 4. Configure SillyTavern API

In SillyTavern → API settings:
- Source: **OpenAI compatible**
- URL: `http://127.0.0.1:1234/v1`
- API key: `lmstudio` (any value works)
- Model: your preferred local model (Gemma 4 26B recommended)

### 5. Start the bridge

```bash
python serveur_estim.py
```

You should see:
```
✔  Connected to ReStim
✔  WebSocket server started on ws://localhost:5001
Waiting for SillyTavern...
```

### 6. Set up your AI character

Create a character in SillyTavern and paste the contents of `lyna_example_note.txt` into the **Character Note** field (role: System).

## How it works

The AI generates a short command at the start of each response:

```json
<estim>{"action":"generate","type":"vague","intensity":65,"speed":"fast","mood":"dominant","count":8,"shape":"up","focus":"rotate"}</estim>
```

The SillyTavern extension intercepts this tag, strips it from the displayed text, and sends it to the Python bridge via WebSocket. The bridge calls `pattern_generator.py` which computes a full multi-step T-Code pattern and streams it to ReStim in a background loop.

The pattern keeps running while the conversation continues, and is replaced on each new AI response.

## Pattern Generator

The generator (`pattern_generator.py`) translates a simple intent into a complete calibrated pattern with mathematically shaped curves, proper alpha/beta movement, and electrode intensity modulation via `e1`/`e2`/`e3` axes.

### Pattern types

| Type | Description |
|------|-------------|
| `caresse` | Slow gentle rotation |
| `tease` | Irregular oscillation, unpredictable |
| `vague` | Progressive build-up |
| `frisson` | Fast jumps between electrodes |
| `rotation` | Sequential A→B→C rotation |
| `pulsation` | Rhythmic center pulse |
| `tremblement` | Micro-oscillations |
| `onde` | Sinusoidal wave across electrodes |
| `respiration` | Breathing curve (inhale/exhale) |
| `spirale` | Expanding spiral from center |
| `chaos` | Controlled random |
| `spike` | Brief intense peak |
| `climax` | Full intensity build |
| `decompression` | Cool-down after climax |
| `buzz` | High-frequency buzz with vibration layer |
| `edge` | Sustained high intensity with micro-variations |
| `stay` | Stable gentle presence |
| `cum` | Explosive peak then release |
| `slow_stroke` | Slow A↔B sweep through center |
| `fast_stroke` | Fast A→B→C jumps |
| `circle` | True circle via 120° phase shift on e1/e2/e3 |
| `circle_in` | Circle that tightens toward center |

### Parameters

| Parameter | Values | Description |
|-----------|--------|-------------|
| `intensity` | 1–100 | Signal strength (mapped to 15–60% volume) |
| `speed` | `slow` / `medium` / `fast` / `frantic` | Step timing |
| `mood` | `soft` / `tease` / `intense` / `dominant` | Frequency range (8–120 Hz) |
| `count` | 2–16 | Number of steps |
| `shape` | `up` / `down` / `wave` / `pulse` / `spike` / `hold` | Volume curve shape |
| `focus` | `A` / `B` / `C` / `center` / `rotate` / `free` | Electrode focus |

**Spatial modulation:** as intensity increases, the position automatically moves toward the center of the triangle (more concentrated signal). This mirrors how ReStim's native patterns work.

### T-Code axes used

| Axis | Parameter |
|------|-----------|
| `V0` | Volume |
| `L0` | Alpha (vertical position) |
| `L1` | Beta (horizontal position) |
| `P0` | Pulse frequency (up to 120 Hz) |
| `P1` | Pulse width |
| `C0` | Carrier frequency (500–2000 Hz) |
| `E0/E1/E2` | Individual electrode intensity (e1/e2/e3) |
| `V1/V2` | Vibration frequency/strength (buzz & edge) |

## Architecture

```
serveur_estim.py          Python WebSocket bridge
pattern_generator.py      Pattern computation engine
sillytavern-extension/
  index.js                Polls chat, intercepts <estim> tags
  manifest.json           ST extension metadata
lyna_example_note.txt     Example AI character system prompt
```

## Tips

- Use a model with at least 7B parameters. Gemma 4 26B works well. Smaller models tend to forget the XML tags.
- Keep `max_tokens` at 1500+ in SillyTavern to avoid truncated JSON.
- The bridge auto-reconnects if ReStim or SillyTavern restarts.
- Volume calibration: below 15% intensity is imperceptible, above 60% is very strong. Adjust ReStim's output volume slider to your comfort level.
- Pulse frequency: 5–20 Hz = distinct pulses, 50–80 Hz = smooth vibration, 80–120 Hz = intense buzz.

## Acknowledgements

- [diglet48](https://github.com/diglet48) — ReStim and NeoDK 3-phase firmware
- [edger477](https://github.com/edger477) — ReStim development and funscript tools
- [Onwrikbaar](https://github.com/Onwrikbaar) — NeoDK hardware and inspiration
- Joanne's E-stim community for sharing knowledge

## License

MIT — do whatever you want with it, just don't be weird about it.
