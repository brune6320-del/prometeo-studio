"""
PROMETEO · FASE 0B · DATASET ADVERSARIAL RASTER (§8 A–O)
────────────────────────────────────────────────────────
Fixtures REPRODUCIBLES (numpy con semilla fija) que degradan un
documento sintético vectorial de forma realista. El ground truth
vectorial se guarda SOLO para medir error fuera del pipeline.
"""
from __future__ import annotations

import os

import numpy as np
import pymupdf
from PIL import Image, ImageFilter

HERE = os.path.dirname(os.path.abspath(__file__))
RASTER_DIR = os.path.join(HERE, "assets", "raster")
DPI = 300

# fuentes candidatas para el caso H (fuente difícil)
FONT_CANDIDATES = [
    "/System/Library/Fonts/Supplemental/Georgia.ttf",
    "/System/Library/Fonts/Supplemental/Verdana.ttf",
    "/System/Library/Fonts/Supplemental/Courier New.ttf",
]

A4_W, A4_H = 595.276, 841.890


def _source_pdf(path: str, fontfile: str | None = None,
                small: bool = False, graphics: bool = False,
                g2: str | None = None) -> None:
    """g2=None · fixture normal.
    g2="cross"  · fondo gris bajo la banda + línea que CRUZA la región
                  que será reparada (reparar la destruiría → debe
                  detectarse y rechazarse). FC-002 raster.
    g2="near"   · borde de tabla CERCANO pero fuera de la región →
                  control de especificidad (no debe disparar falso
                  positivo)."""
    doc = pymupdf.open()
    page = doc.new_page(width=A4_W, height=A4_H)
    fname, ffile = "helv", None
    if fontfile:
        page.insert_font(fontname="FX", fontfile=fontfile)
        fname, ffile = "FX", fontfile
    body = 6.5 if small else 11
    if g2 == "cross":
        # fondo de color bajo la banda del objetivo (antes del texto)
        page.draw_rect(pymupdf.Rect(60, 98, 260, 120),
                       color=None, fill=(0.93, 0.93, 0.93))
    if graphics:
        page.draw_rect(pymupdf.Rect(60, 80, 535, 210), color=(0, 0, 0), width=0.8)
        page.draw_line(pymupdf.Point(60, 145), pymupdf.Point(535, 145))
        page.draw_line(pymupdf.Point(60, 178), pymupdf.Point(535, 178))
    page.insert_text(pymupdf.Point(72, 72), "FACTURA SIMPLIFICADA",
                     fontname="hebo", fontsize=13)
    page.insert_text(pymupdf.Point(72, 110), "Cliente: Juan Perez",
                     fontname=fname, fontfile=ffile, fontsize=body)
    page.insert_text(pymupdf.Point(72, 132), "Fecha de emision: 10 de agosto de 2025",
                     fontname=fname, fontfile=ffile, fontsize=body)
    page.insert_text(pymupdf.Point(72, 168), "Importe total: 1.250,00 EUR",
                     fontname=fname, fontfile=ffile, fontsize=body)
    page.insert_text(pymupdf.Point(72, 196), "Referencia interna: AB-2025-0042",
                     fontname=fname, fontfile=ffile, fontsize=body)
    if g2 == "cross":
        # subrayado/línea de tabla que ATRAVIESA la región de reparación
        # del objetivo. OJO: "Cliente: Juan Perez" no tiene descendentes,
        # el bbox de tinta termina en el baseline (110) → la región de
        # reparación/gate es 99–113. La línea debe caer DENTRO (una a
        # 113.5 quedaría fuera y el fixture no probaría nada).
        page.draw_line(pymupdf.Point(60, 111.5), pymupdf.Point(535, 111.5),
                       color=(0, 0, 0), width=1.0)
    if g2 == "near":
        # borde de tabla cercano pero FUERA de la región de la línea Fecha
        page.draw_rect(pymupdf.Rect(300, 95, 535, 220), color=(0, 0, 0), width=0.8)
    doc.save(path, garbage=3, deflate=True)
    doc.close()


def _render(src_pdf: str) -> Image.Image:
    doc = pymupdf.open(src_pdf)
    pix = doc[0].get_pixmap(dpi=DPI)
    img = Image.frombytes("RGB", (pix.width, pix.height), pix.samples)
    doc.close()
    return img


def _np(img: Image.Image) -> np.ndarray:
    return np.asarray(img.convert("L"), dtype=np.float32)


def _pil(a: np.ndarray) -> Image.Image:
    return Image.fromarray(np.clip(a, 0, 255).astype(np.uint8), "L")


def degrade_noise(img: Image.Image, sigma=14.0, blur=0.6, contrast=0.82,
                  seed=11) -> Image.Image:
    rng = np.random.default_rng(seed)
    a = _np(img)
    if blur:
        im = _pil(a)
        im = im.filter(ImageFilter.GaussianBlur(blur))
        a = _np(im)
    a = 255.0 - (255.0 - a) * contrast
    a = a + rng.normal(0, sigma, a.shape)
    return _pil(a)


