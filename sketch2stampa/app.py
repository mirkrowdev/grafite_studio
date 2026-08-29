"""
Grafite — Sketch→Stampa GUI
Finestra principale: header, notebook con due schede, barra di stato.
"""
import tkinter as tk
from tkinter import ttk
import sys
import base64
import io
import logging

from PIL import Image, ImageTk
import numpy as np

import log_setup
from risorse import LOGO_HEADER_B64, LOGO_WATERMARK_B64
from scheda_normalizza import SchedaNormalizza
from scheda_esporta import SchedaEsporta
from scheda_comfyui import SchedaComfyUI

log_setup.configura()
_log = logging.getLogger("grafite.app")


# ---------------------------------------------------------------------------
# Palette colori — unica fonte di verità per l'intero tema scuro
# ---------------------------------------------------------------------------

COLORI = {
    "sfondo_app":   "#111113",
    "barra":        "#1F1F23",
    "superficie":   "#18181B",
    "contenitore":  "#27272A",
    "bordo":        "#3F3F46",
    "bordo_tenue":  "#2A2A2E",
    "testo":        "#E8E6E1",
    "testo_sec":    "#A1A1AA",
    "attenuato":    "#71717A",
    "primario":     "#60A5FA",
    "accento":      "#EA580C",
}


# ---------------------------------------------------------------------------
# Dark mode Windows
# ---------------------------------------------------------------------------

def _imposta_dark_mode_windows(hwnd):
    """Barra del titolo scura su Windows 10 (1809+) e Windows 11."""
    try:
        import ctypes
        ctypes.windll.dwmapi.DwmSetWindowAttribute(
            hwnd, 20, ctypes.byref(ctypes.c_int(1)), ctypes.sizeof(ctypes.c_int))
    except Exception:
        pass


# ---------------------------------------------------------------------------
# Applicazione principale
# ---------------------------------------------------------------------------

