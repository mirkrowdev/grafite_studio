"""
FASE 4 — Export per scenario di stampa.
Ridimensiona, applica margini, assegna profilo colore e DPI, salva in TIFF.

Gli scenari stanno in un dizionario, non nel codice: aggiungerne uno = tre righe.
"""
from PIL import Image, ImageCms
from profilo_adobergb import costruisci_adobergb
import os

SCENARI = {
    "artok_provino": {
        "cm": (20, 30),
        "dpi": 300,
        "profilo": "AdobeRGB",
        "adatta": "contieni",
        "sfondo": (255, 255, 255),
    },
    "canvas_bordo_avvolgente": {
        "cm": (60, 90),
        "dpi": 150,
        "profilo": "sRGB",
        "adatta": "contieni",
        "sfondo": (255, 255, 255),
        "bordo_cm": 4,
    },
    "poster_a3": {
        "cm": (29.7, 42),
        "dpi": 200,
        "profilo": "sRGB",
        "adatta": "contieni",
        "sfondo": (255, 255, 255),
    },
}


def cm_to_px(cm, dpi):
    return int(round(cm / 2.54 * dpi))


def _profilo(nome):
    if nome == "sRGB":
        return ImageCms.ImageCmsProfile(ImageCms.createProfile("sRGB"))
    if nome == "AdobeRGB":
        # Usa directory utente, non la directory dello script (evita problemi di
        # permessi con eseguibili PyInstaller in cartelle di sistema)
        config_dir = os.path.join(os.path.expanduser("~"), ".config", "grafite")
        os.makedirs(config_dir, exist_ok=True)
        percorso = os.path.join(config_dir, "AdobeRGB1998.icc")
        if not os.path.exists(percorso):
            with open(percorso, "wb") as f:
                f.write(costruisci_adobergb())
        return ImageCms.getOpenProfile(percorso)
    raise ValueError(f"Profilo non gestito: {nome}")


def converti_profilo(img, da, a):
    if da == a:
        return img
    return ImageCms.profileToProfile(
        img, _profilo(da), _profilo(a), outputMode="RGB",
        renderingIntent=0,
    )


def esporta(path_in, path_out, scenario, override=None):
    cfg = {**SCENARI[scenario]}
    if override:
        cfg.update(override)
    dpi = cfg["dpi"]

    larghezza_cm, altezza_cm = cfg["cm"]
    bordo = cfg.get("bordo_cm", 0)
    if bordo:
        larghezza_cm += bordo * 2
        altezza_cm += bordo * 2

    W = cm_to_px(larghezza_cm, dpi)
    H = cm_to_px(altezza_cm, dpi)

    img = Image.open(path_in).convert("RGB")
    img = converti_profilo(img, "sRGB", cfg["profilo"])

    scala = min(W / img.width, H / img.height) if cfg["adatta"] == "contieni" \
        else max(W / img.width, H / img.height)
    nuova = (int(round(img.width * scala)), int(round(img.height * scala)))
    img = img.resize(nuova, Image.LANCZOS)

    tela = Image.new("RGB", (W, H), cfg["sfondo"])
    tela.paste(img, ((W - img.width) // 2, (H - img.height) // 2))

    tela.save(
        path_out,
        format="TIFF",
        compression="tiff_lzw",
        dpi=(dpi, dpi),
        icc_profile=_profilo(cfg["profilo"]).tobytes(),
    )
    return {
        "file": path_out,
        "px": (W, H),
        "cm": (round(larghezza_cm, 1), round(altezza_cm, 1)),
        "dpi": dpi,
        "profilo": cfg["profilo"],
    }


if __name__ == "__main__":
    print(esporta(
        "/mnt/user-data/uploads/1786364219057_image.png",
        "/home/claude/TPKing_artok_20x30_300dpi_AdobeRGB.tif",
        "artok_provino",
    ))
