# Grafite

Desktop GUI for the Sketch→Print workflow — built with Python and Tkinter.

Wraps two processing scripts into a clean dark-themed interface:

- **Normalize** (Phase 1): perspective correction, paper tone neutralization, local contrast enhancement (CLAHE)
- **Export** (Phase 4): resize to print scenario, color profile, DPI metadata, LZW TIFF output

Phases 2 (AI master generation) and 3 (upscale in ComfyUI) are manual external steps and are intentionally outside the scope of this tool.

---

## Requirements

- Python 3.10+
- On Ubuntu, Tkinter may not be bundled with Python:
  ```bash
  sudo apt install python3-tk
  ```
- Python dependencies:
  ```bash
  pip install -r sketch2stampa/requirements.txt
  ```

---

## Run from source

```bash
cd sketch2stampa
python3 app.py
```

---

## Build standalone executable

PyInstaller must be run separately on each target system — no cross-compilation.

**Ubuntu:**
```bash
cd sketch2stampa
pip install pyinstaller
pyinstaller --onefile --windowed --name grafite app.py
# Output: dist/grafite
```

**Windows:**
```cmd
cd sketch2stampa
pip install pyinstaller
pyinstaller --onefile --windowed --name grafite app.py
:: Output: dist\grafite.exe
```

Expected size: 150–250 MB (mostly OpenCV and NumPy). No external files needed next to the executable.

---

## Adding a print scenario

Edit the `SCENARI` dictionary in `sketch2stampa/export_stampa.py`. Adding a scenario takes three lines — the new entry appears automatically in the dropdown with its detail panel:

```python
"my_format": {
    "cm": (40, 50),
    "dpi": 240,
    "profilo": "sRGB",
    "adatta": "contieni",   # "contieni" = white margin | "riempi" = crop
    "sfondo": (255, 255, 255),
},
```

Optional key: `bordo_cm` — extra border for canvas wrap (added to all sides).

---

## Preview accuracy note

The Normalize tab previews processing on a downscaled image (~900 px). CLAHE (local contrast) behaves differently at reduced resolution — **the preview is approximate**. The saved file is always processed at full resolution.

---

## Project layout

```
sketch2stampa/
├── app.py                  entry point, window, header, tabs
├── scheda_normalizza.py    Normalize tab
├── scheda_esporta.py       Export tab
├── normalizza.py           Phase 1 engine
├── export_stampa.py        Phase 4 engine
├── profilo_adobergb.py     Adobe RGB (1998) ICC profile builder
├── risorse.py              logo embedded as base64
└── requirements.txt
```

---

## License

Personal tool — no license.
