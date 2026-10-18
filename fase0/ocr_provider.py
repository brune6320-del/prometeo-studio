"""
PROMETEO · FASE 0B · PROVEEDORES DE OCR
───────────────────────────────────────
interface OCRProvider (DAS §9): el dominio jamás se acopla a un
proveedor. Implementación inicial: Tesseract (local, determinista,
gratuito). Futuros: GoogleDocumentAIProvider, PaddleProvider…

Los bboxes salen en PÍXELES de la imagen analizada, con el dpi
declarado. La conversión a pt ocurre UNA vez, en raster.py, a través
de geometry.SpaceTransform.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class OcrWord:
    text: str
    conf: float
    bbox_px: tuple          # (x0, y0, x1, y1) píxeles
    line_key: tuple         # agrupación (block, par, line) del proveedor


@dataclass
class OcrPage:
    words: List[OcrWord] = field(default_factory=list)
    width_px: int = 0
    height_px: int = 0
    dpi: float = 300.0
    provider: str = ""

    def lines(self) -> List[List[OcrWord]]:
        """Agrupa palabras en líneas (orden de lectura)."""
        by_key: dict = {}
        for w in self.words:
            by_key.setdefault(w.line_key, []).append(w)
        lines = [sorted(ws, key=lambda w: w.bbox_px[0]) for ws in by_key.values()]
        lines.sort(key=lambda ws: ws[0].bbox_px[1])
        return lines

    def find_line_containing(self, text: str) -> Optional[List[OcrWord]]:
        for ws in self.lines():
            joined = " ".join(w.text for w in ws)
            if text in joined:
                return ws
        return None


class OCRProvider(ABC):
    name: str = "abstract"

    @abstractmethod
    def process(self, image, dpi: float) -> OcrPage:
        """`image`: PIL.Image (L o RGB)."""
        raise NotImplementedError

import os
import shutil
import subprocess

class OCRUnavailableError(RuntimeError):
    """Lanzada cuando el motor OCR solicitado (p.ej. Tesseract) no está disponible en el entorno."""
    pass


def find_tesseract_binary() -> Optional[str]:
    """Descubre el binario ejecutable de tesseract en variables de entorno, bundle o PATH."""
    env_bin = os.environ.get("PROMETEO_TESSERACT_PATH")
    if env_bin and os.path.isfile(env_bin) and os.access(env_bin, os.X_OK):
        return env_bin

    # App bundle paths
    app_dir = os.environ.get("PROMETEO_APP_DIR")
    if app_dir:
        candidates = [
            os.path.join(app_dir, "Contents", "Resources", "ocr", "bin", "tesseract"),
            os.path.join(app_dir, "Contents", "MacOS", "tesseract"),
            os.path.join(app_dir, "Contents", "Resources", "tesseract"),
            os.path.join(app_dir, "resources", "ocr", "bin", "tesseract"),
            os.path.join(app_dir, "bin", "tesseract"),
        ]
        for c in candidates:
            if os.path.isfile(c) and os.access(c, os.X_OK):
                return c

    # Packaged repo resources
    repo_resources_bin = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "studio-desktop", "resources", "ocr", "bin", "tesseract"))
    if os.path.isfile(repo_resources_bin) and os.access(repo_resources_bin, os.X_OK):
        return repo_resources_bin

    # System paths
    for p in ["/opt/homebrew/bin/tesseract", "/usr/local/bin/tesseract", "/usr/bin/tesseract"]:
        if os.path.isfile(p) and os.access(p, os.X_OK):
            return p

    which_path = shutil.which("tesseract")
    if which_path:
        return which_path

    return None


def find_tessdata_dir() -> Optional[str]:
    """Descubre el directorio tessdata para prefijos de idioma."""
    env_dir = os.environ.get("TESSDATA_PREFIX") or os.environ.get("PROMETEO_TESSDATA_PREFIX")
    if env_dir and os.path.isdir(env_dir):
        return env_dir

    app_dir = os.environ.get("PROMETEO_APP_DIR")
    if app_dir:
        candidates = [
            os.path.join(app_dir, "Contents", "Resources", "ocr", "tessdata"),
            os.path.join(app_dir, "Contents", "Resources", "tessdata"),
            os.path.join(app_dir, "resources", "ocr", "tessdata"),
            os.path.join(app_dir, "share", "tessdata"),
        ]
        for c in candidates:
            if os.path.isdir(c):
                return c

    repo_resources_tessdata = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "studio-desktop", "resources", "ocr", "tessdata"))
    if os.path.isdir(repo_resources_tessdata):
        return repo_resources_tessdata

    for p in ["/opt/homebrew/share/tessdata", "/usr/local/share/tessdata", "/usr/share/tessdata"]:
        if os.path.isdir(p):
            return p

    return None


def is_tesseract_available() -> bool:
    """Verifica de forma no bloqueante si Tesseract puede ser ejecutado."""
    bin_path = find_tesseract_binary()
    if not bin_path:
        return False
    try:
        proc = subprocess.run([bin_path, "--version"], stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=2.0)
        return proc.returncode == 0
    except Exception:
        return False


class TesseractOCRProvider(OCRProvider):
    """OCR real, local, determinista. Calidad honesta: ni mejor ni peor
    que la que tendrá un proveedor de nube — y con cajas imperfectas,
    que es exactamente lo que Fase 0B debe soportar."""

    name = "tesseract"
    min_conf: float = 30.0

    def __init__(self, lang: str = "eng", config: str = "--psm 6", timeout_seconds: Optional[float] = None, tesseract_cmd: Optional[str] = None):
        import pytesseract  # import diferido: dependencia del proveedor
        self._pt = pytesseract
        self.lang = lang
        self.config = config
        self.timeout_seconds = timeout_seconds

        resolved_bin = tesseract_cmd or find_tesseract_binary()
        if resolved_bin:
            self._pt.pytesseract.tesseract_cmd = resolved_bin

        tessdata = find_tessdata_dir()
        if tessdata and "TESSDATA_PREFIX" not in os.environ:
            os.environ["TESSDATA_PREFIX"] = tessdata

    def process(self, image, dpi: float) -> OcrPage:
        if not is_tesseract_available():
            raise OCRUnavailableError("Tesseract OCR binary is not available. System is operating in degraded born-digital mode.")

        kwargs = {
            "lang": self.lang,
            "config": self.config,
            "output_type": self._pt.Output.DICT,
        }
        if self.timeout_seconds is not None:
            kwargs["timeout"] = self.timeout_seconds

        data = self._pt.image_to_data(image, **kwargs)
        page = OcrPage(width_px=image.width, height_px=image.height,
                       dpi=dpi, provider=self.name)
        for i in range(len(data["text"])):
            txt = data["text"][i].strip()
            try:
                conf = float(data["conf"][i])
            except (ValueError, TypeError):
                conf = -1.0
            if not txt or conf < self.min_conf:
                continue
            x, y, w, h = (data["left"][i], data["top"][i],
                          data["width"][i], data["height"][i])
            page.words.append(OcrWord(
                text=txt, conf=conf, bbox_px=(x, y, x + w, y + h),
                line_key=(data["block_num"][i], data["par_num"][i],
                          data["line_num"][i])))
        return page


class JitterOCRProvider(OCRProvider):
    """Decorador adversarial (caso J): perturba las cajas del OCR real
    con ruido gaussiano controlado — simula la geometría imperfecta de
    un OCR peor sin fingir el texto: las palabras siguen viniendo del
    OCR de verdad."""

    name = "tesseract+jitter"

    def __init__(self, inner: OCRProvider, sigma_px: float = 3.0, seed: int = 7):
        import random
        self.inner = inner
        self.sigma = sigma_px
        self.rng = random.Random(seed)

    def process(self, image, dpi: float) -> OcrPage:
        page = self.inner.process(image, dpi)
        for w in page.words:
            x0, y0, x1, y1 = w.bbox_px
            dx0, dy0, dx1, dy1 = (self.rng.gauss(0, self.sigma) for _ in range(4))
            w.bbox_px = (max(0, x0 + dx0), max(0, y0 + dy0),
                         x1 + dx1, y1 + dy1)
        return page


# ── Independencia de verificación (PRE-GATE) ─────────────────────────
# El OCR que VERIFICA no debería ser el mismo camino que DETECTÓ.
# Niveles:
#   NONE   — misma instancia, o mismo motor con misma config: un error
#            sistemático de lectura se autoconfirmaría.
#   WEAK   — mismo motor, config distinta: reduce correlación, NO es
#            independencia fuerte. Se marca explícitamente y nunca se
#            presenta como verificación independiente.
#   STRONG — motor distinto (p.ej. detección Tesseract + verificación
#            PaddleOCR / Google Document AI).

def engine_of(provider: OCRProvider) -> OCRProvider:
    """Desenvuelve decoradores (JitterOCRProvider…) hasta el motor base."""
    cur = provider
    while getattr(cur, "inner", None) is not None:
        cur = cur.inner
    return cur


def independence_level(primary: OCRProvider, verifier: OCRProvider) -> str:
    if primary is None or verifier is None:
        return "NONE"
    if verifier is primary:
        return "NONE"
    pe, ve = engine_of(primary), engine_of(verifier)
    if type(pe).__name__ != type(ve).__name__:
        return "STRONG"
    same_cfg = getattr(pe, "config", None) == getattr(ve, "config", None)
    return "NONE" if same_cfg else "WEAK"


def default_verifier_for(primary: OCRProvider) -> OCRProvider:
    """Verificador por defecto: config DISTINTA del detector cuando el
    motor es el mismo (→ WEAK, marcado). Con motor desconocido, un
    Tesseract con config propia → STRONG."""
    base = engine_of(primary)
    if type(base).__name__ == "TesseractOCRProvider":
        cfg = "--psm 4" if base.config == "--psm 3" else "--psm 3"
        return TesseractOCRProvider(config=cfg)
    return TesseractOCRProvider(config="--psm 3")
