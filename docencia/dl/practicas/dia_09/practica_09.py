"""Práctica Día 09 — Self-attention de un solo bloque con numpy + verificación PyTorch."""
from __future__ import annotations

import numpy as np
import torch
import torch.nn.functional as F


def softmax(x: np.ndarray, axis: int = -1) -> np.ndarray:
    x = x - x.max(axis=axis, keepdims=True)
    e = np.exp(x)
    return e / e.sum(axis=axis, keepdims=True)


def multihead_self_attention(X: np.ndarray, Wq, Wk, Wv, Wo, n_heads: int) -> np.ndarray:
    """Self-attention multi-head implementada a mano.

    Args:
        X: (T, d_model)
        Wq, Wk, Wv: (d_model, d_model)
        Wo: (d_model, d_model)
        n_heads: número de cabezas
    """
    T, d_model = X.shape
    d_head = d_model // n_heads
    Q = X @ Wq
    K = X @ Wk
    V = X @ Wv
    # split en n_heads
    def split(M):
        return M.reshape(T, n_heads, d_head).transpose(1, 0, 2)  # (h, T, d_head)
    Qh = split(Q); Kh = split(K); Vh = split(V)
    scores = Qh @ Kh.transpose(0, 2, 1) / np.sqrt(d_head)
    alpha = softmax(scores, axis=-1)
    out = alpha @ Vh  # (h, T, d_head)
    out = out.transpose(1, 0, 2).reshape(T, d_model)
    return out @ Wo


def main():
    rng = np.random.default_rng(0)
    T, d_model, n_heads = 6, 16, 4
    X = rng.normal(size=(T, d_model)).astype(np.float32)
    Wq = rng.normal(size=(d_model, d_model)).astype(np.float32) * 0.1
    Wk = rng.normal(size=(d_model, d_model)).astype(np.float32) * 0.1
    Wv = rng.normal(size=(d_model, d_model)).astype(np.float32) * 0.1
    Wo = rng.normal(size=(d_model, d_model)).astype(np.float32) * 0.1

    np_out = multihead_self_attention(X, Wq, Wk, Wv, Wo, n_heads)

    # PyTorch reference
    mha = torch.nn.MultiheadAttention(d_model, n_heads, bias=False, batch_first=True)
    with torch.no_grad():
        # PyTorch concatena Wq Wk Wv en in_proj_weight (3*d_model, d_model)
        mha.in_proj_weight.copy_(torch.tensor(np.concatenate([Wq.T, Wk.T, Wv.T], axis=0)))
        mha.out_proj.weight.copy_(torch.tensor(Wo.T))
    Xt = torch.tensor(X).unsqueeze(0)
    pt_out, _ = mha(Xt, Xt, Xt, need_weights=False)
    pt_out = pt_out.squeeze(0).detach().numpy()

    err = np.abs(np_out - pt_out).max()
    print(f"Max error vs PyTorch MultiheadAttention: {err:.2e}")
    print("OK" if err < 1e-4 else "MISMATCH")


if __name__ == "__main__":
    main()
