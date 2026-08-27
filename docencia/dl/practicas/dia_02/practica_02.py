"""Práctica Día 02 — Tu primer MLP sobre Telco Customer Churn.

Asignatura: Deep Learning para Business Analytics — Comillas (ICADE).
Profesor: Eduardo C. Garrido-Merchán · ecgarrido@comillas.edu.

Si no tienes el CSV de Kaggle, se genera un sintético compatible.

Nota didáctica sobre el sintético: el proceso generador NO es un modelo
lineal en los log-odds. Incorpora (i) un riesgo de baja no monótono en
`tenure` (pico de onboarding + picos de renovación en el mes 12 y el 24),
(ii) un umbral sobre el precio por servicio `monthly_charges/(1+extra_lines)`,
(iii) una interacción con cambio de signo entre fibra y llamadas a soporte,
y (iv) una promoción que solo retiene en contrato mensual. Ninguna de estas
cuatro estructuras es representable por una logística sobre las features
crudas, y por eso el MLP gana de forma sistemática. Si en cambio cargas el
CSV real de Kaggle, verás que la diferencia casi desaparece: en ese dataset
la señal es prácticamente lineal y la logística es un baseline durísimo.
Ambas lecciones son parte de la práctica.
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


def load_data(csv: Path | None = None, n: int = 6000) -> pd.DataFrame:
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
        "support_calls":    rng.poisson(1.3, n),
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

    tenure = df["tenure"].to_numpy(dtype=float)
    monthly = df["monthly_charges"].to_numpy(dtype=float)
    support = df["support_calls"].to_numpy(dtype=float)
    month_to_month = df["contract_month"].to_numpy(dtype=float)
    fiber = df["internet_fiber"].to_numpy(dtype=float)
    lines = df["extra_lines"].to_numpy(dtype=float)
    promo = df["promo_used"].to_numpy(dtype=float)

    # (i) Riesgo de baja no monótono en la antigüedad: pico de onboarding en
    # los primeros meses, dos picos de renovación (mes 12 y mes 24) y una
    # deriva de fidelización a largo plazo. Una logística solo puede ajustar
    # una pendiente monótona sobre `tenure`, así que pierde los tres picos.
    onboarding = 2.4 * np.exp(-tenure / 4.5)
    renewal = (1.7 * np.exp(-((tenure - 12.0) ** 2) / 16.0)
               + 1.4 * np.exp(-((tenure - 24.0) ** 2) / 16.0))
    loyalty = -0.030 * tenure

    # (ii) Umbral sobre el precio POR SERVICIO. La feature relevante es un
    # cociente que no está en la tabla; el efecto además satura por ambos
    # lados. Ni el cociente ni la saturación son lineales en las features.
    price_per_line = monthly / (1.0 + lines)
    price_shock = 2.2 / (1.0 + np.exp(-(price_per_line - 62.0) / 5.0))

    # (iii) Interacción con CAMBIO DE SIGNO: la fibra retiene al cliente que
    # no llama a soporte y lo expulsa al que llama mucho. El efecto marginal
    # medio de `internet_fiber` es casi cero, de modo que su coeficiente
    # logístico es aproximadamente nulo y el efecto real queda invisible.
    fiber_term = fiber * (1.05 * np.minimum(support, 3.0) - 1.45)

    # (iv) La promoción solo funciona en contrato mensual; en contrato largo
    # es señal de un cliente ya insatisfecho. Otro cambio de signo.
    promo_term = -1.6 * promo * month_to_month + 0.5 * promo * (1.0 - month_to_month)

    # (v) Bloque genuinamente lineal, para que la logística tenga algo que sí
    # puede capturar y el ejercicio sea una comparación justa.
    linear = (0.85 * month_to_month
              + 0.30 * df["paperless"].to_numpy(dtype=float)
              + 0.30 * df["senior"].to_numpy(dtype=float)
              - 0.30 * df["partner"].to_numpy(dtype=float)
              + 0.45 * np.sqrt(support))

    z = (onboarding + renewal + loyalty + price_shock + fiber_term
         + promo_term + linear - 2.00 + rng.normal(0, 0.35, n))
    p = 1 / (1 + np.exp(-z))
    df["churn"] = (rng.uniform(0, 1, n) < p).astype(int)
    return df


def prepare(df: pd.DataFrame) -> tuple[np.ndarray, np.ndarray]:
    y = df["churn"].values.astype(np.float32)
    X = pd.get_dummies(df.drop(columns=["churn"]), drop_first=True)
    return X.values.astype(np.float32), y


class MLP(nn.Module):
    def __init__(self, d_in: int, d_h: int = 64):
        super().__init__()
        self.net = nn.Sequential(
            nn.Linear(d_in, d_h), nn.ReLU(),
            nn.Linear(d_h, d_h // 2), nn.ReLU(),
            nn.Linear(d_h // 2, 1),
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return self.net(x).squeeze(-1)


def train(X_tr, y_tr, X_va, y_va, *, lr=1e-3, epochs=120, batch=64):
    """Entrena el MLP y devuelve el modelo en su MEJOR época de validación.

    `X_va`/`y_va` deben ser un split de validación separado del test: se usan
    para elegir la época, y elegir con el test sería mirar la respuesta.
    """
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
    best_vl, best_state, best_ep = float("inf"), None, -1
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
        if vl < best_vl:
            best_vl, best_ep = vl, ep
            best_state = {k: v.detach().clone() for k, v in m.state_dict().items()}
    assert best_state is not None, "el entrenamiento no registró ninguna época"
    m.load_state_dict(best_state)
    hist["best_epoch"] = best_ep
    hist["best_val"] = best_vl
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
    # Tres splits: train para ajustar, val para elegir la época del MLP,
    # test intacto para medir. La logística se ajusta sobre train+val para
    # que la comparación sea justa en número de ejemplos vistos.
    X_fit, X_te, y_fit, y_te = train_test_split(X, y, test_size=0.2,
                                                random_state=SEED, stratify=y)
    X_tr, X_va, y_tr, y_va = train_test_split(X_fit, y_fit, test_size=0.2,
                                              random_state=SEED, stratify=y_fit)
    sc = StandardScaler().fit(X_tr)
    X_tr_s, X_va_s, X_te_s = (sc.transform(X_tr), sc.transform(X_va),
                              sc.transform(X_te))
    sc_lr = StandardScaler().fit(X_fit)
    lr = LogisticRegression(max_iter=2000).fit(sc_lr.transform(X_fit), y_fit)
    p_lr = lr.predict_proba(sc_lr.transform(X_te))[:, 1]
    yh_lr = (p_lr >= 0.5).astype(int)
    m_lr = {"auc": roc_auc_score(y_te, p_lr),
            "acc": accuracy_score(y_te, yh_lr),
            "recall": recall_score(y_te, yh_lr, pos_label=1),
            "f1": f1_score(y_te, yh_lr, pos_label=1)}
    m, hist = train(X_tr_s, y_tr, X_va_s, y_va)
    m_mlp = metrics(m, X_te_s, y_te)
    print(f"Mejor época del MLP: {hist['best_epoch']} "
          f"(pérdida val {hist['best_val']:.4f})")
    print("\nMétrica       LR     MLP    Δ")
    for k in m_lr:
        print(f"  {k:>6s}    {m_lr[k]:5.3f}  {m_mlp[k]:5.3f}  {m_mlp[k]-m_lr[k]:+5.3f}")


if __name__ == "__main__":
    main()
