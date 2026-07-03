"""Práctica Día 16 — LoRA fine-tuning sobre 500 pares sintéticos.

Requiere PEFT (Hugging Face) y un modelo pequeño descargable.
Si no hay GPU, ejecuta sólo el cálculo de parámetros entrenables y la receta.
"""
from __future__ import annotations

import argparse


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--dry-run", action="store_true",
                   help="Sólo imprime la configuración, no entrena.")
    p.add_argument("--model", default="meta-llama/Llama-3.2-1B-Instruct",
                   help="Modelo base de HF. Si está gated y no tienes acceso, "
                        "se usa automáticamente un modelo abierto pequeño.")
    args = p.parse_args()
    try:
        from peft import LoraConfig, get_peft_model
        from transformers import AutoModelForCausalLM, AutoTokenizer
        import torch
    except ImportError:
        raise SystemExit("Instala peft, transformers y torch.")

    base = args.model
    # fp16 solo tiene sentido en GPU; en CPU usa fp32 para que cargue/entrene.
    dtype = torch.float16 if torch.cuda.is_available() else torch.float32
    print(f"Cargando modelo base: {base}")
    try:
        tok = AutoTokenizer.from_pretrained(base)
        model = AutoModelForCausalLM.from_pretrained(base, dtype=dtype)
    except (OSError, EnvironmentError) as exc:
        fallback = "HuggingFaceTB/SmolLM2-135M-Instruct"
        print(f"No se pudo cargar '{base}' ({type(exc).__name__}: pide acceso/"
              f"login en HF). Usando modelo abierto '{fallback}'.")
        base = fallback
        tok = AutoTokenizer.from_pretrained(base)
        model = AutoModelForCausalLM.from_pretrained(base, dtype=dtype)

    cfg = LoraConfig(
        r=8, lora_alpha=16,
        target_modules=["q_proj", "v_proj"],
        lora_dropout=0.05, bias="none", task_type="CAUSAL_LM")
    model = get_peft_model(model, cfg)
    model.print_trainable_parameters()

    if args.dry_run:
        return
    print("(Para correr entrenamiento real, sigue el notebook).")


if __name__ == "__main__":
    main()
