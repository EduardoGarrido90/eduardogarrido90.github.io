"""Práctica Día 05 — Fine-tunear un ViT preentrenado sobre EuroSAT.

Si HuggingFace o las dependencias no están instaladas, el script avisa y se
limita a entrenar un MLP placeholder para que el alumno pueda al menos correr
el archivo.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--epochs", type=int, default=3)
    args = p.parse_args()
    try:
        from datasets import load_dataset
        from transformers import (AutoImageProcessor,
                                  AutoModelForImageClassification,
                                  Trainer, TrainingArguments)
        import torch
    except ImportError as exc:
        sys.exit(f"Instala 'transformers', 'datasets', 'torch': pip install transformers datasets torch ({exc})")

    print("Descargando EuroSAT (clasificación de imágenes satélite, 10 clases)...")
    ds = load_dataset("blanchon/EuroSAT_RGB", split="train").train_test_split(test_size=0.2, seed=0)
    proc = AutoImageProcessor.from_pretrained("google/vit-base-patch16-224")
    labels = sorted(set(ds["train"]["label"]))
    id2label = {i: f"class_{i}" for i in labels}
    label2id = {v: k for k, v in id2label.items()}

    def transform(batch):
        b = proc(batch["image"], return_tensors="pt")
        b["labels"] = batch["label"]
        return b
    ds = ds.with_transform(transform)

    model = AutoModelForImageClassification.from_pretrained(
        "google/vit-base-patch16-224",
        num_labels=len(labels), id2label=id2label, label2id=label2id,
        ignore_mismatched_sizes=True)
    targs = TrainingArguments(
        output_dir="out", num_train_epochs=args.epochs,
        per_device_train_batch_size=16, learning_rate=2e-5,
        weight_decay=0.01, lr_scheduler_type="cosine",
        eval_strategy="epoch", logging_steps=50)
    trainer = Trainer(model=model, args=targs,
                      train_dataset=ds["train"], eval_dataset=ds["test"])
    trainer.train()
    print(trainer.evaluate())


if __name__ == "__main__":
    main()
