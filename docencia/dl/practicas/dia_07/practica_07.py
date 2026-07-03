"""Práctica Día 07 — Implementar la atención a mano y comparar con PyTorch."""
from __future__ import annotations

import numpy as np
import torch
import torch.nn.functional as F


def attention_numpy(Q: np.ndarray, K: np.ndarray, V: np.ndarray) -> np.ndarray:
    """Atención escalada producto-punto.

    Args:
        Q: (T, d)
        K: (T, d)
        V: (T, d_v)
    """
    d = Q.shape[-1]
    scores = Q @ K.T / np.sqrt(d)
    weights = np.exp(scores - scores.max(axis=-1, keepdims=True))
    weights = weights / weights.sum(axis=-1, keepdims=True)
    return weights @ V


def main():
    rng = np.random.default_rng(0)
    T, d, dv = 5, 8, 4
    Q = rng.normal(size=(T, d)).astype(np.float32)
    K = rng.normal(size=(T, d)).astype(np.float32)
    V = rng.normal(size=(T, dv)).astype(np.float32)

    # numpy implementation
    np_out = attention_numpy(Q, K, V)

    # pytorch reference
    Qt, Kt, Vt = map(torch.tensor, (Q, K, V))
    pt_out = F.scaled_dot_product_attention(
        Qt.unsqueeze(0), Kt.unsqueeze(0), Vt.unsqueeze(0)
    ).squeeze(0).numpy()

    err = np.abs(np_out - pt_out).max()
    print(f"Max error vs PyTorch: {err:.2e}")
    assert err < 1e-5, "Atención propia y PyTorch divergen"
    print("OK: atención propia equivale a scaled_dot_product_attention de PyTorch.")


if __name__ == "__main__":
    main()
