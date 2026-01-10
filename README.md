# Duck Game Haptics 🦆🔊

Bring tactile feedback to Duck Game using Intiface-compatible devices.

A small, configurable helper that watches your screen for in-game +1 events and sends smooth, time-limited vibration events to connected devices. Designed for players, streamers, and modders who want matches to feel more immersive.

---

## 🔍 Overview

- Real-time haptic feedback for Duck Game using Intiface Central and compatible toys.
- Index-based menus (language, monitors, colors, devices) to avoid locale issues.
- Per-player time-limited vibration events (first/low intensity ~20s → last/high intensity ~10s) with a smooth cosine decay envelope and a sinusoidal carrier signal.
- Optional `templates/intermission.png` detection to reset vibrations during intermissions.

## ✅ Features

- Monitor selection by index
- Language selection (English / Español)
- Global intensity multiplier (0.0–1.0)
- Per-player vibration events with duration mapped from intensity (non-linear curve)
- Smooth fade-out envelope and sine-based amplitude modulation
- Safe shutdown and device stop on exit

## 📦 Requirements

- Python 3.8+
- `Intiface Central` running locally and devices added to Intiface
- Dependencies listed in `requirements.txt` (install with pip)

## ⚙️ Installation

1. Clone the repo:

   ```bash
   git clone https://github.com/yourname/duckgame_haptics.git
   cd duckgame_haptics
   ```

2. Install dependencies:

   ```bash
   pip install -r requirements.txt
   ```

3. Make sure Intiface Central is installed, running, and your devices are connected and authorized in Intiface.


## 📦 Packaging / Distributing an executable

If you want to distribute the tool as a standalone executable so users don't need Python installed, you can build a single-file executable (Windows `.exe`) using PyInstaller. Example (Windows):

```powershell
pyinstaller --onefile --add-data "templates;templates" main.py
```

Notes:
- Users running the distributed `.exe` do **not** need Python installed; the executable bundles the Python runtime and dependencies.
- Intiface Central still **must** be installed and running on the user's machine for devices to be available and accessible.
- Ensure the `templates/` folder (including `template.png` and optional `intermission.png`) is included in the build via `--add-data` (Windows uses `;` as the separator, macOS/Linux use `:`).
- Test the generated executable on a clean machine or VM to verify it works as expected and that Intiface devices are recognized.

## ▶️ Usage

1. Start the program:

   ```bash
   python main.py
   ```

2. Follow prompts (index-based):
   - Choose language (0 = English, 1 = Español)
   - Program will attempt to connect to Intiface (ensure Intiface Central is running)
   - Select monitor index (the program lists available monitors)
   - Set the global intensity multiplier (0.0–1.0)
   - Enter number of players and configure each player by selecting the duck color index and the device index

   Notes on play modes:
   - **Local play:** To play locally on a single machine, select **more than one player** and assign each player a connected device.
   - **Online play:** For online matches, each remote player must run their **own instance** of this program and configure their own Intiface environment and device(s) locally—devices do not transmit over the network.

3. While Duck Game runs, the script watches for the `template.png` match (in `templates/`) indicating a +1 event, then:
   - The winner's intensity decreases; losers' intensity increases and **a timed vibration event** triggers
   - Timed event duration is mapped from the new intensity (low-intensity events are longer, high-intensity events shorter)
   - If `templates/intermission.png` is present and detected, all vibrations are reset

4. Press `q` in the console to quit; devices are stopped safely.

## 🧭 Configuration / Tuning

- Templates:
  - `templates/template.png` — REQUIRED. Used to detect the +1 event.
  - `templates/intermission.png` — optional. If present, triggers a reset of vibrations when detected.

- Code-level parameters (in `DuckHaptics.__init__`):
  - `vibration_freq` (Hz) — sine carrier frequency (default 40 Hz)
  - `vibration_rate` (Hz) — how many times per second the vibration level is updated (default 40 Hz)
  - `duration_for_intensity()` — maps intensity → duration; tweak `duration_curve_exponent` to change curve behavior

If you want these exposed as CLI args or a config file, I can add that.

## 🧪 Testing without hardware

- Run the program without devices connected to verify prompts and monitor/template matching.
- Logs will show device scan results and template-detection messages. To fully validate vibrations, connect at least one Intiface-recognized device.

## ⚙️ Troubleshooting

- "No devices found": ensure Intiface Central is running and the device is authorized/paired.
- Template not found: check `templates/template.png` path and that the screen contents match the image at the correct scale.

## 🤝 Contributing

Contributions, bug reports, and PRs are welcome. Please open issues or PRs for features, bug fixes, or improvements (i.e., CLI arguments, config files, improved templates or matching logic).

## License

This repo does not include a license file by default. If you'd like, I can add an MIT or other permissive license for you.