"""FASE 0 · Tests del núcleo geométrico (el archivo más importante)."""
from make_fixtures import ensure_assets

from geometry import Point, Rect, SpaceTransform


def test_roundtrip_pdf_raster_exacto():
    t = SpaceTransform(595.276, 841.890, dpi=300)
    p = Point(123.4, 567.8)
    back = t.raster_to_pdf(t.pdf_to_raster(p))
    assert abs(back.x - p.x) < 1e-6 and abs(back.y - p.y) < 1e-6


def test_a4_a_300dpi_dimensión_conocida():
    t = SpaceTransform(595.276, 841.890, dpi=300)
    assert t.raster_width == 2480
    assert t.raster_height == 3508


def test_canvas_con_dpr_duplica_raster():
    a = SpaceTransform(612, 792, dpi=144, dpr=1.0)
    b = SpaceTransform(612, 792, dpi=144, dpr=2.0)
    assert abs(b.canvas_width - 2 * a.canvas_width) < 1e-9
    # un punto PDF cae en el mismo lugar relativo en ambos canvas
    p = Point(306, 396)
    assert abs(b.pdf_to_canvas(p).x - 2 * a.pdf_to_canvas(p).x) < 1e-9


def test_norm_esta_en_0_1():
    t = SpaceTransform(595.276, 841.890)
    assert t.pdf_to_norm(Point(t.w_pt, t.h_pt)) == Point(1.0, 1.0)
    back = t.norm_to_pdf(t.pdf_to_norm(Point(100, 200)))
    assert abs(back.x - 100) < 1e-9 and abs(back.y - 200) < 1e-9


def test_rect_raster_roundtrip():
    t = SpaceTransform(595.276, 841.890, dpi=200, dpr=2.0)
    r = Rect(72.0, 100.5, 250.25, 122.75)
    back = t.rect_raster_to_pdf(t.rect_pdf_to_raster(r))
    assert abs(back.x0 - r.x0) < 1e-6 and abs(back.y1 - r.y1) < 1e-6
    assert abs(back.width - r.width) < 1e-6


def test_pixmap_real_coindice_con_transform():
    """El render real de PyMuPDF a 200 dpi debe medir lo que el módulo
    predice (tolerancia 1 px por redondeo del renderer)."""
    import pymupdf
    paths = ensure_assets()
    doc = pymupdf.open(paths["case_a"])
    page = doc[0]
    t = SpaceTransform(page.rect.width, page.rect.height, dpi=200)
    pix = page.get_pixmap(dpi=200)
    assert abs(pix.width - t.raster_width) <= 1
    assert abs(pix.height - t.raster_height) <= 1
    doc.close()


def test_puente_ocr_px_a_pt_error_minimo():
    """Caso B sin proveedor: usamos el ground truth vectorial de case_a,
    lo pasamos a píxeles 'como si lo hubiera dado un OCR a 200 dpi' y
    volvemos a pt. El error debe ser despreciable (< 0.01 pt)."""
    from engine import all_spans, extract
    paths = ensure_assets()
    model = extract(paths["case_a"])
    page0 = model["pages"][0]
    t = SpaceTransform(page0["width_pt"], page0["height_pt"], dpi=200)
    n = 0
    for span in all_spans(model):
        x0, y0, x1, y1 = span["bbox"]
        px = t.rect_pdf_to_raster(Rect(x0, y0, x1, y1))
        assert 0 <= px.x0 <= t.raster_width and 0 <= px.y1 <= t.raster_height
        back = t.rect_raster_to_pdf(px)
        assert abs(back.x0 - x0) < 0.01 and abs(back.y0 - y0) < 0.01
        assert abs(back.width - (x1 - x0)) < 0.01
        n += 1
    assert n >= 5
