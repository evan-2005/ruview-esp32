# RuView — Complete Setup Guide (ESP32-S3 + Windows laptop)

Everything needed to go from a fresh clone of this fork
([evan-2005/ruview-esp32](https://github.com/evan-2005/ruview-esp32), upstream:
[ruvnet/RuView](https://github.com/ruvnet/RuView), MIT) to a live WiFi-sensing
dashboard. The default path needs **only Python — no Rust, no Docker**.

---

## 0 — Prerequisites

| Tool | Needed for | Install |
|------|------------|---------|
| Python 3.10+ | GUI + sensing backend + flashing | [python.org](https://www.python.org/downloads/) — check "Add to PATH" |
| `websockets`, `numpy` | Sensing backend | `pip install websockets numpy` |
| `esptool`, `pyserial` | Flashing / provisioning the ESP32 | `pip install esptool pyserial` |
| CP210x USB driver | ESP32 board shows up as a COM port | [silabs.com driver page](https://www.silabs.com/developers/usb-to-uart-bridge-vcp-drivers) |
| ESP32-S3 board | Real CSI sensing | Any ESP32-S3 with 4 MB or 8 MB flash (plain ESP32 / ESP32-C3 are **not** supported) |

Optional (only for the full Rust pipeline, see step 5): Rust toolchain or Docker Desktop.

Verify the Python deps:

```
python -c "import websockets, numpy; print('deps OK')"
```

---

## 1 — Start the GUI (works immediately, no hardware needed)

```
python scripts/start-gui.py
```

or double-click `scripts/start-gui.bat`. This starts two things and opens your browser:

| What | Where |
|------|-------|
| Sensing backend (pure Python, `archive/v1`) | `ws://localhost:8765` |
| Web dashboard (`ui/`, no-cache static server) | `http://localhost:8080` |

The backend picks its data source automatically, best available first:

1. **ESP32 CSI** on UDP `:5005` → banner: `LIVE — ESP32 HARDWARE`
2. **Laptop WiFi RSSI** (via `netsh`) → banner: `LIVE — LAPTOP WIFI RSSI`
3. Simulation (only if both fail) → clearly labeled `SIMULATED`

So you get a live dashboard from your laptop's own WiFi signal before the ESP32 is
even flashed. Stop everything with Ctrl+C.

> Keep the UI on port 8080 — the UI maps `:8080 → ws :8765` (`:3000 → :3001` is
> reserved for the Docker/Rust-server convention). If a sensing server is already
> running on :8765, the launcher reuses it instead of starting a second one.

**Dashboard tabs:** Dashboard (status overview) · Sensing (live 3D signal field —
the main view) · Live Demo (pose canvas; needs the Rust server) · Pose Fusion ·
Observatory. Keyboard: `1`/`2`/`3` switch tabs, `Ctrl+K` command palette, `?` help.

---

## 2 — Flash the ESP32-S3

Pre-built firmware **v0.6.7** is in `firmware/esp32-csi-node/release_bins/` — no build needed.

1. Plug the board in over USB. Find its COM port: Device Manager → Ports (COM & LPT),
   or `python -m serial.tools.list_ports`. (No port? Install the CP210x driver above.)
2. Flash — **8 MB boards** (offsets are from `firmware/esp32-csi-node/README.md`;
   replace `COM7` with your port):

```
python -m esptool --chip esp32s3 --port COM7 --baud 460800 ^
  write_flash --flash_mode dio --flash_size 8MB ^
  0x0     firmware/esp32-csi-node/release_bins/bootloader.bin ^
  0x8000  firmware/esp32-csi-node/release_bins/partition-table.bin ^
  0xf000  firmware/esp32-csi-node/release_bins/ota_data_initial.bin ^
  0x20000 firmware/esp32-csi-node/release_bins/esp32-csi-node.bin
```

**4 MB boards**: swap in `esp32-csi-node-4mb.bin` + `partition-table-4mb.bin` and
use `--flash_size 4MB`.

(On Git Bash / Linux / macOS replace the `^` line continuations with `\`.)

---

## 3 — Point the ESP32 at the laptop

1. Get the laptop's LAN IP: `ipconfig` → "Wireless LAN adapter Wi-Fi" → IPv4 Address
   (e.g. `192.168.1.20`).
2. Provision over USB serial — no reflash needed:

```
python firmware/esp32-csi-node/provision.py --port COM7 ^
  --ssid "YourWiFi" --password "secret" ^
  --target-ip <laptop IPv4> --target-port 5005
```

3. Allow inbound UDP 5005 through Windows Firewall (run as Administrator):

```
netsh advfirewall firewall add rule name="ESP32 CSI" dir=in action=allow protocol=UDP localport=5005
```

4. Restart the GUI. Within a few seconds the banner should flip to
   `LIVE — ESP32 HARDWARE`.

---

## 4 — Verify it's working

- **Serial monitor:** `python -m serial.tools.miniterm COM7 115200` should show
  `CSI streaming active -> <laptop-ip>:5005` after boot.
- **Dashboard:** Sensing tab banner is green `LIVE — ESP32 HARDWARE`; the Dashboard
  tab's Data Source card shows `ESP32 / Real hardware connected`.
- Walk around the room — motion metrics and the 3D signal field should react.

---

## 5 — Optional: full Rust sensing server (pose, vitals, training)

The Python GUI covers presence/motion. The full pipeline (pose heuristics,
breathing/heart-rate extraction, `.rvf` model training) is the Rust
`wifi-densepose-sensing-server`. Either:

- **Rust:** install [rustup](https://rustup.rs) (MSVC Build Tools already present on
  this machine), then:
  `cd v2 && cargo run -p wifi-densepose-sensing-server -- --http-port 3000 --source esp32`
- **Docker:** `docker run -p 3000:3000 -p 5005:5005/udp ruvnet/wifi-densepose:latest --source esp32`

Then open `http://localhost:3000` (the Rust server ships its own richer UI).
Stop the Python GUI first if it's holding UDP :5005.

---

## 6 — Troubleshooting

| Symptom | Fix |
|---------|-----|
| Banner stuck on `RECONNECTING` | Backend not running — start via `scripts/start-gui.py`, not a bare `http.server` |
| Banner shows `LAPTOP WIFI RSSI` after flashing | ESP32 not reaching the laptop: same WiFi subnet? firewall rule added? `--target-ip` correct? |
| Banner shows `SIMULATED` | No ESP32 **and** `netsh` RSSI unavailable (WiFi adapter off?) |
| No COM port | Install CP210x driver; try another USB cable (must be data-capable) |
| `esptool` can't connect | Hold the board's BOOT button while flashing starts |
| WiFi won't connect after provisioning | Re-run `provision.py` with exact SSID/password; 2.4 GHz network required |
| Presence reads wrong right after boot | Wait ~60 s (adaptive calibration); power-cycle in an empty room |
| Ghost detections | Strong RF interferers (microwave, fan near antenna) — recalibrate by power-cycling |
| UI looks stale after a `git pull` | Hard-refresh once (Ctrl+F5); the service worker is network-first so this should be rare |

---

## 7 — Be accurate about capabilities

When describing this project anywhere external, reflect the repo's own caveats:

- Presence detection is a **calibrated variance/heuristic threshold**, not a trained
  classifier, unless a `.rvf` model file is explicitly loaded.
- Dashboard pose skeletons are **signal-heuristic-driven** unless a trained model is
  supplied — no pretrained pose weights ship in-repo.
- The first **~60 seconds** after ESP32 boot is an adaptive calibration window.
- Strong RF interferers can cause false-positive presence until calibration reconverges.
- Laptop-RSSI mode is far coarser than ESP32 CSI — treat it as a demo/diagnostic source.

---

## 8 — What's mine vs. upstream

Upstream RuView: firmware, sensing servers, signal processing, base UI.
This fork adds (named in commits/writeups):

- **Streamlined laptop dashboard** (`ui/`): trimmed to Dashboard/Sensing/Live Demo,
  honest data-source labels (ESP32 CSI vs laptop RSSI vs simulated), network-first
  service worker (no stale UI), quiet handling of the absent REST API in
  Python-only mode.
- **`scripts/start-gui.py` / `.bat`**: zero-Rust one-command GUI launcher —
  no-cache static serving, sensing-backend reuse, localhost-only binding.
