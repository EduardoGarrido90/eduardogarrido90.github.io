"""Práctica Día 10 — Comparar latencia y calidad: Transformer denso vs MoE vs SSM.

Como Mamba y MoE requieren GPUs grandes, este script se queda en simular las
trade-offs de coste/latencia y deja al alumno la parte cualitativa de
ejecutar prompts reales en HuggingFace Spaces.
"""
from __future__ import annotations

import time
import numpy as np


MODELS = [
    {"name": "Llama 3.3 70B (denso)",  "tok_per_sec": 22.0,  "context_max": 32_768, "active_params": 70.0, "total_params": 70.0,  "quality": 0.78},
    {"name": "Mixtral 8x22B (MoE)",    "tok_per_sec": 38.0,  "context_max": 64_000, "active_params": 39.0, "total_params": 176.0, "quality": 0.81},
    {"name": "DeepSeek-V3 (MoE)",      "tok_per_sec": 40.0,  "context_max": 64_000, "active_params": 37.0, "total_params": 671.0, "quality": 0.86},
    {"name": "Mamba-2 (SSM)",          "tok_per_sec": 65.0,  "context_max": 1_000_000, "active_params": 7.0,  "total_params": 7.0,   "quality": 0.71},
    {"name": "Jamba (híbrido)",        "tok_per_sec": 30.0,  "context_max": 256_000, "active_params": 12.0, "total_params": 52.0,  "quality": 0.79},
]


def main():
    print(f"{'Modelo':30s}  {'Tok/s':>7s}  {'Ctx':>9s}  {'Act B':>7s}  {'Tot B':>7s}  {'Q':>5s}")
    print("-" * 78)
    for m in MODELS:
        print(f"{m['name']:30s}  {m['tok_per_sec']:7.1f}  "
              f"{m['context_max']:>9,d}  {m['active_params']:7.1f}  "
              f"{m['total_params']:7.1f}  {m['quality']:5.2f}")

    print("\nNotas pedagógicas:")
    print("- Mamba lidera contexto y tokens/seg, pero pierde en calidad bruta.")
    print("- DeepSeek-V3 lidera calidad con coste por token bajo (37 B activos de 671 B).")
    print("- Llama 70B es el denso clásico: simple de servir pero más caro por token.")


if __name__ == "__main__":
    main()
