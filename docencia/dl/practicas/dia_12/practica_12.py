"""Práctica Día 12 — Mini-storyboard publicitario con APIs gratuitas o locales."""
from __future__ import annotations

import argparse


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--mode", choices=["plan", "free", "api"], default="plan")
    args = p.parse_args()
    print("Día 12 — Práctica de storyboard.\n")
    print("Pasos a hacer en este notebook/script:")
    print(" 1) Pedir a un LLM (Ollama o Anthropic) un concepto creativo de 60 palabras.")
    print(" 2) Generar 4 imágenes con Stable Diffusion (HF Inference API gratuita).")
    print(" 3) Generar una voz off de 20 segundos con ElevenLabs free-tier o OpenAI TTS.")
    print(" 4) Reportar coste estimado y tiempo total.")
    if args.mode == "free":
        print("\nFree-tiers a usar:")
        print(" - Hugging Face Inference API (limitada por minuto, gratis tras registro).")
        print(" - ElevenLabs free 10K caracteres/mes.")
        print(" - Ollama local para LLM (qwen2.5:7b).")


if __name__ == "__main__":
    main()
