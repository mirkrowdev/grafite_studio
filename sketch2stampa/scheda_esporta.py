"""
Scheda Esporta — interfaccia per la fase 4 (export per scenario di stampa).
"""
import tkinter as tk
from tkinter import ttk, filedialog
import threading
import logging
import os
from datetime import date
from PIL import Image, ImageTk

_log = logging.getLogger("grafite.esporta")


def _fmt_cm(v):
    """20.0 → '20', 29.7 → '29.7'"""
    return str(int(v)) if v == int(v) else str(round(v, 10)).rstrip("0").rstrip(".")


class SchedaEsporta(ttk.Frame):

    def __init__(self, parent, app, **kwargs):
        super().__init__(parent, **kwargs)
        self._app = app
        self._path_in = None
        self._img_info = None   # (width, height) dell'immagine caricata
        self._pil_sorgente = None  # immagine PIL sorgente originale
        self._scenario_var = tk.StringVar()
        self._tk_img = None       # riferimento PhotoImage (evita GC)
        self._pil_preview = None  # immagine PIL corrente per il canvas
        self._aggiornamento_in_corso = False  # flag anti-ricorsione
        # Zoom e pan
        self._zoom = 1.0
        self._pan_x = 0.0
        self._pan_y = 0.0
        self._pan_start = None

        # Variabili editabili per i parametri di export
        self._var_dpi = tk.StringVar()
        self._var_larg_cm = tk.StringVar()
        self._var_alt_cm = tk.StringVar()
        self._var_profilo = tk.StringVar()
        self._var_adatta = tk.StringVar()
        self._var_bordo_cm = tk.StringVar()

        self._crea_layout()

    # ------------------------------------------------------------------
    # Helpers colore
    # ------------------------------------------------------------------

    def _colore(self, nome):
        return self._app.COLORI.get(nome, "#000000")

    # ------------------------------------------------------------------
    # Layout
    # ------------------------------------------------------------------

    def _crea_layout(self):
        from export_stampa import SCENARI, cm_to_px
        self._SCENARI = SCENARI
        self._cm_to_px = cm_to_px

        scenari = list(SCENARI.keys())
        self._scenario_var.set(scenari[0])
        self._scenario_var.trace_add("write", self._aggiorna_dettagli)

        self.columnconfigure(0, weight=0, minsize=340)
        self.columnconfigure(1, weight=1)
        self.rowconfigure(0, weight=1)

        # --- Pannello sinistro ---
        pannello = tk.Frame(self, bg=self._colore("contenitore"))
        pannello.grid(row=0, column=0, sticky="nsew", padx=(8, 4), pady=8)
        pannello.columnconfigure(0, weight=1)

        row = 0

        # 1. Carica immagine
        tk.Label(pannello, text="IMMAGINE SORGENTE",
                 bg=self._colore("contenitore"), fg=self._colore("testo_sec"),
                 font=("sans-serif", 8)).grid(row=row, column=0, sticky="w", padx=10, pady=(12, 2))
        row += 1

        tk.Button(pannello, text="Carica immagine...", command=self._carica_immagine,
                  bg=self._colore("contenitore"), fg=self._colore("testo"),
                  activebackground=self._colore("bordo"), activeforeground=self._colore("testo"),
                  relief="flat", padx=10, pady=6, cursor="hand2").grid(
            row=row, column=0, sticky="ew", padx=10, pady=(0, 4))
        row += 1

        self._lbl_img = tk.Label(pannello, text="Nessuna immagine caricata",
                                 bg=self._colore("contenitore"),
                                 fg=self._colore("attenuato"),
                                 wraplength=300, justify="left", anchor="w")
        self._lbl_img.grid(row=row, column=0, sticky="w", padx=10, pady=(0, 10))
        row += 1

        ttk.Separator(pannello, orient="horizontal").grid(
            row=row, column=0, sticky="ew", padx=10, pady=4)
        row += 1

        # 2. Tendina scenari
        tk.Label(pannello, text="SCENARIO DI STAMPA",
                 bg=self._colore("contenitore"), fg=self._colore("testo_sec"),
                 font=("sans-serif", 8)).grid(row=row, column=0, sticky="w", padx=10, pady=(8, 2))
        row += 1

        self._combo = ttk.Combobox(pannello, textvariable=self._scenario_var,
                                   values=scenari, state="readonly")
        self._combo.grid(row=row, column=0, sticky="ew", padx=10, pady=(0, 10))
        row += 1

        ttk.Separator(pannello, orient="horizontal").grid(
            row=row, column=0, sticky="ew", padx=10, pady=4)
        row += 1

        # 3. Riquadro dettagli scenario (editabili)
        tk.Label(pannello, text="PARAMETRI EXPORT",
                 bg=self._colore("contenitore"), fg=self._colore("testo_sec"),
                 font=("sans-serif", 8)).grid(row=row, column=0, sticky="w", padx=10, pady=(8, 2))
        row += 1

        self._fr_dettagli = tk.Frame(pannello, bg=self._colore("superficie"),
                                     bd=1, relief="flat",
                                     highlightbackground=self._colore("bordo_tenue"),
                                     highlightthickness=1)
        self._fr_dettagli.grid(row=row, column=0, sticky="ew", padx=10, pady=(0, 6))
        self._fr_dettagli.columnconfigure(0, weight=0)
        self._fr_dettagli.columnconfigure(1, weight=1)

        r = 0
        lbl_kw = dict(bg=self._colore("superficie"), fg=self._colore("testo_sec"),
                       anchor="w", padx=8, pady=3)
        entry_kw = dict(bg=self._colore("contenitore"), fg=self._colore("testo"),
                        insertbackground=self._colore("testo"),
                        relief="flat", bd=2, width=10)

        # Larghezza cm
        tk.Label(self._fr_dettagli, text="Larghezza (cm):", **lbl_kw).grid(row=r, column=0, sticky="w")
        e_larg = tk.Entry(self._fr_dettagli, textvariable=self._var_larg_cm, **entry_kw)
        e_larg.grid(row=r, column=1, sticky="ew", padx=(4, 8), pady=2)
        r += 1

        # Altezza cm
        tk.Label(self._fr_dettagli, text="Altezza (cm):", **lbl_kw).grid(row=r, column=0, sticky="w")
        e_alt = tk.Entry(self._fr_dettagli, textvariable=self._var_alt_cm, **entry_kw)
        e_alt.grid(row=r, column=1, sticky="ew", padx=(4, 8), pady=2)
        r += 1

        # DPI
        tk.Label(self._fr_dettagli, text="DPI:", **lbl_kw).grid(row=r, column=0, sticky="w")
        e_dpi = tk.Entry(self._fr_dettagli, textvariable=self._var_dpi, **entry_kw)
        e_dpi.grid(row=r, column=1, sticky="ew", padx=(4, 8), pady=2)
        r += 1

        # Profilo colore
        tk.Label(self._fr_dettagli, text="Profilo colore:", **lbl_kw).grid(row=r, column=0, sticky="w")
        combo_profilo = ttk.Combobox(self._fr_dettagli, textvariable=self._var_profilo,
                                      values=["sRGB", "AdobeRGB"], state="readonly", width=10)
        combo_profilo.grid(row=r, column=1, sticky="ew", padx=(4, 8), pady=2)
        r += 1

        # Adattamento
        tk.Label(self._fr_dettagli, text="Adattamento:", **lbl_kw).grid(row=r, column=0, sticky="w")
        combo_adatta = ttk.Combobox(self._fr_dettagli, textvariable=self._var_adatta,
                                     values=["contieni", "copri"], state="readonly", width=10)
        combo_adatta.grid(row=r, column=1, sticky="ew", padx=(4, 8), pady=2)
        r += 1

        # Bordo avvolgimento
        tk.Label(self._fr_dettagli, text="Bordo avvolg. (cm):", **lbl_kw).grid(row=r, column=0, sticky="w")
        e_bordo = tk.Entry(self._fr_dettagli, textvariable=self._var_bordo_cm, **entry_kw)
        e_bordo.grid(row=r, column=1, sticky="ew", padx=(4, 8), pady=2)
        r += 1

        # Pixel finali (label calcolata, non editabile)
        tk.Label(self._fr_dettagli, text="Pixel finali:", **lbl_kw).grid(row=r, column=0, sticky="w")
        self._lbl_pixel = tk.Label(self._fr_dettagli, text="—",
                                    bg=self._colore("superficie"),
                                    fg=self._colore("primario"),
                                    anchor="w", padx=4, pady=3)
        self._lbl_pixel.grid(row=r, column=1, sticky="w")
        r += 1

        # Trace per aggiornamento live
        for var in (self._var_dpi, self._var_larg_cm, self._var_alt_cm,
                    self._var_profilo, self._var_adatta, self._var_bordo_cm):
            var.trace_add("write", self._on_parametro_cambiato)

        row += 1

        # Avviso ingrandimento (nascosto di default)
        self._fr_avviso = tk.Frame(pannello, bg="#2A1B10",
                                   bd=1, relief="flat",
                                   highlightbackground="#7C3A0E",
                                   highlightthickness=1)
        self._lbl_avviso = tk.Label(self._fr_avviso, text="",
                                    bg="#2A1B10", fg="#F2B48A",
                                    wraplength=290, justify="left", padx=8, pady=6)
        self._lbl_avviso.pack(fill="x")
        self._avviso_row = row
        row += 1

        ttk.Separator(pannello, orient="horizontal").grid(
            row=row, column=0, sticky="ew", padx=10, pady=4)
        row += 1

        # 4. Pulsante Esporta
        self._btn_esporta = tk.Button(pannello, text="Esporta TIFF...",
                                      command=self._esporta,
                                      bg=self._colore("accento"), fg="#FFFFFF",
                                      activebackground="#C04A0A",
                                      activeforeground="#FFFFFF",
                                      relief="flat", padx=10, pady=8,
                                      cursor="hand2",
                                      font=("sans-serif", 10, "bold"))
        self._btn_esporta.grid(row=row, column=0, sticky="ew", padx=10, pady=(8, 12))

        # --- Pannello destro: anteprima ---
        self._canvas = tk.Canvas(self, bg=self._colore("sfondo_app"),
                                 highlightthickness=0)
        self._canvas.grid(row=0, column=1, sticky="nsew", padx=(4, 8), pady=8)
        self._canvas.bind("<Configure>", self._on_canvas_resize)

        # Zoom con rotellina
        self._canvas.bind("<MouseWheel>", self._on_mousewheel)           # Windows/macOS
        self._canvas.bind("<Button-4>", self._on_mousewheel_linux_up)    # Linux scroll up
        self._canvas.bind("<Button-5>", self._on_mousewheel_linux_down)  # Linux scroll down

        # Pan con rotellina (click centrale)
        self._canvas.bind("<Button-2>", self._on_pan_start)
        self._canvas.bind("<B2-Motion>", self._on_pan_move)
        self._canvas.bind("<ButtonRelease-2>", self._on_pan_end)

        # Doppio clic centrale: reset zoom
        self._canvas.bind("<Double-Button-2>", self._on_zoom_reset)

        self._lbl_placeholder = tk.Label(
            self._canvas, text="Carica un'immagine\nper vedere l'anteprima",
            bg=self._colore("sfondo_app"), fg=self._colore("attenuato"),
            justify="center")
        self._canvas.create_window(0, 0, anchor="nw", window=self._lbl_placeholder,
                                   tags="placeholder")

        # Popola subito i dettagli con lo scenario di default
        self._aggiorna_dettagli()

    # ------------------------------------------------------------------
    # Anteprima
    # ------------------------------------------------------------------

    def _mostra_anteprima(self, pil_img):
        """Visualizza pil_img nel canvas con zoom e pan."""
        cw = self._canvas.winfo_width()
        ch = self._canvas.winfo_height()
        if cw < 10 or ch < 10:
            self.after(50, lambda: self._mostra_anteprima(pil_img))
            return

        self._canvas.itemconfigure("placeholder", state="hidden")

        iw, ih = pil_img.size
        # Scala base per fit + zoom
        self._scala_base = min(cw / iw, ch / ih, 1.0)
        scala = self._scala_base * self._zoom
        nw, nh = max(1, int(iw * scala)), max(1, int(ih * scala))
        resample = Image.LANCZOS if nw < 4000 and nh < 4000 else Image.NEAREST
        img_rid = pil_img.resize((nw, nh), resample)

        self._tk_img = ImageTk.PhotoImage(img_rid)
        self._canvas.delete("preview")
        x = cw / 2 + self._pan_x
        y = ch / 2 + self._pan_y
        self._canvas.create_image(int(x), int(y), anchor="center",
                                  image=self._tk_img, tags="preview")

    def _on_canvas_resize(self, event):
        """Ridisegna l'anteprima quando il canvas cambia dimensione."""
        if self._pil_preview is not None:
            self._mostra_anteprima(self._pil_preview)
        else:
            self._canvas.coords("placeholder", event.width // 2, event.height // 2)
            self._canvas.itemconfigure("placeholder", anchor="center", state="normal")

    # ------------------------------------------------------------------
    # Zoom e Pan
    # ------------------------------------------------------------------

    def _applica_zoom(self, fattore, cx, cy):
        if self._pil_preview is None:
            return
        cw = self._canvas.winfo_width()
        ch = self._canvas.winfo_height()

        vecchio = self._zoom
        nuovo = max(0.2, min(vecchio * fattore, 10.0))
        if nuovo == vecchio:
            return

        # Aggiusta pan per mantenere il punto sotto il cursore fisso
        centro_x = cw / 2 + self._pan_x
        centro_y = ch / 2 + self._pan_y
        self._pan_x += (cx - centro_x) * (1 - nuovo / vecchio)
        self._pan_y += (cy - centro_y) * (1 - nuovo / vecchio)
        self._zoom = nuovo

        self._mostra_anteprima(self._pil_preview)
        pct = int(self._zoom * 100)
        self._app.imposta_stato(f"Zoom: {pct}%  (doppio clic rotellina per resettare)")

    def _on_mousewheel(self, event):
        fattore = 1.15 if event.delta > 0 else 1.0 / 1.15
        self._applica_zoom(fattore, event.x, event.y)

    def _on_mousewheel_linux_up(self, event):
        self._applica_zoom(1.15, event.x, event.y)

    def _on_mousewheel_linux_down(self, event):
        self._applica_zoom(1.0 / 1.15, event.x, event.y)

    def _on_pan_start(self, event):
        self._pan_start = (event.x, event.y)

    def _on_pan_move(self, event):
        if self._pan_start is None or self._pil_preview is None:
            return
        dx = event.x - self._pan_start[0]
        dy = event.y - self._pan_start[1]
        self._pan_start = (event.x, event.y)
        self._pan_x += dx
        self._pan_y += dy
        self._mostra_anteprima(self._pil_preview)

    def _on_pan_end(self, event):
        self._pan_start = None

    def _on_zoom_reset(self, event):
        self._zoom = 1.0
        self._pan_x = 0.0
        self._pan_y = 0.0
        if self._pil_preview is not None:
            self._mostra_anteprima(self._pil_preview)
        self._app.imposta_stato("Zoom resettato")

    # ------------------------------------------------------------------
    # Caricamento
    # ------------------------------------------------------------------

    def _carica_immagine(self):
        path = filedialog.askopenfilename(
            title="Apri immagine da esportare",
            filetypes=[("Immagini", "*.jpg *.jpeg *.png *.webp *.tiff *.tif *.bmp"),
                       ("Tutti i file", "*.*")])
        if not path:
            return

        try:
            img = Image.open(path).convert("RGB")
            self._img_info = img.size  # (width, height)
        except Exception as e:
            _log.exception("Impossibile aprire l'immagine sorgente")
            self._app.imposta_stato(f"Impossibile aprire: {e}", "errore")
            return

        self._path_in = path
        self._pil_sorgente = img
        self._pil_preview = img
        self._zoom = 1.0
        self._pan_x = 0.0
        self._pan_y = 0.0
        nome = os.path.basename(path)
        w, h = self._img_info
        self._lbl_img.config(text=f"{nome}\n{w}×{h} px", fg=self._colore("testo"))
        self._app.imposta_stato(f"Caricata: {nome} ({w}×{h} px)")
        self._on_parametro_cambiato()  # genera preview risultato

    # ------------------------------------------------------------------
    # Lettura parametri correnti
    # ------------------------------------------------------------------

    def _leggi_parametri(self):
        """Legge i parametri correnti dai widget editabili. Ritorna None se invalidi."""
        try:
            dpi = int(self._var_dpi.get())
            larg = float(self._var_larg_cm.get())
            alt = float(self._var_alt_cm.get())
            profilo = self._var_profilo.get()
            adatta = self._var_adatta.get()
            bordo_str = self._var_bordo_cm.get().strip()
            bordo = float(bordo_str) if bordo_str else 0
            if dpi <= 0 or larg <= 0 or alt <= 0 or bordo < 0:
                return None
            return {
                "cm": (larg, alt),
                "dpi": dpi,
                "profilo": profilo,
                "adatta": adatta,
                "bordo_cm": bordo,
                "sfondo": (255, 255, 255),
            }
        except (ValueError, TypeError):
            return None

    # ------------------------------------------------------------------
    # Riquadro dettagli
    # ------------------------------------------------------------------

    def _aggiorna_dettagli(self, *_):
        """Popola i campi editabili dallo scenario selezionato."""
        self._aggiornamento_in_corso = True
        scenario = self._scenario_var.get()
        cfg = self._SCENARI.get(scenario, {})

        cm_l, cm_h = cfg.get("cm", (20, 30))
        self._var_larg_cm.set(_fmt_cm(cm_l))
        self._var_alt_cm.set(_fmt_cm(cm_h))
        self._var_dpi.set(str(cfg.get("dpi", 300)))
        self._var_profilo.set(cfg.get("profilo", "sRGB"))
        self._var_adatta.set(cfg.get("adatta", "contieni"))
        bordo = cfg.get("bordo_cm", 0)
        self._var_bordo_cm.set(str(bordo) if bordo else "0")

        self._aggiornamento_in_corso = False
        self._on_parametro_cambiato()

    def _on_parametro_cambiato(self, *_):
        """Callback: un parametro editabile è cambiato → aggiorna pixel e preview."""
        if self._aggiornamento_in_corso:
            return

        params = self._leggi_parametri()
        if params is None:
            self._lbl_pixel.config(text="(valori non validi)")
            return

        cm_l, cm_h = params["cm"]
        bordo = params["bordo_cm"]
        cm_l_tot = cm_l + bordo * 2
        cm_h_tot = cm_h + bordo * 2
        dpi = params["dpi"]
        adatta = params["adatta"]

        W = self._cm_to_px(cm_l_tot, dpi)
        H = self._cm_to_px(cm_h_tot, dpi)
        self._lbl_pixel.config(text=f"{W} × {H} px")

        # Avviso ingrandimento
        self._fr_avviso.grid_forget()
        if self._img_info and W and H:
            iw, ih = self._img_info
            if adatta == "contieni":
                fattore = min(W / iw, H / ih)
            else:
                fattore = max(W / iw, H / ih)
            if fattore > 1.0:
                self._lbl_avviso.config(
                    text=f"L'immagine verrà ingrandita di {fattore:.1f}× "
                         f"— qualità non garantita in stampa.")
                self._fr_avviso.grid(in_=self._fr_dettagli.master,
                                     row=self._avviso_row,
                                     column=0, sticky="ew", padx=10, pady=(2, 4))

        # Aggiorna preview risultato
        self._aggiorna_preview_risultato()

    def _aggiorna_preview_risultato(self):
        """Genera e mostra nel canvas una preview del risultato con i parametri correnti."""
        if self._pil_sorgente is None:
            return

        params = self._leggi_parametri()
        if params is None:
            return

        cm_l, cm_h = params["cm"]
        bordo = params["bordo_cm"]
        cm_l_tot = cm_l + bordo * 2
        cm_h_tot = cm_h + bordo * 2
        dpi = params["dpi"]
        adatta = params["adatta"]

        W = self._cm_to_px(cm_l_tot, dpi)
        H = self._cm_to_px(cm_h_tot, dpi)

        img = self._pil_sorgente.copy()
        iw, ih = img.size

        if adatta == "contieni":
            scala = min(W / iw, H / ih)
        else:
            scala = max(W / iw, H / ih)
        nuova = (max(1, int(round(iw * scala))), max(1, int(round(ih * scala))))

        # Usa NEAREST per velocità nella preview (immagine potenzialmente grande)
        img = img.resize(nuova, Image.LANCZOS if max(nuova) < 4000 else Image.NEAREST)

        tela = Image.new("RGB", (W, H), params["sfondo"])
        tela.paste(img, ((W - img.width) // 2, (H - img.height) // 2))

        self._pil_preview = tela
        self._mostra_anteprima(tela)

    # ------------------------------------------------------------------
    # Nome proposto
    # ------------------------------------------------------------------

    def _nome_proposto(self, path_in, scenario, params):
        """Schema: {nome}_{scenario}_{L}x{H}_{dpi}dpi_{profilo}_{AAAAMMGG}.tif"""
        base = os.path.splitext(os.path.basename(path_in))[0]
        dpi = params.get("dpi", 300)
        cm_l, cm_h = params.get("cm", (0, 0))
        bordo = params.get("bordo_cm", 0)
        cm_l_tot = cm_l + bordo * 2
        cm_h_tot = cm_h + bordo * 2
        profilo = params.get("profilo", "sRGB")
        today = date.today().strftime("%Y%m%d")

        nome = (f"{base}_{scenario}_"
                f"{_fmt_cm(cm_l_tot)}x{_fmt_cm(cm_h_tot)}_"
                f"{dpi}dpi_{profilo}_{today}.tif")

        dir_out = os.path.dirname(path_in)
        percorso = os.path.join(dir_out, nome)

        # Evita sovrascrittura
        if os.path.exists(percorso):
            n = 2
            while True:
                radice = os.path.splitext(nome)[0]
                nome_n = f"{radice}_{n}.tif"
                percorso_n = os.path.join(dir_out, nome_n)
                if not os.path.exists(percorso_n):
                    percorso = percorso_n
                    break
                n += 1

        return percorso

    # ------------------------------------------------------------------
    # Esportazione
    # ------------------------------------------------------------------

    def _esporta(self):
        if not self._path_in:
            self._app.imposta_stato("Carica prima un'immagine.", "avviso")
            return

        params = self._leggi_parametri()
        if params is None:
            self._app.imposta_stato("Parametri non validi.", "avviso")
            return

        scenario = self._scenario_var.get()
        path_proposto = self._nome_proposto(self._path_in, scenario, params)

        dir_out = os.path.dirname(path_proposto)
        nome_prop = os.path.basename(path_proposto)

        path_out = filedialog.asksaveasfilename(
            title="Salva TIFF",
            initialdir=dir_out,
            initialfile=nome_prop,
            defaultextension=".tif",
            filetypes=[("TIFF", "*.tif *.tiff"), ("Tutti i file", "*.*")])
        if not path_out:
            return

        path_in = self._path_in
        override = params  # parametri editati dall'utente
        self._app.imposta_stato("Esportazione in corso...", "info")
        self._btn_esporta.config(state="disabled")

        def lavora():
            from export_stampa import esporta
            try:
                info = esporta(path_in, path_out, scenario, override=override)
                self.after(0, lambda: self._fine_esportazione(info))
            except Exception as e:
                _log.exception("Errore durante l'esportazione")
                msg = str(e)
                self.after(0, lambda: self._app.imposta_stato(f"Errore esportazione: {msg}", "errore"))
                self.after(0, lambda: self._btn_esporta.config(state="normal"))

        threading.Thread(target=lavora, daemon=True).start()

    # ------------------------------------------------------------------
    # API pubblica: caricamento da percorso (usata dalla scheda ComfyUI)
    # ------------------------------------------------------------------

    def carica_da_percorso(self, path):
        """Carica l'immagine al percorso dato, come se l'utente l'avesse selezionata."""
        try:
            img = Image.open(path).convert("RGB")
            self._img_info = img.size
        except Exception as e:
            _log.exception("Impossibile aprire l'immagine da percorso")
            self._app.imposta_stato(f"Impossibile aprire: {e}", "errore")
            return

        self._path_in = path
        self._pil_sorgente = img
        self._pil_preview = img
        self._zoom = 1.0
        self._pan_x = 0.0
        self._pan_y = 0.0
        nome = os.path.basename(path)
        w, h = self._img_info
        self._lbl_img.config(text=f"{nome}\n{w}\u00d7{h} px", fg=self._colore("testo"))
        self._app.imposta_stato(f"Caricata: {nome} ({w}\u00d7{h} px)")
        self._on_parametro_cambiato()

    def _fine_esportazione(self, info):
        self._btn_esporta.config(state="normal")
        w, h = info["px"]
        self._app.imposta_stato(
            f"Esportato: {info['file']} ({w}×{h} px, {info['dpi']} dpi, {info['profilo']})")
        # Mostra il TIFF esportato nell'anteprima
        try:
            img_risultato = Image.open(info["file"]).convert("RGB")
            self._pil_preview = img_risultato
            self._mostra_anteprima(img_risultato)
        except Exception:
            pass