def degrade_texture(img: Image.Image, seed=23) -> Image.Image:
    """Grano de papel: ruido de baja frecuencia + tinte cálido."""
    rng = np.random.default_rng(seed)
    a = _np(img)
    small = rng.normal(0, 9, (a.shape[0] // 16, a.shape[1] // 16))
    grain = np.asarray(Image.fromarray(
        np.clip(small, 0, 255)).resize((a.shape[1], a.shape[0]), Image.BILINEAR),
        dtype=np.float32)
    a = a * 0.965 + grain * 0.6 - 3.0
    return _pil(a)


def degrade_gradient(img: Image.Image, top=233, bottom=255) -> Image.Image:
    a = _np(img)
    g = np.linspace(top, bottom, a.shape[0])[:, None]
    a = np.where(a > 200, g, a)
    return _pil(a)


def degrade_vignette(img: Image.Image, strength=42) -> Image.Image:
    a = _np(img)
    h, w = a.shape
    yy, xx = np.mgrid[0:h, 0:w]
    r = np.sqrt(((xx - w / 2) / (w / 2)) ** 2 + ((yy - h / 2) / (h / 2)) ** 2)
    a = a - (np.clip(r - 0.55, 0, 1) * strength)
    return _pil(a)


def degrade_jpeg(img: Image.Image, quality=35) -> Image.Image:
    import io
    buf = io.BytesIO()
    img.convert("RGB").save(buf, "JPEG", quality=quality)
    buf.seek(0)
    return Image.open(buf).convert("L")


def rotate(img: Image.Image, deg: float, bg=252) -> Image.Image:
    return img.rotate(deg, resample=Image.BICUBIC, fillcolor=bg, expand=False)


def perspective(img: Image.Image, strength=0.045) -> Image.Image:
    w, h = img.size
    quad = (w * strength, 0, w * (1 - strength * 0.3), h * strength,
            w, h * (1 - strength), 0, h)  # trapecio
    return img.transform((w, h), Image.QUAD, quad, resample=Image.BICUBIC,
                         fillcolor=252)


def _img_to_pdf(img: Image.Image, path: str) -> None:
    import io
    buf = io.BytesIO()
    img.save(buf, "PNG")
    doc = pymupdf.open()
    page = doc.new_page(width=img.width * 72.0 / DPI, height=img.height * 72.0 / DPI)
    page.insert_image(page.rect, stream=buf.getvalue())
    doc.save(path, garbage=3, deflate=True)
    doc.close()


def build_all(force: bool = False) -> dict:
    """Genera el dataset A–O. Devuelve {case: {pdf, png, gt_pdf}}."""
    os.makedirs(RASTER_DIR, exist_ok=True)
    font_h = next((f for f in FONT_CANDIDATES if os.path.exists(f)), None)

    # fuentes vectoriales base (deterministas)
    base_src = os.path.join(RASTER_DIR, "_src_base.pdf")
    gfx_src = os.path.join(RASTER_DIR, "_src_graphics.pdf")
    small_src = os.path.join(RASTER_DIR, "_src_small.pdf")
    font_src = os.path.join(RASTER_DIR, "_src_font.pdf")
    g2_cross_src = os.path.join(RASTER_DIR, "_src_g2_cross.pdf")
    g2_near_src = os.path.join(RASTER_DIR, "_src_g2_near.pdf")
    srcs = (base_src, gfx_src, small_src, font_src, g2_cross_src, g2_near_src)
    if not all(os.path.exists(p) for p in srcs) or force:
        _source_pdf(base_src)
        _source_pdf(gfx_src, graphics=True)
        _source_pdf(small_src, small=True)
        _source_pdf(font_src, fontfile=font_h)
        _source_pdf(g2_cross_src, g2="cross")
        _source_pdf(g2_near_src, g2="near")

    spec = {
        "A_scan_limpio":    ("clean", base_src),
        "B_scan_degradado": ("degraded", base_src),
        "C_caso_DAS":       ("rot2.5", base_src),
        "D_textura_papel":  ("texture", base_src),
        "E_jpeg":           ("jpeg", base_src),
        "F_perspectiva":    ("perspective", base_src),
        "G_sobre_graficos": ("clean", gfx_src),
        "H_fuente_dificil": ("clean", font_src),
        "I_texto_pequeno":  ("clean", small_src),
        "J_bbox_imperfecta": ("clean", base_src),       # con JitterProvider
        "M_rotacion_4":     ("rot-4.5", base_src),
        "N_fondo_gradiente": ("gradient", base_src),
        "O_iluminacion":    ("vignette", base_src),
        "G2_linea_cruza":   ("clean", g2_cross_src),   # FC-002 raster real
        "G2_borde_cercano": ("clean", g2_near_src),    # control especificidad
    }
    out = {}
    for case, (kind, src) in spec.items():
        pdf = os.path.join(RASTER_DIR, f"{case}.pdf")
        png = os.path.join(RASTER_DIR, f"{case}.png")
        if force or not (os.path.exists(pdf) and os.path.exists(png)):
            img = _render(src)
            if kind == "degraded":
                img = degrade_noise(img)
            elif kind.startswith("rot"):
                img = rotate(img, float(kind[3:]))
            elif kind == "texture":
                img = degrade_texture(img)
            elif kind == "jpeg":
                img = degrade_jpeg(img)
            elif kind == "perspective":
                img = perspective(img)
            elif kind == "gradient":
                img = degrade_gradient(img)
            elif kind == "vignette":
                img = degrade_vignette(img)
            img.save(png)
            _img_to_pdf(img, pdf)
        out[case] = {"pdf": pdf, "png": png, "gt_pdf": src}
    return out


if __name__ == "__main__":
    for name, paths in build_all(force="--force" in os.sys.argv).items():
        print(f"{name:20s} → {os.path.basename(paths['pdf'])}")
