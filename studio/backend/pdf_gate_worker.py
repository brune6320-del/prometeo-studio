"""Analizador aislado de PDFs no confiables (CAMP-002 · F5). NO se importa desde el motor.

Se ejecuta como proceso aparte (`python -I pdf_gate_worker.py <ruta> <max_pages> <cpu_s>`):
abre el PDF con MuPDF y recorre TODAS las páginas por los mismos caminos de análisis que usará
el motor (texto estructurado, imágenes, dibujos) y renderiza la primera página. Si MuPDF se
cuelga o revienta con un archivo hostil, muere este proceso, no el motor.

Salida: líneas JSON en stdout. Primero `{"stage": "opened", "pages": N}` (el supervisor ajusta el
tiempo máximo al tamaño del documento) y al final el veredicto `{"ok": ...}`. Código 0 si el
análisis terminó (válido o rechazado).

Si stdin es una tubería, se vigila: cuando el motor muere, la tubería se cierra y este proceso
termina en lugar de quedar huérfano.
"""
import json
import os
import resource
import stat
import sys
import threading


def watch_parent():
    try:
        if not stat.S_ISFIFO(os.fstat(0).st_mode):
            return
    except OSError:
        return

    def wait_eof():
        try:
            while os.read(0, 4096):
                pass
        except OSError:
            pass
        os._exit(70)

    threading.Thread(target=wait_eof, daemon=True).start()


def emit(payload):
    sys.stdout.write(json.dumps(payload) + "\n")
    sys.stdout.flush()


def main():
    path, max_pages, cpu_seconds = sys.argv[1], int(sys.argv[2]), int(sys.argv[3])
    # Tiempo de CPU acotado (SIGXCPU). La memoria la vigila el proceso padre: macOS no aplica
    # RLIMIT_AS/RLIMIT_RSS.
    resource.setrlimit(resource.RLIMIT_CPU, (cpu_seconds, cpu_seconds + 1))
    watch_parent()
    import pymupdf

    pymupdf.TOOLS.mupdf_display_errors(False)
    try:
        doc = pymupdf.open(path)
    except Exception as e:  # archivo dañado o que no es PDF
        emit({"ok": False, "code": "DOCUMENT_UNREADABLE", "reason": f"{type(e).__name__}: {str(e)[:200]}"})
        return
    if doc.needs_pass or doc.is_encrypted:
        emit({"ok": False, "code": "DOCUMENT_ENCRYPTED", "reason": "needs_pass"})
        return
    pages = doc.page_count
    if pages == 0:
        emit({"ok": False, "code": "DOCUMENT_UNREADABLE", "reason": "sin páginas"})
        return
    if pages > max_pages:
        emit({"ok": False, "code": "PDF_TOO_COMPLEX", "reason": f"{pages} páginas (máximo {max_pages})"})
        return
    emit({"stage": "opened", "pages": pages})
    warnings = 0
    for page in doc:
        page.get_text("rawdict")
        page.get_image_info(xrefs=True)
        page.get_drawings()
    first = doc[0]
    first.get_pixmap(dpi=36)
    warnings = len(pymupdf.TOOLS.mupdf_warnings().splitlines()) if hasattr(pymupdf.TOOLS, "mupdf_warnings") else 0
    emit({"ok": True, "pages": pages, "mupdf_warnings": warnings})


if __name__ == "__main__":
    try:
        main()
    except Exception as e:  # excepción de Python: el PDF no se pudo analizar
        emit({"ok": False, "code": "DOCUMENT_UNREADABLE", "reason": f"{type(e).__name__}: {str(e)[:200]}"})
