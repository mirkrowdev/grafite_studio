"""
Costruisce i byte di un profilo ICC v2 Adobe RGB (1998) dai valori noti.
Non dipende da file esterni né da licenze di Adobe.

Primarie: R (0.6400, 0.3300), G (0.2100, 0.7100), B (0.1500, 0.0600)
Punto bianco: D65 (0.3127, 0.3290)
Gamma: 2.19921875
"""
import struct
import numpy as np


# ---------------------------------------------------------------------------
# Primitive ICC
# ---------------------------------------------------------------------------

def _s15f16(v):
    """Virgola fissa signed 15.16."""
    return struct.pack(">i", int(round(v * 65536)))


def _xyz_tag(x, y, z):
    """Tag XYZ (20 byte)."""
    return b"XYZ " + b"\x00" * 4 + _s15f16(x) + _s15f16(y) + _s15f16(z)


def _curv_gamma(gamma):
    """Tag curv con un singolo entry = gamma × 256 (10 byte dati, padding a 4)."""
    v = int(round(gamma * 256))
    return b"curv" + b"\x00" * 4 + struct.pack(">I", 1) + struct.pack(">H", v)


def _desc_tag(text):
    """Tag desc ICC v2."""
    encoded = text.encode("ascii") + b"\x00"
    body = (
        b"desc"
        + b"\x00" * 4
        + struct.pack(">I", len(encoded))
        + encoded
        + b"\x00" * 4   # Unicode count
        + b"\x00" * 4   # Unicode (vuoto)
        + b"\x00" * 2   # ScriptCode
        + b"\x00" * 67  # Mac desc pad
    )
    return body


def _cprt_tag(text):
    """Tag text per copyright."""
    encoded = text.encode("ascii") + b"\x00"
    return b"text" + b"\x00" * 4 + encoded


# ---------------------------------------------------------------------------
# Calcolo delle matrici colorimetriche
# ---------------------------------------------------------------------------

def _calcola_primarie():
    """
    Calcola XYZ normalizzati per R, G, B e il punto bianco D65.
    Seguendo la procedura Bradford-free (solo adattamento lineare al D65).
    """
    primarie_xy = {
        "R": (0.6400, 0.3300),
        "G": (0.2100, 0.7100),
        "B": (0.1500, 0.0600),
    }
    wp_xy = (0.3127, 0.3290)

    def xy_to_xyz(x, y):
        return np.array([x / y, 1.0, (1.0 - x - y) / y])

    wp_xyz = xy_to_xyz(*wp_xy)

    M = np.column_stack([
        xy_to_xyz(*primarie_xy["R"]),
        xy_to_xyz(*primarie_xy["G"]),
        xy_to_xyz(*primarie_xy["B"]),
    ])

    S = np.linalg.solve(M, wp_xyz)

    Rxyz = M[:, 0] * S[0]
    Gxyz = M[:, 1] * S[1]
    Bxyz = M[:, 2] * S[2]

    return Rxyz, Gxyz, Bxyz, wp_xyz


# ---------------------------------------------------------------------------
# Assemblaggio profilo
# ---------------------------------------------------------------------------

def costruisci_adobergb():
    """Restituisce i byte di un profilo ICC v2 Adobe RGB (1998)."""

    Rxyz, Gxyz, Bxyz, wp_xyz = _calcola_primarie()

    # --- dati dei tag ---
    tag_desc  = _desc_tag("Adobe RGB (1998)")
    tag_cprt  = _cprt_tag("Copyright 2026 CROBU tech-lab. ICC profile built from specification.")
    tag_wtpt  = _xyz_tag(*wp_xyz)
    tag_rXYZ  = _xyz_tag(*Rxyz)
    tag_gXYZ  = _xyz_tag(*Gxyz)
    tag_bXYZ  = _xyz_tag(*Bxyz)
    tag_rTRC  = _curv_gamma(2.19921875)
    tag_gTRC  = _curv_gamma(2.19921875)
    tag_bTRC  = _curv_gamma(2.19921875)

    # Padding a multiplo di 4 byte per ogni tag data
    def pad4(b):
        r = len(b) % 4
        return b + b"\x00" * (4 - r if r else 0)

    tags_data = [
        (b"desc", tag_desc),
        (b"cprt", tag_cprt),
        (b"wtpt", tag_wtpt),
        (b"rXYZ", tag_rXYZ),
        (b"gXYZ", tag_gXYZ),
        (b"bXYZ", tag_bXYZ),
        (b"rTRC", tag_rTRC),
        (b"gTRC", tag_gTRC),
        (b"bTRC", tag_bTRC),
    ]

    n_tags = len(tags_data)
    header_size = 128
    tag_table_size = 4 + n_tags * 12  # 4 = count uint32

    # Calcola offset di ciascun tag data
    current_offset = header_size + tag_table_size
    offsets = []
    padded_data = []
    for sig, data in tags_data:
        p = pad4(data)
        offsets.append(current_offset)
        padded_data.append(p)
        current_offset += len(p)

    total_size = current_offset

    # --- Header 128 byte ---
    header = bytearray(128)
    struct.pack_into(">I", header, 0, total_size)          # dimensione totale
    # 4-7: CMM signature (zero)
    struct.pack_into(">4s", header, 8, b"\x02\x10\x00\x00")  # versione 2.1.0
    struct.pack_into(">4s", header, 12, b"mntr")           # device class
    struct.pack_into(">4s", header, 16, b"RGB ")           # color space
    struct.pack_into(">4s", header, 20, b"XYZ ")           # PCS
    # 24-35: datetime (zero)
    struct.pack_into(">4s", header, 36, b"acsp")           # firma
    # 40-43: piattaforma (zero)
    # 44-47: flags (zero)
    # 48-55: manufacturer + model (zero)
    # 56-63: attributi dispositivo (zero)
    # 64-67: rendering intent perceptual (zero)
    # Illuminante D65 in s15f16
    struct.pack_into(">i", header, 68, int(round(0.9505 * 65536)))
    struct.pack_into(">i", header, 72, int(round(1.0000 * 65536)))
    struct.pack_into(">i", header, 76, int(round(1.0890 * 65536)))
    # 80-83: creator (zero)
    # 84-127: profile ID + reserved (zero)

    # --- Tag table ---
    tag_table = bytearray()
    tag_table += struct.pack(">I", n_tags)
    for i, (sig, _data) in enumerate(tags_data):
        tag_table += sig
        tag_table += struct.pack(">I", offsets[i])
        tag_table += struct.pack(">I", len(padded_data[i]))

    # --- Assemblaggio finale ---
    profile = bytes(header) + bytes(tag_table)
    for p in padded_data:
        profile += p

    return profile


# ---------------------------------------------------------------------------
# Verifica rapida
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    from PIL import ImageCms
    import io

    data = costruisci_adobergb()
    print(f"Dimensione profilo: {len(data)} byte")

    prof = ImageCms.getOpenProfile(io.BytesIO(data))
    print(f"Descrizione: {ImageCms.getProfileDescription(prof)}")
    print(f"Spazio colore: {ImageCms.getProfileInfo(prof)}")
