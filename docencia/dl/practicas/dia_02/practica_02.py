"""Práctica Día 02 — Tu primer MLP sobre Telco Customer Churn.

Asignatura: Deep Learning para Business Analytics — Comillas (ICADE).
Profesor: Eduardo C. Garrido-Merchán · ecgarrido@comillas.edu.

Si no tienes el CSV de Kaggle, se genera un sintético compatible.
"""
from __future__ import annotations

import argparse
import warnings
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

SEED = 0
DEVICE = "cuda" if torch.cuda.is_available() else "cpu"
warnings.filterwarnings("ignore", category=UserWarning)


def load_data(csv: Path | None = None, n: int = 3000) -> pd.DataFrame:
    if csv is not None and csv.exists():
        df = pd.read_csv(csv)
        if "TotalCharges" in df.columns:
            df["TotalCharges"] = pd.to_numeric(df["TotalCharges"], errors="coerce")
            df = df.dropna()
        # Normaliza el esquema real de Kaggle (blastchar/telco-customer-churn)
        # al que espera prepare(): sin columna de ID y objetivo 'churn' en {0,1}.
        df = df.drop(columns=[c for c in ("customerID", "customerid")
                              if c in df.columns])
        if "Churn" in df.columns and "churn" not in df.columns:
            df = df.rename(columns={"Churn": "churn"})
        if "churn" in df.columns and df["churn"].dtype == object:
            df["churn"] = (df["churn"].map({"Yes": 1, "No": 0,
                                            "yes": 1, "no": 0})
                           .astype(np.float32))
            df = df.dropna(subset=["churn"])
        return df
    rng = np.random.default_rng(SEED)
    df = pd.DataFrame({
        "tenure":           rng.integers(1, 73, n),
        "monthly_charges":  rng.uniform(18, 120, n).round(2),
        "support_calls":    rng.poisson(1.5, n),
        "contract_month":   rng.integers(0, 2, n),
        "paperless":        rng.integers(0, 2, n),
        "internet_fiber":   rng.integers(0, 2, n),
        "extra_lines":      rng.integers(0, 4, n),
        "promo_used":       rng.integers(0, 2, n),
        "senior":           rng.integers(0, 2, n),
        "partner":          rng.integers(0, 2, n),
    })
    df["total_charges"] = (df["tenure"] * df["monthly_charges"]
                           + rng.normal(0, 80, n)).clip(lower=0)
    z = (-0.04 * df["tenure"] + 0.02 * df["monthly_charges"]
         + 0.55 * df["support_calls"]
         + 1.3 * df["contract_month"] + 0.4 * df["paperless"]
         + 0.6 * df["internet_fiber"] - 0.05 * df["extra_lines"]
         - 0.8 * df["promo_used"] + 0.3 * df["senior"] - 0.2 * df["partner"]
         + 0.6 * (df["contract_month"] * df["internet_fiber"])
         - 0.50 + rng.normal(0, 0.6, n))
    p = 1 / (1 + np.exp(-z))
    df["churn"] = (rng.uniform(0, 1, n) < p).astype(int)
    return df


def prepare(df: pd.DataFrame) -> tuple[np.ndarray, np.ndarray]:
    y = df["churn"].values.astype(np.float32)
    X = pd.get_dummies(df.drop(columns=["churn"]), drop_first=True)
    return X.values.astype(np.float32), y


class MLP(nn.Module):
    def __init__(self, d_in: int, d_h: int = 32):
        super().__init__()
        self.net = nn.Sequential(
            nn.Linear(d_in, d_h), nn.ReLU(),
            nn.Linear(d_h, d_h // 2), nn.ReLU(),
            nn.Linear(d_h // 2, 1),
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return self.net(x).squeeze(-1)


def train(X_tr, y_tr, X_va, y_va, *, lr=1e-3, epochs=60, batch=64):
    torch.manual_seed(SEED)
    m = MLP(X_tr.shape[1]).to(DEVICE)
    opt = torch.optim.AdamW(m.parameters(), lr=lr, weight_decay=1e-4)
    fn = nn.BCEWithLogitsLoss()
    Xt = torch.tensor(X_tr, dtype=torch.float32, device=DEVICE)
    yt = torch.tensor(y_tr, dtype=torch.float32, device=DEVICE)
    Xv = torch.tensor(X_va, dtype=torch.float32, device=DEVICE)
    yv = torch.tensor(y_va, dtype=torch.float32, device=DEVICE)
    hist = {"train": [], "val": []}
    n = len(Xt)
    for ep in range(epochs):
        m.train()
        idx = torch.randperm(n, device=DEVICE)
        tl = 0.0
        for i in range(0, n, batch):
            sl = idx[i:i + batch]
            opt.zero_grad()
            loss = fn(m(Xt[sl]), yt[sl])
            loss.backward(); opt.step()
            tl += loss.item() * len(sl)
        m.eval()
        with torch.no_grad():
            vl = fn(m(Xv), yv).item()
        hist["train"].append(tl / n); hist["val"].append(vl)
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
    print(f"Dataset: {df.shape}; tasa churn={df['churn'].mean():.3f}")
    X_tr, X_te, y_tr, y_te = train_test_split(X, y, test_size=0.2,
                                              random_state=SEED, stratify=y)
    sc = StandardScaler().fit(X_tr)
    X_tr_s, X_te_s = sc.transform(X_tr), sc.transform(X_te)
    lr = LogisticRegression(max_iter=2000).fit(X_tr_s, y_tr)
    p_lr = lr.predict_proba(X_te_s)[:, 1]; yh_lr = (p_lr >= 0.5).astype(int)
    m_lr = {"auc": roc_auc_score(y_te, p_lr),
            "acc": accuracy_score(y_te, yh_lr),
            "recall": recall_score(y_te, yh_lr, pos_label=1),
            "f1": f1_score(y_te, yh_lr, pos_label=1)}
    m, _ = train(X_tr_s, y_tr, X_te_s, y_te)
    m_mlp = metrics(m, X_te_s, y_te)
    print("\nMétrica       LR     MLP    Δ")
    for k in m_lr:
        print(f"  {k:>6s}    {m_lr[k]:5.3f}  {m_mlp[k]:5.3f}  {m_mlp[k]-m_lr[k]:+5.3f}")


if __name__ == "__main__":
    main()
