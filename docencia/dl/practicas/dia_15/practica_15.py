"""Práctica Día 15 — RAG mínimo: ingesta + búsqueda + respuesta.

Sin dependencias pesadas: usa sentence-transformers + chroma (o numpy puro).
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np


def chunk_text(text: str, size: int = 400, overlap: int = 60) -> list[str]:
    chunks = []
    i = 0
    while i < len(text):
        chunks.append(text[i:i + size])
        i += size - overlap
    return chunks


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--corpus", type=Path, default=None,
                   help="Carpeta con .txt o .md a indexar; si no, usa demo.")
    p.add_argument("--query", default="¿Cuál es el plazo máximo de la hipoteca?")
    args = p.parse_args()

    if args.corpus is None or not args.corpus.exists():
        docs = [
            ("hipoteca_fija.txt", "La hipoteca a tipo fijo de BBVA incluye una comisión de apertura del 0,5 %. El plazo máximo es de 30 años. La tasación corre por cuenta del cliente."),
            ("hipoteca_variable.txt", "La hipoteca variable de BBVA está referenciada al Euribor + 0,9 %. No tiene comisión de apertura."),
            ("plazo_personal.txt", "Los préstamos personales tienen un plazo máximo de 8 años y un importe de hasta 75 000 €."),
        ]
    else:
        docs = [(f.name, f.read_text(encoding="utf-8"))
                for f in args.corpus.glob("**/*") if f.is_file() and f.suffix in (".md", ".txt")]

    try:
        from sentence_transformers import SentenceTransformer
        m = SentenceTransformer("sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2")
    except ImportError:
        raise SystemExit("Instala sentence-transformers: pip install sentence-transformers")

    # ingesta
    index = []  # (chunk_text, source, embedding)
    chunk_texts, sources = [], []
    for src, txt in docs:
        for ch in chunk_text(txt):
            chunk_texts.append(ch); sources.append(src)
    embs = m.encode(chunk_texts, normalize_embeddings=True, convert_to_numpy=True)
    print(f"Indexados {len(chunk_texts)} chunks de {len(docs)} documentos.")

    # retrieval
    q = m.encode(args.query, normalize_embeddings=True, convert_to_numpy=True)
    sims = embs @ q
    top = np.argsort(-sims)[:3]
    print(f"\nQuery: {args.query!r}")
    print("Top-3 chunks recuperados:")
    for rank, i in enumerate(top):
        print(f"  [{rank+1}] {sources[i]}  sim={sims[i]:+.3f}")
        print(f"      {chunk_texts[i][:200]}...")


if __name__ == "__main__":
    main()
