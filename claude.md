# Specifica — Sketch→Stampa GUI

*Documento di specifica per l'implementazione. Redatto il 29 agosto 2026.*

Programma desktop personale che mette un'interfaccia grafica sopra due script già
esistenti e funzionanti del progetto Sketch→Stampa: la **fase 1 — normalizzazione**
(`normalizza.py`) e la **fase 4 — export per scenario di stampa** (`export_stampa.py`).

---

## 1. Principio architetturale — leggere prima di tutto il resto

**Gli script esistenti sono il motore e restano il motore.** La GUI è un guscio che
raccoglie parametri e chiama le loro funzioni. Nessuna logica di elaborazione immagini
va riscritta nell'interfaccia, e nessuna logica va duplicata.

In particolare: **il dizionario `SCENARI` in `export_stampa.py` resta l'unica fonte di
verità sugli scenari di stampa.** L'interfaccia lo legge e si costruisce da sola. Deve
restare vero che aggiungere uno scenario costa tre righe nel dizionario e zero righe
nell'interfaccia — la nuova voce compare automaticamente nella tendina, con le sue
caratteristiche nel riquadro dei dettagli. Questa è un'accortezza deliberata del
progetto, non un dettaglio implementativo: non va persa.

Sono ammessi ritocchi minimi ai due script dove servono per l'uso interattivo (vedi §7),
purché le firme delle funzioni pubbliche restino compatibili con l'uso da riga di comando.

---

## 2. Perimetro

### Cosa fa

- Fase 1: raddrizza e pulisce una foto di uno sketch, con anteprima interattiva
- Fase 4: prepara un file per uno scenario di stampa, con scelta guidata dello scenario

### Cosa non fa

Le fasi 2 (master generato da ChatGPT/Gemini) e 3 (upscale in ComfyUI) **stanno fuori dal
programma** e ci restano. Sono passaggi manuali su strumenti esterni.

**Conseguenza di progetto:** le due schede non sono in sequenza e non devono suggerire di
esserlo. Non c'è un percorso guidato che porta dall'una all'altra, non c'è passaggio
automatico del file dalla scheda 1 alla scheda 2. L'utente normalizza una foto, porta il
risultato altrove, e torna giorni dopo con un file completamente diverso da esportare.

---

## 3. Stack tecnico e portabilità

| Voce | Scelta |
|---|---|
| Linguaggio | Python 3.10+ |
| Interfaccia | **Tkinter** (libreria standard) |
| Immagini | `opencv-python-headless`, `numpy`, `Pillow` |
| Sistemi | Ubuntu e Windows 11, stesso sorgente |

**Perché Tkinter:** è nella libreria standard, non aggiunge dipendenze, e per una
manciata di campi e due bottoni fa il lavoro. Qt darebbe un risultato più curato al
prezzo di 40-80 MB e di una dipendenza in più. Lo scambio era in discussione finché
erano previsti due temi, perché in Tkinter sarebbero costati molto; con un tema solo
(§4.1) la scelta è chiusa a favore di Tkinter, coerentemente con la priorità dichiarata
di avere un eseguibile portabile e leggero.

**Perché la variante `headless` di OpenCV:** la GUI la fa Tkinter, quindi le finestre di
OpenCV non servono. Si evitano così sia un pacchetto molto più pesante sia i conflitti
noti tra le librerie Qt incluse in OpenCV e il resto dell'ambiente su Linux.

**Nota su Ubuntu:** Tkinter non è sempre installato con Python. Il README deve indicare
`sudo apt install python3-tk` per l'esecuzione da sorgente. Nell'eseguibile impacchettato
il problema non si pone.

### Distribuzione

PyInstaller in modalità one-file. **Va compilato separatamente su ciascun sistema** —
PyInstaller non fa cross-compilazione. Quindi un `.exe` costruito su Windows e un binario
ELF costruito su Ubuntu, dallo stesso sorgente.

