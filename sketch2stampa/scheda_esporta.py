"""
Scheda Esporta — interfaccia per la fase 4 (export per scenario di stampa).
"""
import tkinter as tk
from tkinter import ttk, filedialog
import threading
import os
from datetime import date
from PIL import Image, ImageTk


def _fmt_cm(v):
    """20.0 → '20', 29.7 → '29.7'"""
    return str(int(v)) if v == int(v) else str(round(v, 10)).rstrip("0").rstrip(".")


class SchedaEsporta(ttk.Frame):

    def __init__(self, parent, app, **kwargs):
        super().__init__(parent, **kwargs)
        self._app = app
        self._path_in = None
        self._img_info = None   # (width, height) dell'immagine caricata
        self._scenario_var = tk.StringVar()
        self._tk_img = None       # riferimento PhotoImage (evita GC)
        self._pil_preview = None  # immagine PIL corrente per il canvas
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

        # 3. Riquadro dettagli scenario
        tk.Label(pannello, text="DETTAGLI SCENARIO",
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
        # non mostrato per ora

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
        """Visualizza pil_img nel canvas, scalata per adattarsi."""
        cw = self._canvas.winfo_width()
        ch = self._canvas.winfo_height()
        if cw < 10 or ch < 10:
            # Canvas non ancora renderizzato — riprova al prossimo ciclo
            self.after(50, lambda: self._mostra_anteprima(pil_img))
            return

        # Nasconde placeholder
        self._canvas.itemconfigure("placeholder", state="hidden")

        # Scala mantenendo le proporzioni
        iw, ih = pil_img.size
        scala = min(cw / iw, ch / ih, 1.0)
        nw, nh = max(1, int(iw * scala)), max(1, int(ih * scala))
        img_rid = pil_img.resize((nw, nh), Image.LANCZOS)

        self._tk_img = ImageTk.PhotoImage(img_rid)
        self._canvas.delete("preview")
        self._canvas.create_image(cw // 2, ch // 2, anchor="center",
                                  image=self._tk_img, tags="preview")

    def _on_canvas_resize(self, event):
        """Ridisegna l'anteprima quando il canvas cambia dimensione."""
        if self._pil_preview is not None:
            self._mostra_anteprima(self._pil_preview)
        else:
            # Riposiziona il placeholder al centro
            self._canvas.coords("placeholder", event.width // 2, event.height // 2)
            self._canvas.itemconfigure("placeholder", anchor="center", state="normal")

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
            self._app.imposta_stato(f"Impossibile aprire: {e}", "errore")
            return

        self._path_in = path
        self._pil_preview = img
        nome = os.path.basename(path)
        w, h = self._img_info
        self._lbl_img.config(text=f"{nome}\n{w}×{h} px", fg=self._colore("testo"))
        self._app.imposta_stato(f"Caricata: {nome} ({w}×{h} px)")
        self._mostra_anteprima(img)
        self._aggiorna_dettagli()

    # ------------------------------------------------------------------
    # Riquadro dettagli
    # ------------------------------------------------------------------

    def _aggiorna_dettagli(self, *_):
        scenario = self._scenario_var.get()
        cfg = self._SCENARI.get(scenario, {})

        # Pulisci riquadro
        for widget in self._fr_dettagli.winfo_children():
            widget.destroy()

        dpi = cfg.get("dpi", "?")
        cm_l, cm_h = cfg.get("cm", (0, 0))
        bordo = cfg.get("bordo_cm", 0)
        cm_l_tot = cm_l + bordo * 2
        cm_h_tot = cm_h + bordo * 2
        profilo = cfg.get("profilo", "?")
        adatta = cfg.get("adatta", "?")

        adatta_testo = "margine bianco" if adatta == "contieni" else "ritaglia"

        righe = [
            ("Misura", f"{_fmt_cm(cm_l_tot)} × {_fmt_cm(cm_h_tot)} cm"),
            ("DPI", str(dpi)),
            ("Profilo colore", profilo),
            ("Adattamento", adatta_testo),
        ]

        if bordo:
            righe.append(("Bordo avvolgimento", f"{bordo} cm per lato"))

        # Pixel finali
        if dpi != "?":
            W = self._cm_to_px(cm_l_tot, dpi)
            H = self._cm_to_px(cm_h_tot, dpi)
            righe.append(("Pixel finali", f"{W} × {H} px"))
        else:
            W, H = None, None

        for i, (etichetta, valore) in enumerate(righe):
            tk.Label(self._fr_dettagli, text=etichetta + ":",
                     bg=self._colore("superficie"), fg=self._colore("testo_sec"),
                     anchor="w", padx=8, pady=2).grid(
                row=i, column=0, sticky="w")
            is_px = etichetta == "Pixel finali"
            colore_val = self._colore("primario") if is_px else self._colore("testo")
            tk.Label(self._fr_dettagli, text=valore,
                     bg=self._colore("superficie"), fg=colore_val,
                     anchor="w", padx=4, pady=2).grid(
                row=i, column=1, sticky="w")

        # Avviso ingrandimento
        self._fr_avviso.grid_forget()
        if self._img_info and W and H:
            iw, ih = self._img_info
            # Fattore di scala che verrà applicato (stessa logica di esporta())
            if adatta == "contieni":
                fattore = min(W / iw, H / ih)
            else:
                fattore = max(W / iw, H / ih)
            if fattore > 1.0:
                self._lbl_avviso.config(
                    text=f"L'immagine verrà ingrandita di {fattore:.1f}× "
                         f"— qualità non garantita in stampa.")
                self._fr_avviso.grid(in_=self._fr_dettagli.master,
                                     row=self._fr_dettagli.grid_info()["row"] + 1,
                                     column=0, sticky="ew", padx=10, pady=(2, 4))

    # ------------------------------------------------------------------
    # Nome proposto
    # ------------------------------------------------------------------

    def _nome_proposto(self, path_in, scenario, cfg):
        """Schema: {nome}_{scenario}_{L}x{H}_{dpi}dpi_{profilo}_{AAAAMMGG}.tif"""
        base = os.path.splitext(os.path.basename(path_in))[0]
        dpi = cfg.get("dpi", 300)
        cm_l, cm_h = cfg.get("cm", (0, 0))
        bordo = cfg.get("bordo_cm", 0)
        cm_l_tot = cm_l + bordo * 2
        cm_h_tot = cm_h + bordo * 2
        profilo = cfg.get("profilo", "sRGB")
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

        scenario = self._scenario_var.get()
        cfg = self._SCENARI.get(scenario, {})
        path_proposto = self._nome_proposto(self._path_in, scenario, cfg)

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
        self._app.imposta_stato("Esportazione in corso...", "info")
        self._btn_esporta.config(state="disabled")

        def lavora():
            from export_stampa import esporta
            try:
                info = esporta(path_in, path_out, scenario)
                self.after(0, lambda: self._fine_esportazione(info))
            except Exception as e:
                self.after(0, lambda: self._app.imposta_stato(f"Errore esportazione: {e}", "errore"))
                self.after(0, lambda: self._btn_esporta.config(state="normal"))

        threading.Thread(target=lavora, daemon=True).start()

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
