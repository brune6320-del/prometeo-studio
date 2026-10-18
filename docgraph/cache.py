"""PROMETEO · DocGraph Cache v0.1
────────────────────────────────
Caché determinista en memoria para DocGraph.
Evita reconstrucciones redundantes del grafo durante secuencias de llamadas a herramientas.

Garantías:
1. Clave de caché basada en digest criptográfico (source_sha256) + versión de DocGraph.
2. Agnóstico de la ruta física: dos rutas con idéntico SHA256 comparten la misma entrada.
3. Thread-safe mediante cerrojo reentrante.
4. Soporte para invalidación explícita y medición de latencias (cold vs warm).
"""

from __future__ import annotations

import os
import threading
from collections import OrderedDict
import time
from typing import Dict, Optional, Tuple

from .builder import build_docgraph, sha256_file
from .model import DocGraph


class DocGraphCache:
    """Caché en memoria indexado por SHA256 del contenido binario y versión."""

    # Versión por defecto = la que de verdad se construía. Hasta CAMP-002 la clave decía "0.1" pero
    # `get_or_build` llamaba a `build_docgraph` sin versión y siempre construía 0.3; ahora la
    # versión de la clave y la del grafo coinciden (pedir "0.1" construye 0.1 de verdad).
    def __init__(self, docgraph_version: str = "0.3", max_entries: int = 4) -> None:
        # LRU acotada: sin límite, cada documento distinto quedaba en memoria para siempre
        # (73 págs ≈ 290 MB retenidos tras cerrar la sesión; remediación 001, 2026-10-09).
        self._cache: "OrderedDict[Tuple[str, str], DocGraph]" = OrderedDict()
        self._max_entries = max(1, int(max_entries))
        self._lock = threading.RLock()
        self._default_version = docgraph_version
        self._stats = {"hits": 0, "misses": 0, "cold_ms": 0.0, "warm_ms": 0.0}

    def get(self, pdf_path: str, version: Optional[str] = None) -> Optional[DocGraph]:
        """Recupera el DocGraph en caché si el hash del archivo coincide."""
        abs_path = os.path.abspath(pdf_path)
        if not os.path.isfile(abs_path):
            return None
        sha = sha256_file(abs_path)
        ver = version or self._default_version
        key = (sha, ver)
        with self._lock:
            return self._cache.get(key)

    def get_or_build(
        self,
        pdf_path: str,
        version: Optional[str] = None,
    ) -> Tuple[DocGraph, bool]:
        """Obtiene de caché o construye deterministamente el DocGraph.
        
        Retorna:
            (graph, was_cached)
        """
        abs_path = os.path.abspath(pdf_path)
        if not os.path.isfile(abs_path):
            raise FileNotFoundError(f"Documento no encontrado: {abs_path}")

        sha = sha256_file(abs_path)
        ver = version or self._default_version
        key = (sha, ver)

        with self._lock:
            if key in self._cache:
                t0 = time.perf_counter()
                g = self._cache[key]
                self._cache.move_to_end(key)
                elapsed = (time.perf_counter() - t0) * 1000.0
                self._stats["hits"] += 1
                self._stats["warm_ms"] += elapsed
                return g, True

            # Cold build
            t0 = time.perf_counter()
            g = build_docgraph(abs_path, docgraph_version=ver)
            elapsed = (time.perf_counter() - t0) * 1000.0
            self._cache[key] = g
            self._evict()
            self._stats["misses"] += 1
            self._stats["cold_ms"] += elapsed
            return g, False

    def put(self, graph: DocGraph) -> None:
        """Almacena explícitamente un DocGraph en la caché."""
        key = (graph.source_sha256, graph.docgraph_version)
        with self._lock:
            self._cache[key] = graph
            self._cache.move_to_end(key)
            self._evict()

    def _evict(self) -> None:
        while len(self._cache) > self._max_entries:
            self._cache.popitem(last=False)

    def invalidate(self, sha256: str, version: Optional[str] = None) -> bool:
        """Invalida entradas para un hash de documento dado."""
        ver = version or self._default_version
        key = (sha256, ver)
        with self._lock:
            return self._cache.pop(key, None) is not None

    def clear(self) -> None:
        """Limpia toda la caché."""
        with self._lock:
            self._cache.clear()
            self._stats = {"hits": 0, "misses": 0, "cold_ms": 0.0, "warm_ms": 0.0}

    @property
    def stats(self) -> Dict[str, float]:
        with self._lock:
            return dict(self._stats)

    def __len__(self) -> int:
        with self._lock:
            return len(self._cache)


GLOBAL_DOCGRAPH_CACHE = DocGraphCache()
