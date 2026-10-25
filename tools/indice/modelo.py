"""SigLIP local: pesos fijados, verificados y nunca incluidos en Git."""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Iterable

import numpy as np

REPO = "google/siglip-base-patch16-224"
REVISION = "264b4cf2be2e3805db80dd7f84df43989a4b76e0"
WEIGHTS_FILE = "model.safetensors"
WEIGHTS_SHA256 = "2c63cb7d1f2e95ba501893cbb8faeb4ea9a3af295498d35097126228659c2af8"
MODEL_ID = f"{REPO}@{REVISION}"


def sha256_archivo(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def cache_modelo() -> Path:
    path = Path(__file__).resolve().parent / ".cache" / "hf"
    path.mkdir(parents=True, exist_ok=True)
    return path


class ModeloVisual:
    """Codifica imágenes RGB con el modelo fijo, en CPU o MPS."""

    def __init__(self, dispositivo: str = "cpu", cache: Path | None = None):
        if dispositivo not in {"cpu", "mps"}:
            raise ValueError("dispositivo debe ser cpu o mps")
        try:
            import torch
            from huggingface_hub import hf_hub_download, snapshot_download
            from transformers import AutoImageProcessor, AutoModel
        except ImportError as exc:
            raise RuntimeError("Instala requirements.txt antes de cargar SigLIP") from exc

        if dispositivo == "mps" and not torch.backends.mps.is_available():
            raise RuntimeError("MPS no está disponible en esta Mac")
        self.dispositivo = dispositivo
        self.torch = torch
        cache_dir = str(cache or cache_modelo())
        pesos = Path(hf_hub_download(REPO, WEIGHTS_FILE, revision=REVISION, cache_dir=cache_dir))
        digest = sha256_archivo(pesos)
        if digest != WEIGHTS_SHA256:
            raise RuntimeError(f"SHA-256 de pesos incorrecto: {digest}")
        self.pesos_sha256 = digest
        # Descarga solo los ficheros de configuración/procesador necesarios.
        local = snapshot_download(
            REPO,
            revision=REVISION,
            cache_dir=cache_dir,
            allow_patterns=["*.json", "*.txt", WEIGHTS_FILE],
        )
        self.procesador = AutoImageProcessor.from_pretrained(local, local_files_only=True, use_fast=False)
        self.modelo = AutoModel.from_pretrained(local, local_files_only=True, use_safetensors=True)
        self.modelo.to(dispositivo).eval()

    def codificar(self, imagenes: Iterable, lote: int = 2) -> np.ndarray:
        if lote < 1 or lote > 8:
            raise ValueError("lote debe estar entre 1 y 8 para esta Mac")
        imagenes = list(imagenes)
        if not imagenes:
            return np.empty((0, 0), dtype=np.float32)
        vectores = []
        with self.torch.inference_mode():
            for inicio in range(0, len(imagenes), lote):
                entrada = self.procesador(images=imagenes[inicio:inicio + lote], return_tensors="pt")
                entrada = {k: v.to(self.dispositivo) for k, v in entrada.items()}
                salida = self.modelo.get_image_features(**entrada)
                if hasattr(salida, "pooler_output"):
                    salida = salida.pooler_output
                salida = salida.float()
                salida = salida / salida.norm(dim=-1, keepdim=True).clamp_min(1e-12)
                vectores.append(salida.cpu().numpy())
        return np.concatenate(vectores, axis=0).astype(np.float32, copy=False)