Il peso atteso è 150-250 MB, quasi tutto OpenCV e NumPy. È accettabile per uno strumento
personale; non vale la pena ottimizzarlo.

Nessun file esterno deve essere richiesto accanto all'eseguibile: logo e profilo colore
sono incorporati (§6.3 e §7.2).

---

## 4. Struttura della finestra

```
┌────────────────────────────────────────────────┐
│  [corvo]  CROBU tech-lab  - Grafite                     │  ← fascia fissa
├────────────────────────────────────────────────┤
│ │ Normalizza │  Esporta  │                     │  ← due schede
├────────────────────────────────────────────────┤
│                                                │
│              contenuto della scheda            │
│                                                │
├────────────────────────────────────────────────┤
│  barra di stato: messaggi ed errori            │
└────────────────────────────────────────────────┘
```

- **Fascia superiore fissa**, sempre visibile su entrambe le schede: logo del corvo a
  sinistra, dicitura "CROBU tech-lab - Grafite" a fianco. Altezza contenuta, non deve rubare spazio
  all'anteprima.
- **Due schede** (`ttk.Notebook`): `Normalizza` ed `Esporta`. Indipendenti, ciascuna col
  proprio stato.
- **Barra di stato in basso**, unica per tutta la finestra: esito delle operazioni, errori,
  avvisi. Gli errori vanno qui e non in finestre modali, tranne quando bloccano
  l'operazione in corso.
- Finestra ridimensionabile. Misura iniziale indicativa 1100×800. L'anteprima si adatta al
  ridimensionamento.
- Interfaccia interamente in italiano.

### 4.1 Tema — solo scuro

**Il programma ha un tema solo, scuro.** Il tema chiaro è stato valutato e scartato: due
temi completi in Tkinter costano sproporzionatamente rispetto al beneficio, e la priorità
dichiarata è che l'applicazione sia portabile e autosufficiente. Nessun interruttore,
nessun file di preferenze per il tema, nessuna commutazione a caldo.

| Ruolo | Hex | Uso |
|---|---|---|
| Sfondo app | `#111113` | Fondo della finestra |
| Barra e schede | `#1F1F23` | Fascia del logo, striscia delle schede, barra di stato |
| Superficie | `#18181B` | Fondo dei campi di sola lettura |
| Contenitore | `#27272A` | Riquadri, bottoni neutri, tendina |
| Bordo | `#3F3F46` | Bordi esterni e separatori marcati |
| Bordo tenue | `#2A2A2E` | Bordi interni e dei campi |
| Testo primario | `#E8E6E1` | |
| Testo secondario | `#A1A1AA` | Etichette |
| Attenuato | `#71717A` · `#52525B` | Metadati, segnaposto |
| Primario | `#60A5FA` | Scheda attiva, valori calcolati in evidenza, link |
| Accento | `#EA580C` | Azione principale di ciascuna scheda, marcatori degli angoli |

Tutti i colori vanno in **un unico dizionario** in cima al modulo dell'interfaccia, mai
sparsi nel codice. Se un giorno il tema chiaro dovesse tornare in gioco, il lavoro è
aggiungere un secondo dizionario, non ripassare ogni widget.

**Colore d'avviso.** La palette non ne prevede uno e l'arancione è già impegnato come
azione principale. L'avviso di ingrandimento (§6.2) usa quindi la stessa famiglia
dell'arancione ma come superficie tinta, mai come pieno, così non si confonde col bottone:
fondo `#2A1B10`, bordo `#7C3A0E`, testo `#F2B48A`.

**Filigrana del corvo.** Il logo compare a tutta finestra come sfondo, inciso e appena
percettibile. Si ottiene con due copie sovrapposte della sagoma, senza sfumature: una
copia di rilievo in `#1E1E23` spostata di ~2,5 px in basso a destra, e sopra la copia
principale in `#0C0C0E` a registro. Lo scarto rispetto al fondo `#111113` resta entro 5-8
punti per canale: deve leggersi solo se la si cerca.

