"""
FASE 1 — Normalizzazione dello sketch fotografato.
Correzione prospettica + neutralizzazione del tono carta + contrasto.
"""
import cv2
import numpy as np


def correggi_prospettiva(img, angoli, larghezza=None, altezza=None):
    """angoli: [TL, TR, BR, BL] in coordinate pixel dell'originale."""
    src = np.float32(angoli)
    tl, tr, br, bl = src

    if larghezza is None:
        larghezza = int(max(np.linalg.norm(tr - tl), np.linalg.norm(br - bl)))
    if altezza is None:
        altezza = int(max(np.linalg.norm(bl - tl), np.linalg.norm(br - tr)))

    dst = np.float32([[0, 0], [larghezza, 0], [larghezza, altezza], [0, altezza]])
    M = cv2.getPerspectiveTransform(src, dst)
    return cv2.warpPerspective(img, M, (larghezza, altezza), flags=cv2.INTER_CUBIC)


def neutralizza_carta(img, forza=0.7):
    """Toglie la dominante di colore della luce ambiente senza spegnere i pigmenti."""
    lab = cv2.cvtColor(img, cv2.COLOR_BGR2LAB).astype(np.float32)
    L, A, B = cv2.split(lab)
    mask = L > np.percentile(L, 75)
    A -= (np.mean(A[mask]) - 128) * forza
    B -= (np.mean(B[mask]) - 128) * forza
    out = cv2.merge([L, A, B])
    return cv2.cvtColor(np.clip(out, 0, 255).astype(np.uint8), cv2.COLOR_LAB2BGR)


def contrasto_locale(img, clip=1.6, griglia=8):
    """CLAHE sulla sola luminanza: recupera il tratto senza bruciare i colori."""
    lab = cv2.cvtColor(img, cv2.COLOR_BGR2LAB)
    L, A, B = cv2.split(lab)
    L = cv2.createCLAHE(clipLimit=clip, tileGridSize=(griglia, griglia)).apply(L)
    return cv2.cvtColor(cv2.merge([L, A, B]), cv2.COLOR_LAB2BGR)


def normalizza_array(img, angoli, clip=1.6, forza_wb=0.7):
    """
    Elabora un array numpy BGR già caricato e restituisce l'array elaborato.

    Parametri
    ---------
    img      : array numpy BGR (come restituito da cv2.imread)
    angoli   : lista/array di 4 coordinate [(x,y), ...] in ordine [TL, TR, BR, BL]
    clip     : clipLimit per CLAHE (default 1.6)
    forza_wb : forza della neutralizzazione della carta (default 0.7)

    Restituisce
    -----------
    Array numpy BGR elaborato.
    """
    img = correggi_prospettiva(img, angoli)
    img = neutralizza_carta(img, forza=forza_wb)
    img = contrasto_locale(img, clip=clip)
    return img


def normalizza(path_in, path_out, angoli, clip=1.6, forza_wb=0.7):
    img = cv2.imread(path_in)
    if img is None:
        raise FileNotFoundError(path_in)
    img = normalizza_array(img, angoli, clip=clip, forza_wb=forza_wb)
    cv2.imwrite(path_out, img, [cv2.IMWRITE_PNG_COMPRESSION, 3])
    return img.shape


if __name__ == "__main__":
    ANGOLI = [(135, 70), (2645, 20), (2620, 3920), (120, 3985)]
    print(normalizza(
        "/mnt/user-data/uploads/1000081588.webp",
        "/home/claude/sketch_normalizzato.png",
        ANGOLI,
    ))
