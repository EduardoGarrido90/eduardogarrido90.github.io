"""Práctica Día 06 — Forecast LSTM sobre serie de demanda sintética."""
from __future__ import annotations

import argparse

import numpy as np
import torch
import torch.nn as nn

SEED = 0
DEVICE = "cuda" if torch.cuda.is_available() else "cpu"


def make_series(n=312, seed=SEED) -> np.ndarray:
    rng = np.random.default_rng(seed)
    t = np.arange(n)
    y = (100 + 0.18 * t + 12 * np.sin(2 * np.pi * t / 52)
         + np.where((t % 52 < 4) | ((t % 52 > 47) & (t % 52 < 51)), 18, 0)
         + rng.normal(0, 4, n))
    return y.astype(np.float32)


def windows(y: np.ndarray, lookback: int = 24, horizon: int = 4):
    X, T = [], []
    for i in range(len(y) - lookback - horizon):
        X.append(y[i:i + lookback])
        T.append(y[i + lookback:i + lookback + horizon])
    return np.array(X)[..., None], np.array(T)  # (N, T, 1), (N, H)


class Forecaster(nn.Module):
    def __init__(self, hidden=64, n_layers=2, horizon=4):
        super().__init__()
        self.lstm = nn.LSTM(1, hidden, n_layers, dropout=0.2, batch_first=True)
        self.head = nn.Linear(hidden, horizon)

    def forward(self, x):
        o, _ = self.lstm(x)
        return self.head(o[:, -1])


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--epochs", type=int, default=30)
    args = p.parse_args()
    torch.manual_seed(SEED)

    y = make_series()
    mean, std = y.mean(), y.std()
    y_n = (y - mean) / std
    X, T = windows(y_n, lookback=24, horizon=4)
    n_train = int(0.8 * len(X))
    Xtr, Ttr = X[:n_train], T[:n_train]
    Xte, Tte = X[n_train:], T[n_train:]
    print(f"Train: {Xtr.shape}  Test: {Xte.shape}")

    m = Forecaster(horizon=4).to(DEVICE)
    opt = torch.optim.AdamW(m.parameters(), lr=1e-3, weight_decay=1e-4)
    sched = torch.optim.lr_scheduler.CosineAnnealingLR(opt, T_max=args.epochs)
    fn = nn.MSELoss()
    Xt = torch.tensor(Xtr, device=DEVICE)
    yt = torch.tensor(Ttr, device=DEVICE)
    Xv = torch.tensor(Xte, device=DEVICE)
    yv = torch.tensor(Tte, device=DEVICE)
    for ep in range(args.epochs):
        m.train()
        idx = torch.randperm(len(Xt), device=DEVICE)
        tl = 0.0
        for i in range(0, len(Xt), 32):
            sl = idx[i:i + 32]
            opt.zero_grad()
            loss = fn(m(Xt[sl]), yt[sl])
            loss.backward(); opt.step()
            tl += loss.item() * len(sl)
        sched.step()
        m.eval()
        with torch.no_grad():
            vl = fn(m(Xv), yv).item()
            mae = (m(Xv) - yv).abs().mean().item() * std
        if ep % 5 == 0 or ep == args.epochs - 1:
            print(f"epoch {ep:>2d}  train={tl/len(Xt):.4f}  val={vl:.4f}  "
                  f"MAE={mae:.2f} unidades/sem")


if __name__ == "__main__":
    main()
