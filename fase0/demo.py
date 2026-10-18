"""
PROMETEO · FASE 0 · DEMO
───────────────────────
Uso:
  python demo.py <in.pdf> <texto_viejo> <texto_nuevo> <out.pdf> [--scan]

Ejecuta el ciclo completo (extraer → validar → aplicar → exportar →
verificar) e imprime el reporte de trazabilidad en JSON.
"""
from __future__ import annotations

import argparse
import json
import os
import sys

from engine import replace_flow


def main() -> int:
    ap = argparse.ArgumentParser(description="PROMETEO Fase 0 · vertical slice")
    ap.add_argument("src")
    ap.add_argument("old")
    ap.add_argument("new")
    ap.add_argument("out")
    ap.add_argument("--scan", action="store_true",
                    help="ruta experimental Clase B (parche de fondo)")
    args = ap.parse_args()

    report = replace_flow(args.src, args.old, args.new, args.out,
                          scan_mode=args.scan)
    print(json.dumps(report, indent=2, ensure_ascii=False))

    report_path = args.out + ".report.json"
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)

    if report.get("ok"):
        size = os.path.getsize(args.out)
        print(f"\n✔ versión exportada: {args.out} ({size} bytes)")
        print(f"✔ reporte:           {report_path}")
        return 0
    print("\n✘ operación rechazada o fallida — no se escribió versión válida",
          file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
