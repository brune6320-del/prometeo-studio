# Índice visual de referentes

Embeddings locales con **SigLIP base patch16 224**, en CPU o MPS. No se entrena el modelo. Ejecuta los comandos con `nice -n 15` y lotes de 1–2 en una Mac de 8 GB.

## Procedencia del modelo

- Repositorio de pesos: [google/siglip-base-patch16-224](https://huggingface.co/google/siglip-base-patch16-224), revisión `264b4cf2be2e3805db80dd7f84df43989a4b76e0`.
- Licencia declarada para modelo y pesos: **Apache-2.0** en el repositorio del modelo. Código de `transformers`: **Apache-2.0**.
- `model.safetensors`: SHA-256 **publicado** `2c63cb7d1f2e95ba501893cbb8faeb4ea9a3af295498d35097126228659c2af8`; `modelo.py` lo recalcula sobre la descarga y rechaza cualquier discrepancia.
- Fuentes: [ficha del modelo](https://huggingface.co/google/siglip-base-patch16-224/tree/main), [archivo y SHA-256](https://huggingface.co/google/siglip-base-patch16-224/blob/264b4cf2be2e3805db80dd7f84df43989a4b76e0/model.safetensors), [código de SigLIP](https://github.com/huggingface/transformers/blob/main/src/transformers/models/siglip/modeling_siglip.py).

Los pesos se guardan en `tools/indice/.cache/hf/`, ignorado por Git. Tampoco se versionan imágenes ni índices generados.

## Instalación

Desde `tools/indice/`:

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
```

La primera ejecución necesita conexión para descargar los pesos. Para fotogramas de video instala además `opencv-python-headless>=4.8,<5`.
