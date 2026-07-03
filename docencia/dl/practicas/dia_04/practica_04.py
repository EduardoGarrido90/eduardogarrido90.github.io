"""Práctica Día 04 — Tu primera CNN con transfer learning sobre Fashion-MNIST.

Asignatura: Deep Learning para Business Analytics — Comillas (ICADE).

Si torchvision falla la descarga de Fashion-MNIST, usa el archivo local
señalado en --data. Comparamos un MLP plano vs una CNN simple, en CPU si no
hay GPU. Para una práctica completa con ResNet preentrenada, ver el notebook.
"""
from __future__ import annotations

import argparse
import time
from pathlib import Path

import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as F
from torch.utils.data import DataLoader, TensorDataset

SEED = 0
DEVICE = "cuda" if torch.cuda.is_available() else "cpu"


def load_fashion(root: Path) -> tuple[torch.Tensor, torch.Tensor, torch.Tensor, torch.Tensor]:
    """Carga Fashion-MNIST con torchvision; cae a sintético si no se puede descargar."""
    try:
        from torchvision import datasets, transforms
        tfm = transforms.ToTensor()
        tr = datasets.FashionMNIST(root, train=True, download=True, transform=tfm)
        te = datasets.FashionMNIST(root, train=False, download=True, transform=tfm)
        Xtr = torch.stack([x for x, _ in tr]); ytr = torch.tensor([y for _, y in tr])
        Xte = torch.stack([x for x, _ in te]); yte = torch.tensor([y for _, y in te])
        return Xtr, ytr, Xte, yte
    except Exception as exc:  # noqa: BLE001
        print(f"[fallback] No se pudo descargar Fashion-MNIST ({exc}). Sintético.")
        rng = np.random.default_rng(SEED)
        Xtr = torch.tensor(rng.uniform(0, 1, (2000, 1, 28, 28)).astype(np.float32))
        ytr = torch.tensor(rng.integers(0, 10, 2000))
        Xte = torch.tensor(rng.uniform(0, 1, (500, 1, 28, 28)).astype(np.float32))
        yte = torch.tensor(rng.integers(0, 10, 500))
        return Xtr, ytr, Xte, yte


class MLP(nn.Module):
    def __init__(self):
        super().__init__()
        self.net = nn.Sequential(
            nn.Flatten(), nn.Linear(28 * 28, 128), nn.ReLU(),
            nn.Linear(128, 10),
        )

    def forward(self, x): return self.net(x)


class SimpleCNN(nn.Module):
    def __init__(self):
        super().__init__()
        self.conv = nn.Sequential(
            nn.Conv2d(1, 16, 3, padding=1), nn.BatchNorm2d(16), nn.ReLU(),
            nn.MaxPool2d(2),
            nn.Conv2d(16, 32, 3, padding=1), nn.BatchNorm2d(32), nn.ReLU(),
            nn.MaxPool2d(2),
        )
        self.head = nn.Sequential(
            nn.Flatten(), nn.Linear(32 * 7 * 7, 128), nn.ReLU(),
            nn.Dropout(0.3), nn.Linear(128, 10),
        )

    def forward(self, x): return self.head(self.conv(x))


def train(model, Xtr, ytr, Xte, yte, *, epochs=5, batch=128, lr=1e-3):
    torch.manual_seed(SEED)
    model = model.to(DEVICE)
    loader = DataLoader(TensorDataset(Xtr, ytr), batch_size=batch, shuffle=True)
    opt = torch.optim.AdamW(model.parameters(), lr=lr, weight_decay=1e-4)
    fn = nn.CrossEntropyLoss()
    for ep in range(epochs):
        model.train()
        tl = 0.0
        for xb, yb in loader:
            xb, yb = xb.to(DEVICE), yb.to(DEVICE)
            opt.zero_grad()
            loss = fn(model(xb), yb)
            loss.backward(); opt.step()
            tl += loss.item() * len(xb)
        with torch.no_grad():
            model.eval()
            yh = model(Xte.to(DEVICE)).argmax(-1).cpu()
            acc = (yh == yte).float().mean().item()
        print(f"  epoch {ep+1:>2d}: loss={tl/len(Xtr):.4f}  test_acc={acc:.3f}")
    return acc


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--data", type=Path, default=Path("~/.cache/fashion").expanduser())
    p.add_argument("--epochs", type=int, default=5)
    args = p.parse_args()
    args.data.mkdir(parents=True, exist_ok=True)
    print(f"Device: {DEVICE}")
    Xtr, ytr, Xte, yte = load_fashion(args.data)
    print(f"Train: {Xtr.shape}  Test: {Xte.shape}")

    t0 = time.time()
    print("\n--- MLP plano ---")
    acc_mlp = train(MLP(), Xtr, ytr, Xte, yte, epochs=args.epochs)
    t_mlp = time.time() - t0

    t0 = time.time()
    print("\n--- CNN simple ---")
    acc_cnn = train(SimpleCNN(), Xtr, ytr, Xte, yte, epochs=args.epochs)
    t_cnn = time.time() - t0

    print(f"\nResumen: MLP acc={acc_mlp:.3f} ({t_mlp:.1f}s); "
          f"CNN acc={acc_cnn:.3f} ({t_cnn:.1f}s); Δ={acc_cnn - acc_mlp:+.3f}")


if __name__ == "__main__":
    main()
