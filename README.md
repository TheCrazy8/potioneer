# Potioneer

A cozy, forest-themed potion brewing game built with Tkinter.

## Features

- Inventory of ingredients and a cauldron to mix them
- Flexible recipe specs via `requires()` (kwargs, dicts, pairs, strings)
- Brew only when the pot matches a recipe exactly (no extras)
- Images for ingredients and potions (Pillow-powered), with graceful fallbacks
- Auto-save progress to your user data folder; manual Save and Reset buttons

## Run (Windows)

From the repo root:

```powershell
python .\docs\main.py
```

Requires Python 3.10+ and these packages:

```powershell
pip install -r requirements.txt
```

## Assets

Place images in any of these, checked in order:

1. User data: %LOCALAPPDATA%\Potioneer\assets\ingredients\<name>.png
   and %LOCALAPPDATA%\Potioneer\assets\potions\<potion>.png
2. Bundled (inside the EXE, handled automatically)
3. Dev repo: docs\assets\ingredients and docs\assets\potions

Supported formats with Pillow installed: png/jpg/webp/gif; without Pillow, Tk supports png/gif/ppm/pgm.

## Save data

- Auto-saved to `%LOCALAPPDATA%\Potioneer\save.json` on most actions and on exit
- “Save Now” and “Reset Progress” available in the Cauldron panel

## Building a Windows EXE

1. Install dependencies:

```powershell
pip install -r requirements.txt
pip install pyinstaller
```

1. Build:

```powershell
python .\makeexe.py
```

Artifacts go to `dist/Potioneer`.

## Installer (Inno Setup)

- GitHub Actions workflow `build-exe.yml` builds the EXE and compiles `installer/potioneer.iss` into `installer/out/PotioneerInstaller.exe`.

## License

Apache 2.0 (see LICENSE)