class App(tk.Tk):
    COLORI = COLORI  # esposto ai moduli figli

    def __init__(self):
        super().__init__()
        self.title("Grafite — CROBU tech-lab")
        self.geometry("1100x800")
        self.minsize(800, 600)
        self.configure(bg=COLORI["sfondo_app"])

        self._imposta_stile()
        self._crea_filigrana()
        self._crea_header()
        self._crea_notebook()
        self._crea_barra_stato()

        # Cleanup alla chiusura
        self.protocol("WM_DELETE_WINDOW", self._on_chiusura)

        # Dark title bar su Windows
        self.update_idletasks()
        if sys.platform == "win32":
            _imposta_dark_mode_windows(self.winfo_id())

    # ------------------------------------------------------------------
    # Stile ttk
    # ------------------------------------------------------------------

    def _imposta_stile(self):
        style = ttk.Style(self)
        style.theme_use("clam")

        # Notebook
        style.configure("TNotebook",
                         background=COLORI["sfondo_app"],
                         borderwidth=0)
        style.configure("TNotebook.Tab",
                         background=COLORI["barra"],
                         foreground=COLORI["testo_sec"],
                         padding=[14, 6],
                         borderwidth=0)
        style.map("TNotebook.Tab",
                  background=[("selected", COLORI["sfondo_app"]),
                               ("active", COLORI["contenitore"])],
                  foreground=[("selected", COLORI["primario"]),
                               ("active", COLORI["testo"])])

        # Frame
        style.configure("TFrame", background=COLORI["sfondo_app"])
        style.configure("Dark.TFrame", background=COLORI["contenitore"])

        # Separatore
        style.configure("TSeparator", background=COLORI["bordo_tenue"])

        # Scale
        style.configure("TScale",
                         background=COLORI["contenitore"],
                         troughcolor=COLORI["superficie"],
                         sliderthickness=14)
        style.map("TScale",
                  background=[("active", COLORI["primario"])])

        # Combobox
        style.configure("TCombobox",
                         fieldbackground=COLORI["contenitore"],
                         background=COLORI["contenitore"],
                         foreground=COLORI["testo"],
                         selectbackground=COLORI["primario"],
                         selectforeground="#FFFFFF",
                         borderwidth=1,
                         relief="flat")
        style.map("TCombobox",
                  fieldbackground=[("readonly", COLORI["contenitore"])],
                  background=[("readonly", COLORI["contenitore"])],
                  foreground=[("readonly", COLORI["testo"])])

        # Scrollbar
        style.configure("TScrollbar",
                         background=COLORI["contenitore"],
                         troughcolor=COLORI["superficie"],
                         borderwidth=0,
                         arrowcolor=COLORI["testo_sec"])

    # ------------------------------------------------------------------
    # Filigrana corvo (pre-calcolata)
    # ------------------------------------------------------------------

    def _crea_filigrana(self):
        """Canvas di sfondo con la filigrana del corvo incisa."""
        self._canvas_sfondo = tk.Canvas(
            self, bg=COLORI["sfondo_app"], highlightthickness=0)
        self._canvas_sfondo.place(x=0, y=0, relwidth=1, relheight=1)

        # Carica l'immagine watermark
        wm_data = base64.b64decode(LOGO_WATERMARK_B64)
        wm_pil = Image.open(io.BytesIO(wm_data)).convert("RGBA")

        # Crea la sagoma: converte alpha in maschera binaria
        r, g, b, a = wm_pil.split()
        # Il logo è corvo nero su bianco con trasparenza: usa il canale alpha come maschera
        # Se l'immagine non ha trasparenza reale, convertila: i pixel scuri sono il corvo
        arr = np.array(wm_pil)

        # Prepara due versioni della sagoma: ombra (#1E1E23) e principale (#0C0C0E)
        def colore_hex_a_rgb(h):
            h = h.lstrip("#")
            return tuple(int(h[i:i+2], 16) for i in (0, 2, 4))

        c_ombra = colore_hex_a_rgb("#1E1E23")
        c_principale = colore_hex_a_rgb("#0C0C0E")

        # Crea immagine sagoma per ombra (RGBA)
        def sagoma_rgba(arr_rgba, colore_rgb):
            out = np.zeros_like(arr_rgba)
            # Alpha: usa il canale alpha originale dell'immagine
            alpha = arr_rgba[:, :, 3]
            # Se non c'è trasparenza, usa la luminanza invertita come maschera
            if alpha.max() == 0:
                lum = 0.299 * arr_rgba[:, :, 0] + 0.587 * arr_rgba[:, :, 1] + 0.114 * arr_rgba[:, :, 2]
                alpha = (255 - lum).astype(np.uint8)
            out[:, :, 0] = colore_rgb[0]
            out[:, :, 1] = colore_rgb[1]
            out[:, :, 2] = colore_rgb[2]
            out[:, :, 3] = alpha
            return out

        arr_ombra = sagoma_rgba(arr, c_ombra)
        arr_principale = sagoma_rgba(arr, c_principale)

        self._pil_ombra = Image.fromarray(arr_ombra, "RGBA")
        self._pil_principale = Image.fromarray(arr_principale, "RGBA")
        self._tk_wm_ombra = None
        self._tk_wm_principale = None

        # Ridisegna al resize
        self._canvas_sfondo.bind("<Configure>", self._ridisegna_filigrana)

    def _ridisegna_filigrana(self, event=None):
        """Ridisegna la filigrana centrata nel canvas."""
        self._canvas_sfondo.delete("filigrana")
        cw = self._canvas_sfondo.winfo_width()
        ch = self._canvas_sfondo.winfo_height()
        if cw < 10 or ch < 10:
            return

        cx = cw // 2
        cy = ch // 2

        # Ombra: offset +2.5 px in basso a destra (arrotondato a 3)
        ombra = self._pil_ombra
        self._tk_wm_ombra = ImageTk.PhotoImage(ombra)
        self._canvas_sfondo.create_image(
            cx + 3, cy + 3, anchor="center",
            image=self._tk_wm_ombra, tags="filigrana")

        # Sagoma principale: a registro
        principale = self._pil_principale
        self._tk_wm_principale = ImageTk.PhotoImage(principale)
        self._canvas_sfondo.create_image(
            cx, cy, anchor="center",
            image=self._tk_wm_principale, tags="filigrana")

        # Il canvas va sotto tutto il resto
        self._canvas_sfondo.lower()

    # ------------------------------------------------------------------
    # Header
    # ------------------------------------------------------------------

    def _crea_header(self):
        header = tk.Frame(self, bg=COLORI["barra"], height=56)
        header.pack(side="top", fill="x")
        header.pack_propagate(False)

        # Logo corvo
        logo_data = base64.b64decode(LOGO_HEADER_B64)
        logo_pil = Image.open(io.BytesIO(logo_data)).convert("RGBA")

        # Converte sfondo bianco in trasparente per integrarsi con la barra
        # (sostituisce i pixel bianchi con la tinta della barra)
        arr = np.array(logo_pil)
        bar_rgb = tuple(int(COLORI["barra"].lstrip("#")[i:i+2], 16) for i in (0, 2, 4))

        # Se non c'è canale alpha reale, usa luminanza
        alpha = arr[:, :, 3]
        if alpha.max() == 0 or alpha.min() == alpha.max():
            lum = 0.299 * arr[:, :, 0].astype(float) + \
                  0.587 * arr[:, :, 1].astype(float) + \
                  0.114 * arr[:, :, 2].astype(float)
            # Corvo (scuro) → testo chiaro, sfondo bianco → trasparente
            arr[:, :, 3] = (255 - lum).clip(0, 255).astype(np.uint8)

        # Colora il corvo con il testo primario
        testo_rgb = tuple(int(COLORI["testo"].lstrip("#")[i:i+2], 16) for i in (0, 2, 4))
        arr[:, :, 0] = testo_rgb[0]
        arr[:, :, 1] = testo_rgb[1]
        arr[:, :, 2] = testo_rgb[2]

        logo_finale = Image.fromarray(arr, "RGBA")
        self._tk_logo = ImageTk.PhotoImage(logo_finale)

        tk.Label(header, image=self._tk_logo,
                 bg=COLORI["barra"]).pack(side="left", padx=(16, 8), pady=4)

        # Testo
        fr_testo = tk.Frame(header, bg=COLORI["barra"])
        fr_testo.pack(side="left", pady=4)

        tk.Label(fr_testo, text="CROBU tech-lab",
                 bg=COLORI["barra"], fg=COLORI["testo_sec"],
                 font=("sans-serif", 9)).pack(anchor="sw")
        tk.Label(fr_testo, text="Grafite",
                 bg=COLORI["barra"], fg=COLORI["testo"],
                 font=("sans-serif", 14, "bold")).pack(anchor="nw")

    # ------------------------------------------------------------------
    # Notebook
    # ------------------------------------------------------------------

    def _crea_notebook(self):
        self._notebook = ttk.Notebook(self)
        self._notebook.pack(side="top", fill="both", expand=True,
                            padx=0, pady=0)

        self._scheda_norm = SchedaNormalizza(self._notebook, app=self,
                                             style="TFrame")
        self._notebook.add(self._scheda_norm, text="  Normalizza  ")

        self._scheda_comfyui = SchedaComfyUI(self._notebook, app=self,
                                              style="TFrame")
        self._notebook.add(self._scheda_comfyui, text="  ComfyUI  ")

        self._scheda_esp = SchedaEsporta(self._notebook, app=self,
                                          style="TFrame")
        self._notebook.add(self._scheda_esp, text="  Esporta  ")

    # ------------------------------------------------------------------
    # Barra di stato
    # ------------------------------------------------------------------

    def _crea_barra_stato(self):
        barra = tk.Frame(self, bg=COLORI["barra"], height=28)
        barra.pack(side="bottom", fill="x")
        barra.pack_propagate(False)

        self._lbl_stato = tk.Label(barra, text="Pronto.",
                                   bg=COLORI["barra"], fg=COLORI["testo_sec"],
                                   anchor="w", padx=12)
        self._lbl_stato.pack(side="left", fill="both", expand=True)

    def imposta_stato(self, msg, tipo="info"):
        """Aggiorna la barra di stato e scrive nel log.

        tipo: "info" | "errore" | "avviso"
        """
        colori_testo = {
            "info":   COLORI["testo_sec"],
            "errore": "#F87171",   # rosso tenue
            "avviso": "#F2B48A",   # arancione tenue
        }
        fg = colori_testo.get(tipo, COLORI["testo_sec"])

        # Log sul file
        if tipo == "errore":
            _log.error(msg)
            testo_barra = f"{msg}  —  log: {log_setup.percorso_log()}"
        elif tipo == "avviso":
            _log.warning(msg)
            testo_barra = msg
        else:
            _log.info(msg)
            testo_barra = msg

        self._lbl_stato.config(text=testo_barra, fg=fg)

    # ------------------------------------------------------------------
    # Accesso schede per comunicazione inter-scheda
    # ------------------------------------------------------------------

    @property
    def scheda_esporta(self):
        return self._scheda_esp

    def seleziona_scheda_esporta(self):
        self._notebook.select(self._scheda_esp)

    # ------------------------------------------------------------------
    # Chiusura
    # ------------------------------------------------------------------

    def _on_chiusura(self):
        try:
            self._scheda_comfyui.cleanup()
        except Exception:
            _log.exception("Errore durante il cleanup ComfyUI")
        self.destroy()


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main():
    app = App()
    app.mainloop()


if __name__ == "__main__":
    main()
