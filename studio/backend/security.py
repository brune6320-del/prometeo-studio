"""PROMETEO Studio · Security Boundary & Path Traversal Guards
──────────────────────────────────────────────────────────────
Garantiza el aislamiento entre el frontend web y el sistema de archivos del host.
1. Bloqueo de path traversal (../, rutas absolutas arbitrarias).
2. Sanitización estricta de nombres de archivos.
3. Confinamiento de almacenamiento en workspace temporal aislado.
"""

import os
import re
from typing import Sequence, Optional

# Extensiones autorizadas
ALLOWED_EXTENSIONS = {".pdf"}


class SecurityViolationError(ValueError):
    """Excepción lanzada cuando una petición viola los límites de seguridad."""
    pass


def sanitize_filename(filename: str) -> str:
    """Elimina secuencias maliciosas de nombres de archivos y retorna un nombre seguro."""
    if not filename:
        return "document.pdf"

    # Normalizar separadores tanto POSIX como Windows
    normalized = filename.replace("\\", "/")
    clean = os.path.basename(normalized)

    base, ext = os.path.splitext(clean)
    if ext.lower() == ".pdf":
        safe_base = re.sub(r"[^a-zA-Z0-9_\-]", "_", base).strip("_.-")
        clean = f"{safe_base or 'document'}.pdf"
    else:
        safe_name = re.sub(r"[^a-zA-Z0-9_\-]", "_", clean).strip("_.-")
        clean = f"{safe_name or 'document'}.pdf"

    return clean


def assert_safe_path(path: str, allowed_bases: Sequence[str]) -> str:
    """Verifica que 'path' resuelve dentro de alguno de los 'allowed_bases' autorizados.
    
    Lanza SecurityViolationError si detecta path traversal o escape de sandbox.
    """
    if "\x00" in path:
        raise SecurityViolationError("Null byte detectado en ruta.")

    abs_path = os.path.abspath(path)

    for base in allowed_bases:
        abs_base = os.path.abspath(base)
        # Comprobar prefijo canónico
        if abs_path == abs_base or abs_path.startswith(abs_base + os.sep):
            return abs_path

    raise SecurityViolationError(
        f"Acceso denegado: '{path}' resuelve fuera de las rutas base autorizadas."
    )