L'immagine di sfondo va **pre-calcolata una volta all'avvio** e disegnata sul `Canvas` di
fondo, non ricomposta a ogni ridisegno.

### 4.2 Note pratiche sul tema scuro in Tkinter

Con un tema solo il lavoro è contenuto, ma tre punti vanno sbrigati subito perché a
scoprirli dopo si riscrive codice:

- I widget `ttk` (`Notebook`, `Combobox`, `Scale`) richiedono un `ttk.Style` configurato a
  parte. **Usare `clam` come tema base**: `vista` su Windows e `aqua` su macOS ignorano
  molte proprietà di colore, `clam` le rispetta tutte.
- I widget classici (`Frame`, `Label`, `Canvas`) vogliono `bg` e `fg` impostati
  singolarmente. Conviene una funzione che li applichi ricorsivamente all'albero dei
  widget alla creazione della finestra.
- Su Windows la barra del titolo resta chiara e stona con tutto il resto. Si corregge con
  una chiamata a `DwmSetWindowAttribute` via `ctypes` (attributo 20,
  `DWMWA_USE_IMMERSIVE_DARK_MODE`), avvolta in un `try` perché su Linux e sulle build
  vecchie di Windows non esiste.

## 5. Scheda "Normalizza"

Espone `normalizza.py` — correzione prospettica a 4 punti, neutralizzazione della
dominante di colore, contrasto locale CLAHE.

### 5.1 Flusso

1. **Carica immagine** — file explorer. Formati accettati: JPG, PNG, WEBP, TIFF, BMP.
   Il caso reale d'uso è una foto da telefono, tipicamente 3000×4000.
2. L'immagine compare nell'anteprima, **rimpicciolita** a lato massimo ~900 px. Il fattore
   di scala va conservato per riportare le coordinate all'originale.
3. **Selezione dei quattro angoli** con clic sull'anteprima (§5.2).
4. Al quarto clic, l'anteprima passa **automaticamente** a mostrare il risultato
   normalizzato coi valori di default. Non serve premere nulla.
5. I due cursori (§5.3) aggiornano l'anteprima **dal vivo**.
6. **Salva** — file explorer, PNG.

### 5.2 Selezione degli angoli

L'utente clicca quattro punti **in ordine libero**. Il programma li riordina da solo in
TL, TR, BR, BL con criterio geometrico:

- somma delle coordinate minima → alto-sinistra; massima → basso-destra
- differenza (y−x) minima → alto-destra; massima → basso-sinistra

Questo elimina la classe di errori più probabile, cioè cliccare nell'ordine sbagliato.

Comandi disponibili:

- **Annulla ultimo punto** — toglie il punto più recente
- **Azzera** — toglie tutti e quattro
- **Trascinamento** — un punto già posato si può afferrare e spostare; l'anteprima si
  ricalcola al rilascio, non durante il trascinamento

Resa visiva: ogni punto è un cerchietto con una crocetta al centro (il centro esatto deve
essere visibile, non coperto dal marcatore). I punti posati sono uniti da un quadrilatero
a linea sottile, che si chiude al quarto. Etichetta con la posizione riconosciuta accanto
a ciascuno, aggiornata dopo il riordino.

**Fondo dell'anteprima: grigio medio**, non nero. Il disegno è su carta chiara e va
giudicato anche nel colore dopo la neutralizzazione: un fondo scuro lo fa sembrare più
caldo di quanto sia. Un grigio neutro attorno al 50% è l'unico che non inganna l'occhio,
ed è quindi l'unico punto dell'interfaccia che si stacca dalla palette scura.

Se i punti sono meno di quattro, il pulsante di salvataggio resta disabilitato.

### 5.3 Parametri

**Devono esserci valori di default che producono da soli il risultato buono.** L'utente
non deve toccare nulla nel caso normale; i cursori servono per le foto che si comportano
male. Sono i valori già validati sul caso di prova "TP King".

