"""
Scheda Normalizza — interfaccia per la fase 1 (correzione prospettica + normalizzazione).
"""
import tkinter as tk
from tkinter import ttk, filedialog
import threading
import logging
import os
import cv2
import numpy as np
from PIL import Image, ImageTk
from normalizza import normalizza_array

_log = logging.getLogger("grafite.normalizza")


class SchedaNormalizza(ttk.Frame):
    FORZA_WB_DEFAULT = 0.7
    CLIP_DEFAULT = 1.6
    MAX_PREVIEW = 900      # px lato massimo per l'anteprima
    PREVIEW_BG = "#808080" # grigio 50%
    MARKER_RAGGIO = 8
    DRAG_SOGLIA = 15       # px di distanza per iniziare drag

    def __init__(self, parent, app, **kwargs):
        super().__init__(parent, **kwargs)
        self._app = app
        self._img_orig = None       # array BGR originale a piena risoluzione
        self._img_preview = None    # array BGR ridotto per l'anteprima
        self._scala = 1.0           # fattore di riduzione (preview / originale)
        self._angoli = []           # lista di (x,y) in coordinate preview
        self._drag_idx = None       # indice del punto in trascinamento
        self._drag_ultimo = None    # coordinata durante il drag
        self._tk_img = None         # PhotoImage corrente (tiene in vita il riferimento)
        self._timer_ricalcolo = None
        self._path_orig = None
        self._forza_wb = tk.DoubleVar(value=self.FORZA_WB_DEFAULT)
        self._clip = tk.DoubleVar(value=self.CLIP_DEFAULT)
        self._etichette_angoli = ["TL", "TR", "BR", "BL"]

        self._crea_layout()

    # ------------------------------------------------------------------
    # Layout
    # ------------------------------------------------------------------

    def _crea_layout(self):
        self.columnconfigure(0, weight=0, minsize=230)
        self.columnconfigure(1, weight=1)
        self.rowconfigure(0, weight=1)

        # --- Pannello sinistro controlli ---
        pannello = tk.Frame(self, bg=self._colore("contenitore"))
        pannello.grid(row=0, column=0, sticky="nsew", padx=(8, 4), pady=8)
        pannello.columnconfigure(0, weight=1)

        # Carica
        tk.Label(pannello, text="IMMAGINE", bg=self._colore("contenitore"),
                 fg=self._colore("testo_sec"), font=("sans-serif", 8)).grid(
            row=0, column=0, sticky="w", padx=10, pady=(12, 2))
        tk.Button(pannello, text="Carica immagine...", command=self._carica_immagine,
                  bg=self._colore("contenitore"), fg=self._colore("testo"),
                  activebackground=self._colore("bordo"), activeforeground=self._colore("testo"),
                  relief="flat", padx=10, pady=6, cursor="hand2").grid(
            row=1, column=0, sticky="ew", padx=10, pady=(0, 10))

        ttk.Separator(pannello, orient="horizontal").grid(
            row=2, column=0, sticky="ew", padx=10, pady=4)

        # Angoli
        tk.Label(pannello, text="ANGOLI DEL FOGLIO", bg=self._colore("contenitore"),
                 fg=self._colore("testo_sec"), font=("sans-serif", 8)).grid(
            row=3, column=0, sticky="w", padx=10, pady=(8, 2))

        self._lbl_angoli = tk.Label(pannello,
                                    text="Clicca 4 angoli sull'anteprima",
                                    bg=self._colore("contenitore"),
                                    fg=self._colore("attenuato"),
                                    wraplength=200, justify="left")
        self._lbl_angoli.grid(row=4, column=0, sticky="w", padx=10, pady=(0, 6))

        fr_btn_angoli = tk.Frame(pannello, bg=self._colore("contenitore"))
        fr_btn_angoli.grid(row=5, column=0, sticky="ew", padx=10, pady=(0, 6))
        fr_btn_angoli.columnconfigure(0, weight=1)
        fr_btn_angoli.columnconfigure(1, weight=1)

        self._btn_annulla = tk.Button(fr_btn_angoli, text="Annulla ultimo",
                                      command=self._annulla_ultimo,
                                      bg=self._colore("contenitore"),
                                      fg=self._colore("testo"),
                                      activebackground=self._colore("bordo"),
                                      activeforeground=self._colore("testo"),
                                      relief="flat", padx=6, pady=4, cursor="hand2")
        self._btn_annulla.grid(row=0, column=0, sticky="ew", padx=(0, 2))

        self._btn_azzera = tk.Button(fr_btn_angoli, text="Azzera",
                                     command=self._azzera_angoli,
                                     bg=self._colore("contenitore"),
                                     fg=self._colore("testo"),
                                     activebackground=self._colore("bordo"),
                                     activeforeground=self._colore("testo"),
                                     relief="flat", padx=6, pady=4, cursor="hand2")
        self._btn_azzera.grid(row=0, column=1, sticky="ew", padx=(2, 0))

        ttk.Separator(pannello, orient="horizontal").grid(
            row=6, column=0, sticky="ew", padx=10, pady=4)

        # Parametri
        tk.Label(pannello, text="PARAMETRI", bg=self._colore("contenitore"),
                 fg=self._colore("testo_sec"), font=("sans-serif", 8)).grid(
            row=7, column=0, sticky="w", padx=10, pady=(8, 2))

        # Forza WB
        fr_wb = tk.Frame(pannello, bg=self._colore("contenitore"))
        fr_wb.grid(row=8, column=0, sticky="ew", padx=10, pady=(2, 0))
        fr_wb.columnconfigure(0, weight=1)
        tk.Label(fr_wb, text="Neutralizzazione carta",
                 bg=self._colore("contenitore"), fg=self._colore("testo"),
                 anchor="w").grid(row=0, column=0, sticky="w")
        self._lbl_wb_val = tk.Label(fr_wb, text=f"{self.FORZA_WB_DEFAULT:.2f}",
                                    bg=self._colore("contenitore"),
                                    fg=self._colore("primario"), width=5)
        self._lbl_wb_val.grid(row=0, column=1)

        self._scale_wb = ttk.Scale(pannello, from_=0.0, to=1.0,
                                   variable=self._forza_wb,
                                   command=self._on_slider_change)
        self._scale_wb.grid(row=9, column=0, sticky="ew", padx=10, pady=(2, 8))

        # Clip CLAHE
        fr_clip = tk.Frame(pannello, bg=self._colore("contenitore"))
        fr_clip.grid(row=10, column=0, sticky="ew", padx=10, pady=(2, 0))
        fr_clip.columnconfigure(0, weight=1)
        tk.Label(fr_clip, text="Contrasto del tratto",
                 bg=self._colore("contenitore"), fg=self._colore("testo"),
                 anchor="w").grid(row=0, column=0, sticky="w")
        self._lbl_clip_val = tk.Label(fr_clip, text=f"{self.CLIP_DEFAULT:.1f}",
                                      bg=self._colore("contenitore"),
                                      fg=self._colore("primario"), width=5)
        self._lbl_clip_val.grid(row=0, column=1)

        self._scale_clip = ttk.Scale(pannello, from_=0.5, to=4.0,
                                     variable=self._clip,
                                     command=self._on_slider_change)
        self._scale_clip.grid(row=11, column=0, sticky="ew", padx=10, pady=(2, 8))

        # Ripristina
        tk.Button(pannello, text="Ripristina consigliati",
                  command=self._ripristina_default,
                  bg=self._colore("contenitore"), fg=self._colore("testo_sec"),
                  activebackground=self._colore("bordo"),
                  activeforeground=self._colore("testo"),
                  relief="flat", padx=10, pady=4, cursor="hand2").grid(
            row=12, column=0, sticky="ew", padx=10, pady=(0, 10))

        ttk.Separator(pannello, orient="horizontal").grid(
            row=13, column=0, sticky="ew", padx=10, pady=4)

        # Salva
        self._btn_salva = tk.Button(pannello, text="Salva PNG...",
                                    command=self._salva,
                                    state="disabled",
                                    bg=self._colore("accento"), fg="#FFFFFF",
                                    activebackground="#C04A0A",
                                    activeforeground="#FFFFFF",
                                    relief="flat", padx=10, pady=8,
                                    cursor="hand2", font=("sans-serif", 10, "bold"))
        self._btn_salva.grid(row=14, column=0, sticky="ew", padx=10, pady=(8, 12))

        # --- Canvas anteprima ---
        self._canvas = tk.Canvas(self, bg=self.PREVIEW_BG,
                                 cursor="crosshair", highlightthickness=0)
        self._canvas.grid(row=0, column=1, sticky="nsew", padx=(4, 8), pady=8)

        self._canvas.bind("<Button-1>", self._on_canvas_click)
        self._canvas.bind("<B1-Motion>", self._on_canvas_drag)
        self._canvas.bind("<ButtonRelease-1>", self._on_canvas_release)

        # Placeholder testo al centro
        self._id_placeholder = self._canvas.create_text(
            0, 0, text="Carica un'immagine per iniziare",
            fill=self._colore("attenuato"), font=("sans-serif", 13), anchor="center", tags="placeholder")
        self._canvas.bind("<Configure>", self._on_canvas_resize)

    # ------------------------------------------------------------------
    # Helpers colore
    # ------------------------------------------------------------------

    def _colore(self, nome):
        """Recupera il colore dal dizionario dell'app."""
        return self._app.COLORI.get(nome, "#000000")

    # ------------------------------------------------------------------
    # Caricamento immagine
    # ------------------------------------------------------------------

    def _carica_immagine(self):
        path = filedialog.askopenfilename(
            title="Apri immagine sketch",
            filetypes=[("Immagini", "*.jpg *.jpeg *.png *.webp *.tiff *.tif *.bmp"),
                       ("Tutti i file", "*.*")])
        if not path:
            return

        img = cv2.imread(path)
        if img is None:
            self._app.imposta_stato(f"Impossibile aprire: {path}", "errore")
            return

        self._path_orig = path
        self._img_orig = img
        self._angoli = []
        self._drag_idx = None

        h, w = img.shape[:2]
        scala = min(self.MAX_PREVIEW / max(w, h), 1.0)
        self._scala = scala
        nw, nh = int(w * scala), int(h * scala)
        self._img_preview = cv2.resize(img, (nw, nh), interpolation=cv2.INTER_AREA)

        self._mostra_immagine(self._img_preview)
        self._btn_salva.config(state="disabled")
        self._aggiorna_etichetta_angoli()
        self._app.imposta_stato(f"Caricata: {os.path.basename(path)} ({w}×{h} px)")

    # ------------------------------------------------------------------
    # Visualizzazione
    # ------------------------------------------------------------------

    def _array_a_tkimg(self, arr):
        """Converte array BGR numpy in PhotoImage."""
        rgb = cv2.cvtColor(arr, cv2.COLOR_BGR2RGB)
        pil = Image.fromarray(rgb)
        return ImageTk.PhotoImage(pil)

    def _mostra_immagine(self, arr):
        """Visualizza arr sul canvas, centrato."""
        self._canvas.delete("immagine")
        self._canvas.delete("overlay")
        self._canvas.delete("placeholder")

        tk_img = self._array_a_tkimg(arr)
        self._tk_img = tk_img  # mantieni il riferimento

        cw = self._canvas.winfo_width() or 600
        ch = self._canvas.winfo_height() or 600
        x0 = (cw - arr.shape[1]) // 2
        y0 = (ch - arr.shape[0]) // 2
        self._img_x0 = x0
        self._img_y0 = y0

        self._canvas.create_image(x0, y0, anchor="nw", image=tk_img, tags="immagine")
        self._disegna_overlay()

    def _on_canvas_resize(self, event):
        """Ricentra placeholder o immagine al ridimensionamento."""
        if self._img_orig is None:
            cx, cy = event.width // 2, event.height // 2
            self._canvas.coords(self._id_placeholder, cx, cy)
        else:
            # Ridisegna immagine corrente (ricentra)
            if hasattr(self, "_ultima_arr") and self._ultima_arr is not None:
                self._mostra_immagine(self._ultima_arr)

    # ------------------------------------------------------------------
    # Click / drag angoli
    # ------------------------------------------------------------------

    def _canvas_to_preview(self, cx, cy):
        """Coordinate canvas → coordinate preview."""
        x0 = getattr(self, "_img_x0", 0)
        y0 = getattr(self, "_img_y0", 0)
        return cx - x0, cy - y0

    def _punto_vicino(self, px, py):
        """Ritorna l'indice del punto angolo più vicino a (px,py) se < soglia."""
        best_idx = None
        best_dist = self.DRAG_SOGLIA
        for i, (ax, ay) in enumerate(self._angoli):
            d = ((ax - px) ** 2 + (ay - py) ** 2) ** 0.5
            if d < best_dist:
                best_dist = d
                best_idx = i
        return best_idx

    def _on_canvas_click(self, event):
        if self._img_orig is None:
            return

        px, py = self._canvas_to_preview(event.x, event.y)

        # Verifica se siamo vicini a un punto esistente → avvia drag
        idx = _punto_vicino = self._punto_vicino(px, py)
        if idx is not None:
            self._drag_idx = idx
            return

        # Aggiungi nuovo punto
        if len(self._angoli) >= 4:
            return

        # Clamp alle dimensioni dell'immagine
        if self._img_preview is not None:
            ph, pw = self._img_preview.shape[:2]
            px = max(0, min(px, pw - 1))
            py = max(0, min(py, ph - 1))

        self._angoli.append((px, py))
        self._aggiorna_etichetta_angoli()

        if len(self._angoli) == 4:
            self._riordina_angoli()
            self._btn_salva.config(state="normal")
            self._avvia_ricalcolo()
        else:
            self._disegna_overlay_su_originale()

    def _on_canvas_drag(self, event):
        if self._drag_idx is None:
            return
        px, py = self._canvas_to_preview(event.x, event.y)
        if self._img_preview is not None:
            ph, pw = self._img_preview.shape[:2]
            px = max(0, min(px, pw - 1))
            py = max(0, min(py, ph - 1))
        self._drag_ultimo = (px, py)
        # Aggiorna solo il marker visivamente (non ricalcola)
        self._angoli[self._drag_idx] = (px, py)
        self._disegna_overlay_su_originale()

    def _on_canvas_release(self, event):
        if self._drag_idx is None:
            return
        px, py = self._canvas_to_preview(event.x, event.y)
        if self._img_preview is not None:
            ph, pw = self._img_preview.shape[:2]
            px = max(0, min(px, pw - 1))
            py = max(0, min(py, ph - 1))
        self._angoli[self._drag_idx] = (px, py)
        self._drag_idx = None
        self._drag_ultimo = None
        if len(self._angoli) == 4:
            self._riordina_angoli()
            self._avvia_ricalcolo()
        else:
            self._disegna_overlay_su_originale()

    def _annulla_ultimo(self):
        if self._angoli:
            self._angoli.pop()
            self._aggiorna_etichetta_angoli()
            self._btn_salva.config(state="disabled")
            self._disegna_overlay_su_originale()

    def _azzera_angoli(self):
        self._angoli = []
        self._aggiorna_etichetta_angoli()
        self._btn_salva.config(state="disabled")
        if self._img_preview is not None:
            self._mostra_immagine(self._img_preview)
            self._ultima_arr = self._img_preview

    def _aggiorna_etichetta_angoli(self):
        n = len(self._angoli)
        if n == 0:
            self._lbl_angoli.config(text="Clicca 4 angoli sull'anteprima")
        elif n < 4:
            self._lbl_angoli.config(text=f"{n}/4 angoli selezionati")
        else:
            self._lbl_angoli.config(text="4 angoli selezionati ✓")

    # ------------------------------------------------------------------
    # Riordino geometrico
    # ------------------------------------------------------------------

    def _riordina_angoli(self):
        """TL: sum min, BR: sum max, TR: diff(y-x) min, BL: diff(y-x) max."""
        pts = np.array(self._angoli, dtype=float)
        s = pts.sum(axis=1)
        d = (pts[:, 1] - pts[:, 0])
        tl = pts[np.argmin(s)]
        br = pts[np.argmax(s)]
        tr = pts[np.argmin(d)]
        bl = pts[np.argmax(d)]
        self._angoli = [tuple(tl), tuple(tr), tuple(br), tuple(bl)]

    # ------------------------------------------------------------------
    # Overlay
    # ------------------------------------------------------------------

    def _disegna_overlay_su_originale(self):
        """Mostra l'immagine originale (preview) con overlay angoli."""
        if self._img_preview is not None:
            self._ultima_arr = self._img_preview
            self._mostra_immagine(self._img_preview)

    def _disegna_overlay(self):
        """Disegna cerchietti, quadrilatero ed etichette sul canvas."""
        self._canvas.delete("overlay")

        if not self._angoli:
            return

        x0 = getattr(self, "_img_x0", 0)
        y0 = getattr(self, "_img_y0", 0)
        r = self.MARKER_RAGGIO
        accento = self._colore("accento")
        etichette = self._etichette_angoli if len(self._angoli) == 4 else [str(i + 1) for i in range(len(self._angoli))]

        # Quadrilatero
        if len(self._angoli) >= 2:
            pts_canvas = [(x0 + ax, y0 + ay) for ax, ay in self._angoli]
            if len(self._angoli) == 4:
                self._canvas.create_polygon(pts_canvas, outline=accento,
                                            fill="", width=1.5, tags="overlay")
            else:
                for i in range(len(pts_canvas) - 1):
                    self._canvas.create_line(pts_canvas[i], pts_canvas[i + 1],
                                             fill=accento, width=1.5, tags="overlay")

        # Marcatori
        for i, (ax, ay) in enumerate(self._angoli):
            cx = x0 + ax
            cy = y0 + ay
            # Cerchio
            self._canvas.create_oval(cx - r, cy - r, cx + r, cy + r,
                                     outline=accento, fill="", width=2, tags="overlay")
            # Crocetta
            self._canvas.create_line(cx - r, cy, cx + r, cy,
                                     fill=accento, width=1.5, tags="overlay")
            self._canvas.create_line(cx, cy - r, cx, cy + r,
                                     fill=accento, width=1.5, tags="overlay")
            # Etichetta
            lbl = etichette[i] if i < len(etichette) else str(i + 1)
            self._canvas.create_text(cx + r + 4, cy - r - 2,
                                     text=lbl, fill=accento,
                                     font=("sans-serif", 9, "bold"),
                                     anchor="sw", tags="overlay")

    # ------------------------------------------------------------------
    # Ricalcolo anteprima (con debounce 120 ms)
    # ------------------------------------------------------------------

    def _on_slider_change(self, _val=None):
        wb_val = self._forza_wb.get()
        clip_val = self._clip.get()
        self._lbl_wb_val.config(text=f"{wb_val:.2f}")
        self._lbl_clip_val.config(text=f"{clip_val:.1f}")

        if len(self._angoli) == 4:
            self._avvia_ricalcolo()

    def _avvia_ricalcolo(self):
        """Debounce 120 ms poi ricalcola in thread."""
        if self._timer_ricalcolo is not None:
            self.after_cancel(self._timer_ricalcolo)
        self._timer_ricalcolo = self.after(120, self._ricalcola_anteprima_thread)

    def _ricalcola_anteprima_thread(self):
        if self._img_preview is None or len(self._angoli) != 4:
            return

        angoli = list(self._angoli)
        img = self._img_preview.copy()
        clip = self._clip.get()
        forza_wb = self._forza_wb.get()

        def lavora():
            try:
                result = normalizza_array(img, angoli, clip=clip, forza_wb=forza_wb)
                self.after(0, lambda: self._aggiorna_canvas_preview(result))
            except Exception as e:
                _log.exception("Errore nel ricalcolo anteprima")
                msg = str(e)
                self.after(0, lambda: self._app.imposta_stato(f"Errore anteprima: {msg}", "errore"))

        threading.Thread(target=lavora, daemon=True).start()

    def _aggiorna_canvas_preview(self, arr):
        self._ultima_arr = arr
        self._mostra_immagine(arr)

    # ------------------------------------------------------------------
    # Ripristina parametri
    # ------------------------------------------------------------------

    def _ripristina_default(self):
        self._forza_wb.set(self.FORZA_WB_DEFAULT)
        self._clip.set(self.CLIP_DEFAULT)
        self._lbl_wb_val.config(text=f"{self.FORZA_WB_DEFAULT:.2f}")
        self._lbl_clip_val.config(text=f"{self.CLIP_DEFAULT:.1f}")
        if len(self._angoli) == 4:
            self._avvia_ricalcolo()

    # ------------------------------------------------------------------
    # Salvataggio
    # ------------------------------------------------------------------

    def _salva(self):
        if self._img_orig is None or len(self._angoli) != 4:
            return

        # Proponi nome
        dir_orig = os.path.dirname(self._path_orig)
        base = os.path.splitext(os.path.basename(self._path_orig))[0]
        nome_proposto = f"{base}_normalizzato.png"

        path_out = filedialog.asksaveasfilename(
            title="Salva PNG normalizzato",
            initialdir=dir_orig,
            initialfile=nome_proposto,
            defaultextension=".png",
            filetypes=[("PNG", "*.png"), ("Tutti i file", "*.*")])
        if not path_out:
            return

        angoli_orig = [(ax / self._scala, ay / self._scala) for ax, ay in self._angoli]
        clip = self._clip.get()
        forza_wb = self._forza_wb.get()
        img = self._img_orig.copy()

        self._app.imposta_stato("Elaborazione in corso...", "info")
        self._btn_salva.config(state="disabled")

        def lavora():
            try:
                result = normalizza_array(img, angoli_orig, clip=clip, forza_wb=forza_wb)
                cv2.imwrite(path_out, result, [cv2.IMWRITE_PNG_COMPRESSION, 3])
                h, w = result.shape[:2]
                self.after(0, lambda: self._fine_salvataggio(path_out, w, h))
            except Exception as e:
                _log.exception("Errore nel salvataggio")
                msg = str(e)
                self.after(0, lambda: self._app.imposta_stato(f"Errore: {msg}", "errore"))
                self.after(0, lambda: self._btn_salva.config(state="normal"))

        threading.Thread(target=lavora, daemon=True).start()

    def _fine_salvataggio(self, path_out, w, h):
        self._btn_salva.config(state="normal")
        self._app.imposta_stato(f"Salvato: {path_out} ({w}×{h} px)")
