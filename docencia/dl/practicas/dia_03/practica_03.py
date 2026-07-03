"""Práctica Día 03 — Regularizar el MLP del Día 02."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import torch
import torch.nn as nn
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (accuracy_score, f1_score, recall_score,
                             roc_auc_score)
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler

DIA02 = Path(__file__).resolve().parents[2] / "dia_02_tema_1" / "practica"
sys.path.insert(0, str(DIA02))
from practica_02 import load_data, prepare  # noqa: E402

SEED = 0
DEVICE = "cuda" if torch.cuda.is_available() else "cpu"


class MLPReg(nn.Module):
    def __init__(self, d_in, d_h=64, p=0.3, use_bn=True):
        super().__init__()
        layers = []
        for d_out in (d_h, d_h // 2):
            layers.append(nn.Linear(d_in, d_out))
            if use_bn:
                layers.append(nn.BatchNorm1d(d_out))
            layers.append(nn.ReLU())
            if p > 0:
                layers.append(nn.Dropout(p))
            d_in = d_out
        layers.append(nn.Linear(d_in, 1))
        self.net = nn.Sequential(*layers)

    def forward(self, x):
        return self.net(x).squeeze(-1)


def train_loop(X_tr, y_tr, X_va, y_va, *, p=0.3, wd=1e-4, lr=1e-3,
               epochs=80, patience=12):
    torch.manual_seed(SEED)
    m = MLPReg(X_tr.shape[1], p=p).to(DEVICE)
    opt = torch.optim.AdamW(m.parameters(), lr=lr, weight_decay=wd)
    sched = torch.optim.lr_scheduler.CosineAnnealingLR(opt, T_max=epochs)
    fn = nn.BCEWithLogitsLoss()
    Xt = torch.tensor(X_tr, dtype=torch.float32, device=DEVICE)
    yt = torch.tensor(y_tr, dtype=torch.float32, device=DEVICE)
    Xv = torch.tensor(X_va, dtype=torch.float32, device=DEVICE)
    yv = torch.tensor(y_va, dtype=torch.float32, device=DEVICE)
    hist = {"train": [], "val": [], "lr": []}
    best, best_state, since = float("inf"), None, 0
    n = len(Xt)
    for ep in range(epochs):
        m.train()
        idx = torch.randperm(n, device=DEVICE)
        tl = 0.0
        for i in range(0, n, 64):
            sl = idx[i:i + 64]
            opt.zero_grad()
            loss = fn(m(Xt[sl]), yt[sl])
            loss.backward(); opt.step()
            tl += loss.item() * len(sl)
        sched.step()
        m.eval()
        with torch.no_grad():
            vl = fn(m(Xv), yv).item()
        hist["train"].append(tl / n); hist["val"].append(vl)
        hist["lr"].append(opt.param_groups[0]["lr"])
        if vl < best - 1e-4:
            best = vl; best_state = {k: v.clone() for k, v in m.state_dict().items()}
            since = 0
        else:
            since += 1
            if since >= patience:
                break
    if best_state is not None:
        m.load_state_dict(best_state)
    return m, hist


def metrics(m, X, y, t=0.5):
    m.eval()
    with torch.no_grad():
        p = torch.sigmoid(m(torch.tensor(X, dtype=torch.float32, device=DEVICE))).cpu().numpy()
    yh = (p >= t).astype(int)
    return {"auc": float(roc_auc_score(y, p)),
            "acc": float(accuracy_score(y, yh)),
            "recall": float(recall_score(y, yh, pos_label=1)),
            "f1": float(f1_score(y, yh, pos_label=1))}


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--csv", type=Path, default=None)
    args = p.parse_args()
    print(f"Device: {DEVICE}")
    df = load_data(args.csv)
    X, y = prepare(df)
    X_tr, X_te, y_tr, y_te = train_test_split(X, y, test_size=0.2,
                                              random_state=SEED, stratify=y)
    sc = StandardScaler().fit(X_tr)
    X_tr_s, X_te_s = sc.transform(X_tr), sc.transform(X_te)
    lr = LogisticRegression(max_iter=2000).fit(X_tr_s, y_tr)
    p_lr = lr.predict_proba(X_te_s)[:, 1]; yh = (p_lr >= 0.5).astype(int)
    m_lr = {"auc": roc_auc_score(y_te, p_lr), "acc": accuracy_score(y_te, yh),
            "recall": recall_score(y_te, yh, pos_label=1),
            "f1": f1_score(y_te, yh, pos_label=1)}
    configs = [{"name": "base", "p": 0.0, "wd": 0.0},
               {"name": "+drop", "p": 0.3, "wd": 0.0},
               {"name": "+drop+L2", "p": 0.3, "wd": 1e-4},
               {"name": "todo+cos", "p": 0.3, "wd": 1e-4}]
    print("\nMétrica       LR     base   +drop  +drop+L2  todo+cos")
    res_all = {"LR": m_lr}
    for c in configs:
        m, _ = train_loop(X_tr_s, y_tr, X_te_s, y_te, p=c["p"], wd=c["wd"],
                          epochs=80)
        res_all[c["name"]] = metrics(m, X_te_s, y_te)
    for k in m_lr:
        row = f"  {k:>6s}    " + "   ".join(
            f"{res_all[n][k]:5.3f}" for n in ["LR", "base", "+drop", "+drop+L2", "todo+cos"]
        )
        print(row)


if __name__ == "__main__":
    main()