| Parametro | Etichetta | Default | Intervallo | Passo |
|---|---|---|---|---|
| `forza_wb` | Neutralizzazione carta | **0.7** | 0.0 – 1.0 | 0.05 |
| `clip` | Contrasto del tratto | **1.6** | 0.5 – 4.0 | 0.1 |

- Valore numerico corrente visibile accanto a ciascun cursore.
- Pulsante **"Ripristina consigliati"** che riporta entrambi ai default.
- `griglia` (CLAHE tile size, oggi 8) resta fisso e non viene esposto: non è un parametro
  che si giudica a occhio.

### 5.4 Anteprima dal vivo

Il vincolo è la reattività: applicare CLAHE su un file da 3000×4000 non è istantaneo.

**Soluzione:** l'anteprima lavora sulla versione rimpicciolita a ~900 px, dove il calcolo
è immediato. I valori scelti si applicano all'originale a piena risoluzione **solo al
momento del salvataggio**.

Nota per l'implementazione: la trasformazione prospettica in anteprima va calcolata sulle
coordinate in scala ridotta, mentre al salvataggio va calcolata su quelle riportate alla
scala originale. Non ridimensionare il risultato dell'anteprima per ottenere il file
finale — deve essere una elaborazione a sé, alla risoluzione piena.

Il ricalcolo dell'anteprima va fatto su un thread separato oppure con un ritardo di
~120 ms dall'ultimo movimento del cursore, per non bloccare l'interfaccia durante il
trascinamento.

**Avvertenza sulla fedeltà:** CLAHE è un'operazione locale, quindi il suo effetto su
un'immagine rimpicciolita non è identico a quello sull'originale. L'anteprima è
indicativa, non esatta. È un compromesso accettato in cambio della reattività, ma va
scritto nel README perché non sorprenda.

### 5.5 Salvataggio

- Formato **PNG**, compressione 3 (come già fa lo script).
- Cartella proposta: quella del file di partenza.
- Nome proposto: `{nomeoriginale}_normalizzato.png`.
- Durante l'elaborazione a piena risoluzione l'interfaccia mostra che sta lavorando
  (cursore di attesa o messaggio in barra di stato) e non sembra bloccata.
- A operazione conclusa, la barra di stato riporta il percorso salvato e le dimensioni
  finali in pixel.

---

## 6. Scheda "Esporta"

Espone `export_stampa.py` — ridimensionamento, margini, profilo colore, DPI, salvataggio
TIFF.

### 6.1 Flusso

1. **Carica immagine** — file explorer. In uso reale è il master già passato per fase 2 e
   fase 3, ma il programma non lo verifica né lo presume.
2. **Tendina degli scenari**, popolata leggendo le chiavi di `SCENARI`.
3. **Riquadro dettagli** sotto la tendina, che si aggiorna al cambio di voce (§6.2).
4. **Esporta** — file explorer con nome proposto (§6.3).

### 6.2 Riquadro dettagli

Mostra, per lo scenario selezionato:

| Riga | Fonte |
|---|---|
| Misura in cm | `cfg["cm"]`, più `bordo_cm` × 2 per lato se presente |
| DPI | `cfg["dpi"]` |
| Profilo colore | `cfg["profilo"]` |
| Adattamento | `contieni` → "margine bianco" · `riempi` → "ritaglia" |
| Bordo aggiuntivo | solo se `bordo_cm` è presente, con la nota "per l'avvolgimento" |
| **Pixel finali** | calcolato: `cm_to_px()` su entrambi i lati |
| **Avviso ingrandimento** | vedi sotto |

Le ultime due righe sono le più utili e non stanno nel dizionario: vanno calcolate al
volo. Per lo scenario `artok_provino` i pixel finali sono 2362×3543.

