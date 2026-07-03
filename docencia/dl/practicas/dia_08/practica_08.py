"""Práctica Día 08 — Buscador semántico con sentence-transformers."""
from __future__ import annotations

import argparse

import numpy as np


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--model", default="sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2")
    p.add_argument("--query", default="¿cuáles son los costes de una hipoteca?")
    args = p.parse_args()

    try:
        from sentence_transformers import SentenceTransformer
    except ImportError:
        raise SystemExit("Instala sentence-transformers: pip install sentence-transformers")

    docs = [
        "La hipoteca a tipo fijo incluye comisión de apertura del 0,5 %.",
        "El préstamo personal tiene un tipo de interés del 7 % TAE.",
        "El banco del parque del Retiro es de madera y tiene 80 años.",
        "Los productos de banca privada exigen un patrimonio mínimo.",
        "La sucursal abre de 8:30 a 14:00 de lunes a viernes.",
        "El parque del Retiro tiene 125 hectáreas en el centro de Madrid.",
    ]
    print(f"Cargando modelo {args.model}...")
    m = SentenceTransformer(args.model)
    embs = m.encode(docs, normalize_embeddings=True, convert_to_numpy=True)
    q = m.encode(args.query, normalize_embeddings=True, convert_to_numpy=True)
    sims = embs @ q
    order = np.argsort(-sims)
    print(f"\nQuery: {args.query!r}")
    print("Documentos por relevancia:")
    for rank, i in enumerate(order):
        print(f"  [{rank+1}]  sim={sims[i]:+.3f}  ->  {docs[i]}")


if __name__ == "__main__":
    main()
