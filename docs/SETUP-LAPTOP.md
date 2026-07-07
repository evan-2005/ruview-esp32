# RuView setup — ESP32-S3 + Windows laptop

Tailored to this fork ([evan-2005/ruview-esp32](https://github.com/evan-2005/ruview-esp32),
upstream: [ruvnet/RuView](https://github.com/ruvnet/RuView), MIT). Written for a laptop with
**Python 3.11 + Node 24 only** — no Rust toolchain, no Docker needed for the default path.

## Current state (already done)

- ✅ Repo imported from the upstream ZIP; `git init` done; remote `origin` points to
  `https://github.com/evan-2005/ruview-esp32.git` with an honest provenance commit
  (`Initial import of RuView (MIT-licensed, upstream: ruvnet/RuView)`).
- ✅ Upstream `LICENSE` (MIT, Copyright (c) 2024 rUv) preserved unmodified at the repo root.
- ✅ Attribution section added at the top of `README.md`.
- ✅ Streamlined laptop GUI verified working (see below).

## 1 — Start the GUI (works right now, no hardware needed)

```
python scripts/start-gui.py
```

or double-click `scripts/start-gui.bat`. This starts:

| What | Where | Notes |
|------|-------|-------|
| Sensing backend (pure Python) | `ws://localhost:8765` | `archive/v1` server; needs `pip install websockets numpy` (already installed) |
| Web dashboard | `http://localhost:8080` | Opens automatically in your browser |

The backend auto-detects its data source, best first:

1. **ESP32 CSI** on UDP `:5005` → banner shows `LIVE — ESP32 HARDWARE`
2. **Laptop WiFi RSSI** (via `netsh`) → banner shows `LIVE — LAPTOP WIFI RSSI`
3. Simulation (only if both fail) → clearly labeled `SIMULATED`

So before the ESP32 is even flashed, you get a live dashboard driven by your laptop's own
WiFi signal. Keep the UI on port 8080 — the UI maps `:8080 → ws :8765` (and `:3000 → :3001`,
which is the Docker/Rust-server convention).

## 2 — Flash the ESP32-S3

Pre-built firmware **v0.6.7** ships in `firmware/esp32-csi-node/release_bins/` — no build needed.

1. Confirm the board is an **ESP32-S3** (plain ESP32 / ESP32-C3 are unsupported).
2. Install the [CP210x USB driver](https://www.silabs.com/developers/usb-to-uart-bridge-vcp-drivers)
   if the board doesn't show up as a COM port.
3. Find the COM port: Device Manager → Ports, or `python -m serial.tools.list_ports`.
4. Install esptool: `pip install esptool`
5. Flash (8 MB boards; offsets from `firmware/esp32-csi-node/README.md`):

```
python -m esptool --chip esp32s3 --port COM7 --baud 460800 ^
  write_flash --flash_mode dio --flash_size 8MB ^
  0x0     firmware/esp32-csi-node/release_bins/bootloader.bin ^
  0x8000  firmware/esp32-csi-node/release_bins/partition-table.bin ^
  0xf000  firmware/esp32-csi-node/release_bins/ota_data_initial.bin ^
  0x20000 firmware/esp32-csi-node/release_bins/esp32-csi-node.bin
```

For 4 MB boards use `esp32-csi-node-4mb.bin` + `partition-table-4mb.bin` with `--flash_size 4MB`.

## 3 — Point the ESP32 at the laptop

1. Find the laptop's LAN IP: `ipconfig` → "Wireless LAN adapter Wi-Fi" → IPv4 Address.
2. Provision over USB serial (no reflash needed):

```
python firmware/esp32-csi-node/provision.py --port COM7 ^
  --ssid "YourWiFi" --password "secret" ^
  --target-ip <laptop IPv4> --target-port 5005
```

3. Allow inbound UDP 5005 through Windows Firewall (admin PowerShell):

```
netsh advfirewall firewall add rule name="ESP32 CSI" dir=in action=allow protocol=UDP localport=5005
```

4. Restart the GUI (`python scripts/start-gui.py`). Within a few seconds the banner should
   flip to `LIVE — ESP32 HARDWARE`. If not: same WiFi subnet? firewall rule applied?
   Serial monitor (`python -m serial.tools.miniterm COM7 115200`) should show
   `CSI streaming active -> <laptop-ip>:5005`.

## 4 — Optional: full Rust sensing server (pose, vitals, training)

The Python GUI covers presence/motion. The full pipeline (17-keypoint pose heuristics,
breathing/heart-rate extraction, `.rvf` model training) lives in the Rust
`wifi-densepose-sensing-server`, which needs either:

- **Rust**: install [rustup](https://rustup.rs) (MSVC is already on this machine), then
  `cd v2 && cargo run -p wifi-densepose-sensing-server -- --http-port 3000 --source esp32`
- **Docker**: `docker run -p 3000:3000 -p 5005:5005/udp ruvnet/wifi-densepose:latest --source esp32`

Then open `http://localhost:3000` (the Rust server serves its own richer UI).

## 5 — Be accurate about capabilities

When describing this project anywhere external, reflect the repo's own caveats:

- Presence detection is a **calibrated variance/heuristic threshold**, not a trained
  classifier, unless a `.rvf` model file is explicitly loaded.
- Dashboard pose skeletons are **signal-heuristic-driven** (amplitude variance, motion-band
  power) unless a trained model is supplied — no pretrained pose weights ship in-repo.
- The first **~60 seconds** after ESP32 boot is an adaptive calibration window; power-cycle
  in an empty room if presence reads wrong.
- Strong RF interferers (microwaves, fans near the antenna, neighboring-AP power swings)
  can cause false-positive presence until calibration reconverges.
- The laptop-RSSI mode is far coarser than ESP32 CSI — treat it as a demo/diagnostic source.

## 6 — What's mine vs. upstream

Upstream RuView: firmware, sensing servers, signal processing, base UI.
This fork adds (name these in commits/writeups):

- Streamlined laptop dashboard (`ui/` — trimmed tabs, honest data-source labels,
  cache-safe service worker).
- `scripts/start-gui.py` / `.bat` — zero-Rust one-command GUI launcher with
  no-cache static serving and ESP32/RSSI auto-detection reuse.