**Avviso di ingrandimento.** Se l'immagine caricata è più piccola dei pixel finali
richiesti, il file verrà interpolato in su e la qualità ne risente. Va mostrato un avviso
evidente (colore d'attenzione, non rosso da errore) che dica di quanto: per esempio
*"L'immagine verrà ingrandita di 1,8× — qualità non garantita in stampa."*
Non deve impedire l'esportazione: è un'informazione, non un blocco. È il caso in cui si è
saltata la fase 3, quindi l'avviso è il promemoria giusto.

Il riquadro deve reggere l'aggiunta di chiavi nuove al dizionario senza rompersi: chiavi
non riconosciute vanno ignorate in silenzio, chiavi opzionali assenti vanno saltate.

### 6.3 Nome proposto in salvataggio

Schema completo, con la data:

```
{nomeoriginale}_{scenario}_{L}x{H}_{dpi}dpi_{profilo}_{AAAAMMGG}.tif
```

Esempio, da `TPKing.png` con scenario `artok_provino` il 29 agosto 2026:

```
TPKing_artok_provino_20x30_300dpi_AdobeRGB_20260829.tif
```

Regole:

- Le misure sono quelle **finali**, bordo compreso se presente. Per
  `canvas_bordo_avvolgente` diventa quindi `68x98`, non `60x90`.
- Le misure non intere usano il **punto** come separatore decimale, mai la virgola:
  `poster_a3` produce `29.7x42`. I decimali a zero si omettono: `20.0` si scrive `20`.
- Cartella proposta: quella del file di partenza.
- Se il nome esiste già, aggiungere `_2`, `_3` e così via. **Mai sovrascrivere in
  silenzio.**

---

## 7. Interventi necessari sul codice esistente

### 7.1 `normalizza.py`

Oggi le funzioni sono già separate e riutilizzabili — bene. Serve solo poter lavorare su
array in memoria invece che su percorsi, per l'anteprima.

Aggiungere una funzione che prenda un array già caricato e restituisca l'array elaborato,
lasciando `normalizza(path_in, path_out, ...)` come involucro che apre, chiama, salva. La
firma esistente non va cambiata: il blocco `__main__` deve continuare a funzionare.

### 7.2 `export_stampa.py` — modulo mancante, va risolto

**Lo script così com'è non parte su una macchina pulita.** Contiene
`from profilo_adobergb import costruisci_adobergb`, ma quel modulo non esiste nel
progetto. Va scritto.

`costruisci_adobergb()` deve restituire i **byte di un profilo ICC Adobe RGB (1998)**
costruito dai suoi valori noti, non letto da un file di Adobe:

- primarie: R (0.6400, 0.3300), G (0.2100, 0.7100), B (0.1500, 0.0600)
- punto di bianco: D65
- gamma: 2.19921875

Costruirlo da specifica invece di distribuire l'`.icc` di Adobe evita sia la dipendenza
da un file esterno sia la questione di licenza. Il profilo generato va verificato
aprendolo con `ImageCms.getOpenProfile()` e controllando che descrizione e spazio colore
siano corretti.

Da valutare in implementazione: `PIL.ImageCms.createProfile()` gestisce solo pochi spazi
predefiniti e **non** consente primarie arbitrarie, quindi i byte ICC vanno scritti
direttamente (profilo ICC v2, tag `rXYZ` `gXYZ` `bXYZ` `wtpt` `rTRC` `gTRC` `bTRC` `desc`
`cprt`). È la parte meno banale di tutto il lavoro.

Il profilo va poi incorporato nell'eseguibile: generato al primo avvio in una cartella di
appoggio dell'utente, oppure tenuto in memoria. **Non** scritto accanto all'eseguibile,
che su Windows può stare in una cartella senza permessi di scrittura — è un difetto già
presente nel codice attuale (`PERCORSO_ADOBERGB` punta alla cartella dello script) e va
corretto in questa occasione.

### 7.3 Logo

Il file sorgente è `logo_raven_crobu_tech_lab.png`, 1024×1024, corvo nero su bianco.

Va **incorporato come base64 in un modulo Python** generato una volta (`risorse.py`), non
letto da disco: l'eseguibile deve restare autosufficiente. Prima di codificarlo,
ridimensionarlo all'altezza effettiva della fascia (~48-64 px) per non portarsi dietro un
PNG da un megapixel.

Lo sfondo è bianco pieno, quindi la fascia superiore va tenuta bianca — oppure il PNG va
convertito con canale alfa trasparente in fase di preparazione, se si vuole uno sfondo
diverso.

---

## 8. Organizzazione dei file

```
sketch2stampa/
├── app.py                  avvio, finestra, fascia col logo, schede
├── scheda_normalizza.py    interfaccia fase 1
├── scheda_esporta.py       interfaccia fase 4
├── normalizza.py           motore fase 1 (esistente, ritocco §7.1)
├── export_stampa.py        motore fase 4 (esistente)
├── profilo_adobergb.py     da scrivere (§7.2)
├── risorse.py              logo in base64 (§7.3)
├── requirements.txt
└── README.md
```

Motori e interfaccia separati, come sono adesso. Deve restare possibile usare
`normalizza.py` ed `export_stampa.py` da riga di comando senza la GUI.

---

## 9. Criteri di verifica

Il lavoro è fatto quando:

1. Il programma parte con doppio clic su Ubuntu e su Windows, senza Python installato.
2. Caricando una foto storta da 3000×4000 e cliccando quattro angoli, l'anteprima
   raddrizzata compare **senza toccare i cursori**, e il risultato è quello buono.
3. Muovendo un cursore l'anteprima si aggiorna senza che l'interfaccia si blocchi.
4. Il PNG salvato è alla risoluzione piena, non quella dell'anteprima.
5. Aggiungendo uno scenario nuovo al dizionario `SCENARI` — e nient'altro — la voce
   compare nella tendina col suo riquadro dettagli corretto.
6. Il nome proposto in salvataggio segue lo schema di §6.3, data compresa.
7. Caricando un'immagine più piccola del necessario, l'avviso di ingrandimento compare e
   riporta il fattore giusto.
8. Il TIFF esportato con scenario `artok_provino` è 2362×3543 px, 300 dpi nei metadati,
   profilo Adobe RGB incorporato, RGB 8 bit, compressione LZW — cioè identico a quello che
   produce oggi lo script da riga di comando.
9. Nessun file di appoggio richiesto accanto all'eseguibile, e nessun file di
   configurazione obbligatorio: il programma parte e funziona al primo avvio su una
   macchina pulita.

Il punto 8 è il più importante: **la GUI non deve cambiare di una virgola l'output.** Se
il file prodotto dall'interfaccia differisce da quello prodotto dallo script, c'è un
errore da qualche parte.

---

## 10. Punti lasciati aperti di proposito

Non implementare, ma non impedire in futuro:

- **Modifica degli scenari dall'interfaccia.** Restano nel codice. Se un giorno servisse,
  la separazione tra logica e configurazione è già lì.
- **Elaborazione a lotti.** Un file alla volta.
- **Tema chiaro.** Valutato e scartato (§4.1). I colori centralizzati in un dizionario
  lasciano la porta aperta senza costare nulla oggi.
- **Anteprima del risultato dell'export.** Una miniatura della tela finale con l'immagine
  dentro mostrerebbe lo spessore reale dei margini con `contieni` e cosa viene tagliato via
  con `riempi`. Utile ma non indispensabile: per il provino ArtOk il risultato è già noto.
  Se si implementa, va accanto al riquadro dei dettagli, non al posto suo.
- **Memoria dell'ultima cartella usata tra un avvio e l'altro.** Utile ma non necessaria.
  Se si implementa, un piccolo file JSON in `~/.config/ricalco/` su Linux e
  `%APPDATA%\\Ricalco\\` su Windows — mai accanto all'eseguibile, che può stare in una
  cartella senza permessi di scrittura. L'assenza del file non deve mai impedire l'avvio.
- **Rilevamento automatico dei bordi del foglio.** Valutato e scartato: il clic manuale è
  affidabile e veloce, l'automatismo aggiunge un modo di sbagliare in silenzio.