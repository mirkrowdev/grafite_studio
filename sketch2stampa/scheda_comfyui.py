"""
Scheda ComfyUI — gestione server locale + calcolatore di ingrandimento.
"""
import json
import logging
import os
import subprocess
import sys
import threading
import urllib.request
import urllib.error
import webbrowser
from pathlib import Path
from tkinter import ttk, filedialog
import tkinter as tk

from PIL import Image, ImageTk

import preferenze

_log = logging.getLogger("grafite.comfyui")

# Massimo righe nel buffer console
_MAX_RIGHE_CONSOLE = 100


class SchedaComfyUI(ttk.Frame):

    def __init__(self, parent, app, **kwargs):
        super().__init__(parent, **kwargs)
        self._app = app

        # Stato server
        self._stato = "spento"          # "spento" | "in_avvio" | "attivo"
        self._processo = None            # Popen, se avviato da Grafite
        self._avviato_da_grafite = False
        self._avvio_diretto = False      # True se python_embeded, False se .bat
        self._console_righe = []         # buffer circolare stdout/stderr
        self._lock_console = threading.Lock()

        # Preferenze
        pref = preferenze.carica()
        self._percorso_comfyui = pref.get("comfyui_percorso", "")
        self._porta = pref.get("comfyui_porta", 8188)

        self._crea_layout()
        self._aggiorna_stato_ui()

        # Avvia polling stato server
        self._polling_attivo = True
        self._poll_stato()

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

        self.columnconfigure(0, weight=0, minsize=380)
        self.columnconfigure(1, weight=1)
        self.rowconfigure(0, weight=1)

        # --- Pannello sinistro (scroll) ---
        pannello = tk.Frame(self, bg=self._colore("contenitore"))
        pannello.grid(row=0, column=0, sticky="nsew", padx=(8, 4), pady=8)
        pannello.columnconfigure(0, weight=1)

        row = 0

        # ======== STATO SERVER ========
        tk.Label(pannello, text="SERVER COMFYUI",
                 bg=self._colore("contenitore"), fg=self._colore("testo_sec"),
                 font=("sans-serif", 8)).grid(
            row=row, column=0, sticky="w", padx=10, pady=(12, 2))
        row += 1

        self._lbl_stato = tk.Label(pannello, text="",
                                    bg=self._colore("contenitore"),
                                    fg=self._colore("attenuato"),
                                    font=("sans-serif", 10, "bold"),
                                    anchor="w")
        self._lbl_stato.grid(row=row, column=0, sticky="w", padx=10, pady=(0, 6))
        row += 1

        # Bottoni server
        fr_btn = tk.Frame(pannello, bg=self._colore("contenitore"))
        fr_btn.grid(row=row, column=0, sticky="ew", padx=10, pady=(0, 2))
        fr_btn.columnconfigure(0, weight=1)
        fr_btn.columnconfigure(1, weight=1)
        fr_btn.columnconfigure(2, weight=1)

        btn_kw = dict(bg=self._colore("contenitore"), fg=self._colore("testo"),
                      activebackground=self._colore("bordo"),
                      activeforeground=self._colore("testo"),
                      relief="flat", padx=10, pady=6, cursor="hand2")

        self._btn_avvia = tk.Button(fr_btn, text="Avvia", command=self._avvia_server, **btn_kw)
        self._btn_avvia.grid(row=0, column=0, sticky="ew", padx=(0, 2))

        self._btn_ferma = tk.Button(fr_btn, text="Ferma", command=self._ferma_server, **btn_kw)
        self._btn_ferma.grid(row=0, column=1, sticky="ew", padx=2)

        self._btn_browser = tk.Button(fr_btn, text="Apri browser", command=self._apri_browser, **btn_kw)
        self._btn_browser.grid(row=0, column=2, sticky="ew", padx=(2, 0))
        row += 1

        self._lbl_nota_ferma = tk.Label(pannello, text="",
                                         bg=self._colore("contenitore"),
                                         fg=self._colore("attenuato"),
                                         wraplength=340, justify="left",
                                         font=("sans-serif", 7))
        self._lbl_nota_ferma.grid(row=row, column=0, sticky="w", padx=10, pady=(0, 4))
        row += 1

        ttk.Separator(pannello, orient="horizontal").grid(
            row=row, column=0, sticky="ew", padx=10, pady=4)
        row += 1

        # ======== CONFIGURAZIONE ========
        tk.Label(pannello, text="CONFIGURAZIONE",
                 bg=self._colore("contenitore"), fg=self._colore("testo_sec"),
                 font=("sans-serif", 8)).grid(
            row=row, column=0, sticky="w", padx=10, pady=(8, 2))
        row += 1

        # Percorso
        fr_path = tk.Frame(pannello, bg=self._colore("contenitore"))
        fr_path.grid(row=row, column=0, sticky="ew", padx=10, pady=(0, 4))
        fr_path.columnconfigure(0, weight=1)
        fr_path.columnconfigure(1, weight=0)

        self._entry_percorso = tk.Entry(fr_path, bg=self._colore("superficie"),
                                         fg=self._colore("testo"),
                                         insertbackground=self._colore("testo"),
                                         relief="flat", bd=2, state="readonly",
                                         readonlybackground=self._colore("superficie"))
        self._entry_percorso.grid(row=0, column=0, sticky="ew", pady=2)
        if self._percorso_comfyui:
            self._entry_percorso.config(state="normal")
            self._entry_percorso.insert(0, self._percorso_comfyui)
            self._entry_percorso.config(state="readonly")

        tk.Button(fr_path, text="Sfoglia...", command=self._seleziona_percorso,
                  bg=self._colore("contenitore"), fg=self._colore("testo"),
                  activebackground=self._colore("bordo"),
                  activeforeground=self._colore("testo"),
                  relief="flat", padx=8, pady=4, cursor="hand2").grid(
            row=0, column=1, padx=(4, 0), pady=2)
        row += 1

        # Porta
        fr_porta = tk.Frame(pannello, bg=self._colore("contenitore"))
        fr_porta.grid(row=row, column=0, sticky="ew", padx=10, pady=(0, 6))

        tk.Label(fr_porta, text="Porta:",
                 bg=self._colore("contenitore"), fg=self._colore("testo_sec")).pack(
            side="left")

        self._var_porta = tk.StringVar(value=str(self._porta))
        self._var_porta.trace_add("write", self._on_porta_cambiata)
        tk.Entry(fr_porta, textvariable=self._var_porta,
                 bg=self._colore("superficie"), fg=self._colore("testo"),
                 insertbackground=self._colore("testo"),
                 relief="flat", bd=2, width=6).pack(side="left", padx=(6, 0))
        row += 1

        ttk.Separator(pannello, orient="horizontal").grid(
            row=row, column=0, sticky="ew", padx=10, pady=4)
        row += 1

        # ======== CALCOLATORE INGRANDIMENTO ========
        tk.Label(pannello, text="CALCOLATORE INGRANDIMENTO",
                 bg=self._colore("contenitore"), fg=self._colore("testo_sec"),
                 font=("sans-serif", 8)).grid(
            row=row, column=0, sticky="w", padx=10, pady=(8, 2))
        row += 1

        tk.Button(pannello, text="Carica immagine sorgente...",
                  command=self._carica_img_calcolo,
                  bg=self._colore("contenitore"), fg=self._colore("testo"),
                  activebackground=self._colore("bordo"),
                  activeforeground=self._colore("testo"),
                  relief="flat", padx=10, pady=6, cursor="hand2").grid(
            row=row, column=0, sticky="ew", padx=10, pady=(0, 4))
        row += 1

        self._lbl_calc_img = tk.Label(pannello, text="Nessuna immagine",
                                       bg=self._colore("contenitore"),
                                       fg=self._colore("attenuato"),
                                       anchor="w")
        self._lbl_calc_img.grid(row=row, column=0, sticky="w", padx=10, pady=(0, 4))
        row += 1

        # Tendina scenario
        tk.Label(pannello, text="Scenario di stampa:",
                 bg=self._colore("contenitore"), fg=self._colore("testo_sec")).grid(
            row=row, column=0, sticky="w", padx=10, pady=(0, 2))
        row += 1

        scenari = list(self._SCENARI.keys())
        self._calc_scenario_var = tk.StringVar(value=scenari[0])
        self._calc_scenario_var.trace_add("write", self._aggiorna_calcolo)

        self._combo_calc = ttk.Combobox(pannello, textvariable=self._calc_scenario_var,
                                         values=scenari, state="readonly")
        self._combo_calc.grid(row=row, column=0, sticky="ew", padx=10, pady=(0, 6))
        row += 1

        # Riquadro risultato calcolo
        self._fr_calc = tk.Frame(pannello, bg=self._colore("superficie"),
                                  bd=1, relief="flat",
                                  highlightbackground=self._colore("bordo_tenue"),
                                  highlightthickness=1)
        self._fr_calc.grid(row=row, column=0, sticky="ew", padx=10, pady=(0, 6))
        self._fr_calc.columnconfigure(1, weight=1)

        lbl_kw = dict(bg=self._colore("superficie"), fg=self._colore("testo_sec"),
                       anchor="w", padx=8, pady=2)

        r = 0
        tk.Label(self._fr_calc, text="Misura attuale:", **lbl_kw).grid(row=r, column=0, sticky="w")
        self._lbl_px_attuale = tk.Label(self._fr_calc, text="—",
                                         bg=self._colore("superficie"),
                                         fg=self._colore("testo"), anchor="w", padx=4)
        self._lbl_px_attuale.grid(row=r, column=1, sticky="w")
        r += 1

        tk.Label(self._fr_calc, text="Misura richiesta:", **lbl_kw).grid(row=r, column=0, sticky="w")
        self._lbl_px_richiesta = tk.Label(self._fr_calc, text="—",
                                           bg=self._colore("superficie"),
                                           fg=self._colore("testo"), anchor="w", padx=4)
        self._lbl_px_richiesta.grid(row=r, column=1, sticky="w")
        r += 1

        tk.Label(self._fr_calc, text="Fattore:", **lbl_kw).grid(row=r, column=0, sticky="w")
        self._lbl_fattore = tk.Label(self._fr_calc, text="—",
                                      bg=self._colore("superficie"),
                                      fg=self._colore("testo"), anchor="w", padx=4)
        self._lbl_fattore.grid(row=r, column=1, sticky="w")
        r += 1

        self._lbl_verdetto = tk.Label(self._fr_calc, text="",
                                       bg=self._colore("superficie"),
                                       fg=self._colore("testo"),
                                       wraplength=320, justify="left",
                                       padx=8, pady=4)
        self._lbl_verdetto.grid(row=r, column=0, columnspan=2, sticky="ew")

        self._calc_img_size = None  # (w, h)
        row += 1

        ttk.Separator(pannello, orient="horizontal").grid(
            row=row, column=0, sticky="ew", padx=10, pady=4)
        row += 1

        # ======== METADATI PNG ========
        tk.Label(pannello, text="METADATI PNG COMFYUI",
                 bg=self._colore("contenitore"), fg=self._colore("testo_sec"),
                 font=("sans-serif", 8)).grid(
            row=row, column=0, sticky="w", padx=10, pady=(8, 2))
        row += 1

        tk.Button(pannello, text="Carica PNG da ComfyUI...",
                  command=self._carica_png_meta,
                  bg=self._colore("contenitore"), fg=self._colore("testo"),
                  activebackground=self._colore("bordo"),
                  activeforeground=self._colore("testo"),
                  relief="flat", padx=10, pady=6, cursor="hand2").grid(
            row=row, column=0, sticky="ew", padx=10, pady=(0, 4))
        row += 1

        self._lbl_meta_info = tk.Label(pannello, text="Nessun file caricato",
                                        bg=self._colore("contenitore"),
                                        fg=self._colore("attenuato"),
                                        wraplength=340, justify="left", anchor="w")
        self._lbl_meta_info.grid(row=row, column=0, sticky="w", padx=10, pady=(0, 4))
        row += 1

        # Bottone "Passa a Esporta"
        self._btn_passa_esporta = tk.Button(
            pannello, text="Passa a Esporta",
            command=self._passa_a_esporta,
            bg=self._colore("contenitore"), fg=self._colore("testo"),
            activebackground=self._colore("bordo"),
            activeforeground=self._colore("testo"),
            relief="flat", padx=10, pady=6, cursor="hand2",
            state="disabled")
        self._btn_passa_esporta.grid(row=row, column=0, sticky="ew", padx=10, pady=(0, 8))
        self._meta_path = None  # percorso del PNG caricato per i metadati
        row += 1

        # --- Pannello destro: area testo metadati JSON ---
        fr_destra = tk.Frame(self, bg=self._colore("sfondo_app"))
        fr_destra.grid(row=0, column=1, sticky="nsew", padx=(4, 8), pady=8)
        fr_destra.rowconfigure(0, weight=0)
        fr_destra.rowconfigure(1, weight=1)
        fr_destra.columnconfigure(0, weight=1)

        tk.Label(fr_destra, text="METADATI JSON",
                 bg=self._colore("sfondo_app"), fg=self._colore("testo_sec"),
                 font=("sans-serif", 8)).grid(
            row=0, column=0, sticky="w", padx=4, pady=(0, 2))

        fr_testo = tk.Frame(fr_destra, bg=self._colore("superficie"))
        fr_testo.grid(row=1, column=0, sticky="nsew")
        fr_testo.rowconfigure(0, weight=1)
        fr_testo.columnconfigure(0, weight=1)

        self._txt_meta = tk.Text(fr_testo, bg=self._colore("superficie"),
                                  fg=self._colore("testo"),
                                  insertbackground=self._colore("testo"),
                                  relief="flat", wrap="none",
                                  font=("Consolas", 9),
                                  state="disabled")
        self._txt_meta.grid(row=0, column=0, sticky="nsew")

        sb_y = ttk.Scrollbar(fr_testo, orient="vertical", command=self._txt_meta.yview)
        sb_y.grid(row=0, column=1, sticky="ns")
        self._txt_meta.config(yscrollcommand=sb_y.set)

        sb_x = ttk.Scrollbar(fr_testo, orient="horizontal", command=self._txt_meta.xview)
        sb_x.grid(row=1, column=0, sticky="ew")
        self._txt_meta.config(xscrollcommand=sb_x.set)

    # ------------------------------------------------------------------
    # Preferenze
    # ------------------------------------------------------------------

    def _salva_preferenze(self):
        pref = preferenze.carica()
        pref["comfyui_percorso"] = self._percorso_comfyui
        pref["comfyui_porta"] = self._porta
        preferenze.salva(pref)

    def _on_porta_cambiata(self, *_):
        try:
            p = int(self._var_porta.get())
            if 1 <= p <= 65535:
                self._porta = p
                self._salva_preferenze()
        except ValueError:
            pass

    # ------------------------------------------------------------------
    # Selezione percorso ComfyUI
    # ------------------------------------------------------------------

    def _seleziona_percorso(self):
        cartella = filedialog.askdirectory(title="Seleziona la cartella di ComfyUI")
        if not cartella:
            return

        root = Path(cartella)

        # Caso 1: python_embeded + ComfyUI/main.py
        python_exe = root / "python_embeded" / "python.exe"
        main_py = root / "ComfyUI" / "main.py"
        if python_exe.is_file() and main_py.is_file():
            self._percorso_comfyui = str(root)
            self._aggiorna_entry_percorso()
            self._salva_preferenze()
            self._app.imposta_stato(f"Percorso ComfyUI: {root}")
            return

        # Caso 2: .bat di avvio
        bat_noti = ["RUN_Launcher.bat", "run_nvidia_gpu.bat", "run_cpu.bat"]
        for nome in bat_noti:
            if (root / nome).is_file():
                self._percorso_comfyui = str(root)
                self._aggiorna_entry_percorso()
                self._salva_preferenze()
                self._app.imposta_stato(f"Percorso ComfyUI (via {nome}): {root}")
                return

        # Rifiuta
        self._app.imposta_stato(
            "Cartella non valida: cercavo python_embeded\\python.exe + "
            "ComfyUI\\main.py, oppure un file .bat di avvio "
            "(RUN_Launcher.bat, run_nvidia_gpu.bat, run_cpu.bat)",
            "errore")

    def _aggiorna_entry_percorso(self):
        self._entry_percorso.config(state="normal")
        self._entry_percorso.delete(0, "end")
        self._entry_percorso.insert(0, self._percorso_comfyui)
        self._entry_percorso.config(state="readonly")

    # ------------------------------------------------------------------
    # Polling stato server
    # ------------------------------------------------------------------

    def _poll_stato(self):
        if not self._polling_attivo:
            return

        def controlla():
            try:
                url = f"http://127.0.0.1:{self._porta}/system_stats"
                req = urllib.request.Request(url, method="GET")
                with urllib.request.urlopen(req, timeout=2):
                    pass
                nuovo = "attivo"
            except Exception:
                nuovo = "spento"
            self.after(0, lambda: self._on_poll_risultato(nuovo))

        threading.Thread(target=controlla, daemon=True).start()

    def _on_poll_risultato(self, nuovo_stato):
        if not self._polling_attivo:
            return

        # Se eravamo in_avvio, non sovrascrivere con "spento" (il thread di avvio gestisce)
        if self._stato == "in_avvio" and nuovo_stato == "spento":
            pass
        else:
            if self._stato != nuovo_stato:
                # Se diventa attivo senza che lo abbiamo avviato noi
                if nuovo_stato == "attivo" and not self._avviato_da_grafite:
                    self._stato = "attivo"
                else:
                    self._stato = nuovo_stato
                self._aggiorna_stato_ui()

        # Riprogramma
        self.after(3000, self._poll_stato)

    # ------------------------------------------------------------------
    # Aggiornamento UI stato
    # ------------------------------------------------------------------

    def _aggiorna_stato_ui(self):
        testi = {
            "spento": ("Spento", self._colore("attenuato")),
            "in_avvio": ("In avvio...", "#F2B48A"),
            "attivo": ("Attivo", self._colore("primario")),
        }
        testo, colore = testi.get(self._stato, ("?", self._colore("testo")))
        self._lbl_stato.config(text=f"\u25CF  {testo}", fg=colore)

        ha_percorso = bool(self._percorso_comfyui)

        if self._stato == "spento":
            self._btn_avvia.config(state="normal" if ha_percorso else "disabled")
            self._btn_ferma.config(state="disabled")
            self._btn_browser.config(state="disabled")
            self._lbl_nota_ferma.config(text="")
        elif self._stato == "in_avvio":
            self._btn_avvia.config(state="disabled")
            self._btn_ferma.config(state="disabled")
            self._btn_browser.config(state="disabled")
            self._lbl_nota_ferma.config(text="")
        elif self._stato == "attivo":
            self._btn_avvia.config(state="disabled")
            if self._avviato_da_grafite:
                self._btn_ferma.config(state="normal")
                self._lbl_nota_ferma.config(text="")
            else:
                self._btn_ferma.config(state="disabled")
                self._lbl_nota_ferma.config(
                    text="Istanza non avviata da Grafite — il bottone Ferma è disabilitato "
                         "per non chiudere una sessione esterna.")
            self._btn_browser.config(state="normal")

    # ------------------------------------------------------------------
    # Avvio server
    # ------------------------------------------------------------------

    def _avvia_server(self):
        if not self._percorso_comfyui:
            self._app.imposta_stato("Configura prima il percorso di ComfyUI.", "avviso")
            return

        self._stato = "in_avvio"
        self._aggiorna_stato_ui()
        self._app.imposta_stato("Avvio ComfyUI in corso...")

        porta = self._porta
        percorso = self._percorso_comfyui

        def lavora():
            # 1. Controlla se la porta risponde già
            try:
                url = f"http://127.0.0.1:{porta}/system_stats"
                with urllib.request.urlopen(url, timeout=2):
                    pass
                # Già attivo — non avviato da noi
                self.after(0, lambda: self._server_gia_attivo())
                return
            except Exception:
                pass

            # 2. Determina modalità di avvio
            root = Path(percorso)
            python_exe = root / "python_embeded" / "python.exe"
            main_py = root / "ComfyUI" / "main.py"

            cmd = None
            avvio_diretto = False

            if python_exe.is_file() and main_py.is_file():
                cmd = [str(python_exe), "-s", str(main_py), "--port", str(porta)]
                avvio_diretto = True
            else:
                bat_noti = ["RUN_Launcher.bat", "run_nvidia_gpu.bat", "run_cpu.bat"]
                for nome in bat_noti:
                    bat_path = root / nome
                    if bat_path.is_file():
                        cmd = [str(bat_path)]
                        break

            if cmd is None:
                self.after(0, lambda: self._avvio_fallito(
                    "Nessun file di avvio trovato nella cartella configurata."))
                return

            # 3. Avvia il processo
            try:
                kwargs = dict(
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    cwd=str(root),
                )
                if sys.platform == "win32":
                    kwargs["creationflags"] = (
                        subprocess.CREATE_NO_WINDOW | subprocess.CREATE_NEW_PROCESS_GROUP)

                proc = subprocess.Popen(cmd, **kwargs)
            except Exception as e:
                msg = str(e)
                self.after(0, lambda: self._avvio_fallito(f"Errore avvio processo: {msg}"))
                return

            self.after(0, lambda: self._registra_processo(proc, avvio_diretto))

            # 4. Thread lettore stdout
            threading.Thread(target=self._leggi_stdout, args=(proc,), daemon=True).start()

            # 5. Attendi che il server risponda (max 120s)
            import time
            scadenza = time.monotonic() + 120
            while time.monotonic() < scadenza:
                # Se il processo è morto, inutile aspettare
                if proc.poll() is not None:
                    with self._lock_console:
                        ultime = list(self._console_righe)
                    testo = "\n".join(ultime[-20:])
                    self.after(0, lambda t=testo: self._avvio_fallito(
                        f"Il processo è terminato (codice {proc.returncode}).\n\n"
                        f"Ultime righe della console:\n{t}"))
                    return

                try:
                    url = f"http://127.0.0.1:{porta}/system_stats"
                    with urllib.request.urlopen(url, timeout=2):
                        pass
                    # Risponde!
                    self.after(0, self._server_pronto)
                    return
                except Exception:
                    time.sleep(1)

            # Timeout
            with self._lock_console:
                ultime = list(self._console_righe)
            testo = "\n".join(ultime[-20:])
            self.after(0, lambda t=testo: self._avvio_fallito(
                f"Timeout: il server non ha risposto entro 120 secondi.\n\n"
                f"Ultime righe della console:\n{t}"))

        threading.Thread(target=lavora, daemon=True).start()

    def _leggi_stdout(self, proc):
        """Legge stdout/stderr del processo in un buffer circolare."""
        try:
            for riga_bytes in iter(proc.stdout.readline, b""):
                try:
                    riga = riga_bytes.decode("utf-8", errors="replace").rstrip("\n\r")
                except Exception:
                    riga = repr(riga_bytes)
                with self._lock_console:
                    self._console_righe.append(riga)
                    if len(self._console_righe) > _MAX_RIGHE_CONSOLE:
                        self._console_righe.pop(0)
        except Exception:
            pass

    def _registra_processo(self, proc, avvio_diretto):
        self._processo = proc
        self._avviato_da_grafite = True
        self._avvio_diretto = avvio_diretto

    def _server_gia_attivo(self):
        self._stato = "attivo"
        self._avviato_da_grafite = False
        self._aggiorna_stato_ui()
        self._app.imposta_stato(
            "ComfyUI era già in esecuzione su questa porta — istanza esterna.")

    def _server_pronto(self):
        self._stato = "attivo"
        self._aggiorna_stato_ui()
        self._app.imposta_stato("ComfyUI attivo e pronto.")

    def _avvio_fallito(self, msg):
        self._stato = "spento"
        self._aggiorna_stato_ui()
        self._app.imposta_stato("Avvio ComfyUI fallito.", "errore")
        # Mostra le righe di errore nell'area testo
        self._txt_meta.config(state="normal")
        self._txt_meta.delete("1.0", "end")
        self._txt_meta.insert("1.0", msg)
        self._txt_meta.config(state="disabled")

    # ------------------------------------------------------------------
    # Apertura browser
    # ------------------------------------------------------------------

    def _apri_browser(self):
        webbrowser.open(f"http://127.0.0.1:{self._porta}")

    # ------------------------------------------------------------------
    # Arresto server
    # ------------------------------------------------------------------

    def _ferma_server(self):
        if not self._avviato_da_grafite or self._processo is None:
            return

        self._app.imposta_stato("Arresto ComfyUI in corso...")
        proc = self._processo
        diretto = self._avvio_diretto

        def lavora():
            self._termina_processo(proc, diretto)
            self.after(0, self._server_fermato)

        threading.Thread(target=lavora, daemon=True).start()

    def _termina_processo(self, proc, avvio_diretto):
        """Termina il processo (e i figli se avvio via .bat)."""
        import time
        if proc.poll() is not None:
            return

        if avvio_diretto:
            proc.terminate()
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait(timeout=5)
        else:
            # Avvio via .bat: su Windows abbatti l'albero con taskkill
            if sys.platform == "win32":
                try:
                    subprocess.run(
                        ["taskkill", "/F", "/T", "/PID", str(proc.pid)],
                        creationflags=subprocess.CREATE_NO_WINDOW,
                        timeout=10)
                except Exception:
                    _log.exception("taskkill fallito")
                    proc.kill()
            else:
                # Unix: gruppo di processi
                import signal
                try:
                    os.killpg(os.getpgid(proc.pid), signal.SIGTERM)
                    time.sleep(2)
                    os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
                except Exception:
                    proc.kill()
            try:
                proc.wait(timeout=5)
            except Exception:
                pass

    def _server_fermato(self):
        self._stato = "spento"
        self._processo = None
        self._avviato_da_grafite = False
        self._aggiorna_stato_ui()
        self._app.imposta_stato("ComfyUI fermato.")

    # ------------------------------------------------------------------
    # Cleanup alla chiusura di Grafite
    # ------------------------------------------------------------------

    def cleanup(self):
        """Chiamato da App alla chiusura. Termina il processo se è nostro."""
        self._polling_attivo = False
        if self._avviato_da_grafite and self._processo is not None:
            self._termina_processo(self._processo, self._avvio_diretto)

    # ------------------------------------------------------------------
    # Calcolatore di ingrandimento
    # ------------------------------------------------------------------

    def _carica_img_calcolo(self):
        path = filedialog.askopenfilename(
            title="Apri immagine per calcolo ingrandimento",
            filetypes=[("Immagini", "*.jpg *.jpeg *.png *.webp *.tiff *.tif *.bmp"),
                       ("Tutti i file", "*.*")])
        if not path:
            return

        try:
            img = Image.open(path)
            w, h = img.size
        except Exception as e:
            self._app.imposta_stato(f"Impossibile aprire: {e}", "errore")
            return

        self._calc_img_size = (w, h)
        nome = os.path.basename(path)
        self._lbl_calc_img.config(text=f"{nome}  ({w}\u00d7{h} px)",
                                   fg=self._colore("testo"))
        self._aggiorna_calcolo()

    def _aggiorna_calcolo(self, *_):
        """Ricalcola fattore di ingrandimento per lo scenario selezionato."""
        if self._calc_img_size is None:
            return

        scenario = self._calc_scenario_var.get()
        cfg = self._SCENARI.get(scenario)
        if cfg is None:
            return

        iw, ih = self._calc_img_size
        cm_l, cm_h = cfg["cm"]
        dpi = cfg["dpi"]
        bordo = cfg.get("bordo_cm", 0)
        cm_l_tot = cm_l + bordo * 2
        cm_h_tot = cm_h + bordo * 2

        W = self._cm_to_px(cm_l_tot, dpi)
        H = self._cm_to_px(cm_h_tot, dpi)

        self._lbl_px_attuale.config(text=f"{iw}\u00d7{ih} px")
        self._lbl_px_richiesta.config(text=f"{W}\u00d7{H} px")

        # Fattore sul lato più sfavorevole (quello che richiede più ingrandimento)
        fattore_w = W / iw
        fattore_h = H / ih
        fattore = max(fattore_w, fattore_h)
        fattore_arr = round(fattore, 1)

        self._lbl_fattore.config(text=f"{fattore_arr}\u00d7")

        if fattore <= 1.0:
            self._lbl_verdetto.config(
                text="L'immagine \u00e8 gi\u00e0 sufficiente, nessun upscale necessario.",
                fg=self._colore("primario"))
        elif fattore <= 4.0:
            self._lbl_verdetto.config(
                text=f"Serve un fattore {fattore_arr}\u00d7, "
                     f"un passaggio con un modello 4\u00d7 \u00e8 sufficiente.",
                fg=self._colore("testo"))
        else:
            self._lbl_verdetto.config(
                text=f"Servono {fattore_arr}\u00d7: un passaggio solo non basta, "
                     f"servono due passaggi o una misura di stampa inferiore.",
                fg=self._colore("accento"))

    # ------------------------------------------------------------------
    # Metadati PNG ComfyUI
    # ------------------------------------------------------------------

    def _carica_png_meta(self):
        path = filedialog.askopenfilename(
            title="Apri PNG prodotto da ComfyUI",
            filetypes=[("PNG", "*.png"), ("Tutti i file", "*.*")])
        if not path:
            return

        try:
            img = Image.open(path)
            w, h = img.size
        except Exception as e:
            self._app.imposta_stato(f"Impossibile aprire: {e}", "errore")
            return

        self._meta_path = path
        nome = os.path.basename(path)
        info_testo = f"{nome}  ({w}\u00d7{h} px)"

        # Leggi metadati ComfyUI
        modello_upscale = None
        json_formattato = None

        try:
            prompt_str = img.info.get("prompt", "")
            workflow_str = img.info.get("workflow", "")

            meta = {}
            if prompt_str:
                try:
                    meta["prompt"] = json.loads(prompt_str)
                except (json.JSONDecodeError, TypeError):
                    pass
            if workflow_str:
                try:
                    meta["workflow"] = json.loads(workflow_str)
                except (json.JSONDecodeError, TypeError):
                    pass

            if meta:
                json_formattato = json.dumps(meta, indent=2, ensure_ascii=False)

                # Cerca il modello di upscale nel prompt
                prompt_data = meta.get("prompt")
                if isinstance(prompt_data, dict):
                    for nodo_id, nodo in prompt_data.items():
                        try:
                            if nodo.get("class_type") == "UpscaleModelLoader":
                                nome_modello = nodo.get("inputs", {}).get("model_name")
                                if nome_modello:
                                    modello_upscale = nome_modello
                                    break
                        except (AttributeError, TypeError):
                            continue
        except Exception:
            _log.exception("Errore nella lettura dei metadati ComfyUI")

        # Aggiorna UI
        if modello_upscale:
            info_testo += f"\nModello upscale: {modello_upscale}"
        elif json_formattato is None:
            info_testo += "\nNessun metadato di ComfyUI"

        self._lbl_meta_info.config(text=info_testo, fg=self._colore("testo"))
        self._btn_passa_esporta.config(state="normal")

        # Mostra JSON nell'area testo
        self._txt_meta.config(state="normal")
        self._txt_meta.delete("1.0", "end")
        if json_formattato:
            self._txt_meta.insert("1.0", json_formattato)
        else:
            self._txt_meta.insert("1.0", "Nessun metadato di ComfyUI trovato in questo file.")
        self._txt_meta.config(state="disabled")

    # ------------------------------------------------------------------
    # Passa a Esporta
    # ------------------------------------------------------------------

    def _passa_a_esporta(self):
        if not self._meta_path:
            return
        self._app.scheda_esporta.carica_da_percorso(self._meta_path)
        self._app.seleziona_scheda_esporta()
