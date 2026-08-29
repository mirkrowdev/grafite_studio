# Grafite — Sketch→Stampa GUI

Interfaccia grafica per le fasi 1 e 4 del workflow Sketch→Stampa:

- **Normalizza**: raddrizzamento prospettico, neutralizzazione del tono carta, contrasto CLAHE
- **Esporta**: ridimensionamento per scenario di stampa, profilo colore, salvataggio TIFF

Le due schede sono indipendenti: tra l'una e l'altra c'è un passaggio manuale esterno
(fase 2 — generazione AI, fase 3 — upscale in ComfyUI).

---

## Requisiti

- Python 3.10 o superiore
- Dipendenze Python:
  ```
  pip install -r requirements.txt
  ```
- Su Ubuntu, Tkinter non è sempre incluso con Python:
  ```
  sudo apt install python3-tk
  ```

---

## Avvio da sorgente

```bash
python3 app.py
```

oppure doppio clic su `app.py` (se il sistema operativo è configurato per aprire `.py` con Python).

---

## Avvertenza sulla fedeltà dell'anteprima

L'anteprima nella scheda Normalizza lavora su una versione ridotta dell'immagine (~900 px
lato massimo). CLAHE (contrasto locale) è un'operazione locale: il suo effetto su
un'immagine piccola non è identico a quello sull'originale a piena risoluzione.
**L'anteprima è indicativa, non esatta.** Il file salvato è sempre elaborato a piena
risoluzione, indipendentemente dall'anteprima.

---

## Compilazione con PyInstaller

PyInstaller deve essere eseguito separatamente su ogni sistema: non fa cross-compilazione.

**Ubuntu:**
```bash
pip install pyinstaller
pyinstaller --onefile --windowed --name grafite app.py
# Eseguibile: dist/grafite
```

**Windows:**
```cmd
pip install pyinstaller
pyinstaller --onefile --windowed --name grafite app.py
:: Eseguibile: dist\grafite.exe
```

Il peso atteso dell'eseguibile è 150–250 MB (prevalentemente OpenCV e NumPy).
Nessun file esterno è richiesto accanto all'eseguibile.

---

## Aggiungere uno scenario di stampa

Modificare il dizionario `SCENARI` in `export_stampa.py`. Aggiungere uno scenario
richiede tre righe, e la nuova voce compare automaticamente nella tendina:

```python
"mio_formato": {
    "cm": (40, 50),
    "dpi": 240,
    "profilo": "sRGB",
    "adatta": "contieni",
    "sfondo": (255, 255, 255),
},
```

Chiavi opzionali: `bordo_cm` (bordo aggiuntivo per canvas avvolgente).
