"""Práctica del Día 01 (Tema 0) — Puesta a punto y primer contacto con un agente.

Asignatura: Deep Learning para Business Analytics — Comillas (ICADE).
Profesor: Eduardo C. Garrido-Merchán · ecgarrido@comillas.edu.

Equivalente plain-Python del notebook `practica_01.ipynb`. La práctica está
diseñada como un *teaching artefact*: cada paso del pipeline reporta en
pantalla, con la paleta dignum-Comillas, qué se instala, cuánto pesa en
disco y cuánta memoria consume. Los `print()` quedan reservados al modo
sin `rich` instalado.

Uso:
    python3 practica_01.py

Requiere Ollama corriendo en `http://localhost:11434` con un modelo (p.ej.
`qwen2.5:3b`) ya descargado. Si Ollama no responde, las secciones que
dependen de él se saltan con un aviso visible, y el resto se ejecuta.
"""

from __future__ import annotations

import json
import os
import platform
import shutil
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Iterable

# rich es opcional pero recomendado: el material visual de la práctica
# depende de él. Si no está, caemos a print() sin colores.
try:
    from rich.console import Console
    from rich.panel import Panel
    from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn
    from rich.table import Table
    from rich.theme import Theme
    from rich.tree import Tree
    RICH = True
except ImportError:  # pragma: no cover
    RICH = False

# Paleta dignum-Comillas mapeada a rich (ANSI). Los hex no se renderizan en
# terminal sin truecolor, así que mapeamos a los nombres rich más cercanos.
DIGNUM = Theme({
    "ink":      "bold #1A1A1A",
    "gold":     "bold #B8860B",
    "golddeep": "bold #8C6508",
    "mute":     "#8A8A8A",
    "ok":       "bold #B8860B",
    "warn":     "bold #C36A1A",
    "err":      "bold red",
    "step":     "bold #8C6508",
    "code":     "italic #1A1A1A on #F5EBD3",
}) if RICH else None

CON = Console(theme=DIGNUM) if RICH else None

OLLAMA_URL = "http://localhost:11434"
OLLAMA_CHAT = f"{OLLAMA_URL}/api/chat"
OLLAMA_PS   = f"{OLLAMA_URL}/api/ps"
OLLAMA_TAGS = f"{OLLAMA_URL}/api/tags"
DEFAULT_MODEL = "qwen2.5:3b"


# ---------------------------------------------------------------------------
# Utilidades de presentación.
# ---------------------------------------------------------------------------
def heading(text: str) -> None:
    """Cabecera grande para una sección."""
    if RICH:
        CON.rule(f"[gold]{text}[/]", style="gold")
    else:
        print("\n" + "=" * 70)
        print(text)
        print("=" * 70)


def step(text: str) -> None:
    """Línea de paso, con marca dorada."""
    if RICH:
        CON.print(f"[step]>>>[/] {text}")
    else:
        print(f">>> {text}")


def callout(title: str, body: str) -> None:
    """Recuadro 'Idea clave' en oro."""
    if RICH:
        CON.print(Panel.fit(body, title=f"[gold]{title}[/]",
                             border_style="gold", padding=(0, 1)))
    else:
        print(f"--- {title} ---\n{body}\n")


# ---------------------------------------------------------------------------
# 1. Entorno Python — qué tenemos en el equipo.
# ---------------------------------------------------------------------------
def check_env() -> None:
    heading("Sección 1 · Inventario del entorno")
    rows = [
        ("Python", sys.version.split()[0], "ok"),
        ("OS", f"{platform.system()} {platform.release()}", "mute"),
    ]
    try:
        import numpy as np
        rows.append(("numpy", np.__version__, "ok"))
    except ImportError:
        rows.append(("numpy", "no instalado", "err"))
    try:
        import pandas as pd
        rows.append(("pandas", pd.__version__, "ok"))
    except ImportError:
        rows.append(("pandas", "no instalado", "err"))
    try:
        import torch
        cuda = "sí" if torch.cuda.is_available() else "no"
        rows.append(("PyTorch", f"{torch.__version__}  ·  CUDA: {cuda}", "ok"))
    except ImportError:
        rows.append(("PyTorch", "no instalado (Colab/Kaggle si no hay GPU)",
                     "warn"))
    try:
        import transformers
        rows.append(("transformers", transformers.__version__, "ok"))
    except ImportError:
        rows.append(("transformers", "no instalado", "warn"))

    if RICH:
        t = Table(title="Paquetes detectados", title_style="ink",
                  header_style="golddeep", show_lines=False,
                  border_style="mute")
        t.add_column("Componente", style="ink", no_wrap=True)
        t.add_column("Versión / estado", style="ink")
        for name, val, role in rows:
            t.add_row(f"[{role}]{name}[/]", f"[{role}]{val}[/]")
        CON.print(t)
    else:
        for name, val, _ in rows:
            print(f"  {name:14s} {val}")

    callout("Idea clave",
            "Si falta PyTorch o transformers, tres opciones: Colab "
            "(gratuito, T4), Kaggle (gratuito, P100), Hugging Face Spaces.")


# ---------------------------------------------------------------------------
# 2. Inventario de Ollama: qué modelos están instalados y cuánto ocupan.
# ---------------------------------------------------------------------------
def list_ollama_models() -> list[dict] | None:
    """Devuelve la lista de modelos instalados o None si Ollama no responde."""
    try:
        with urllib.request.urlopen(OLLAMA_TAGS, timeout=5) as resp:
            return json.loads(resp.read().decode("utf-8")).get("models", [])
    except Exception:  # noqa: BLE001
        return None


def list_ollama_running() -> list[dict] | None:
    """Devuelve los modelos cargados en memoria o None si Ollama no responde."""
    try:
        with urllib.request.urlopen(OLLAMA_PS, timeout=5) as resp:
            return json.loads(resp.read().decode("utf-8")).get("models", [])
    except Exception:  # noqa: BLE001
        return None


def fmt_gb(n_bytes: int) -> str:
    return f"{n_bytes / 2**30:.2f} GB"


def section_2_ollama_inventory() -> None:
    heading("Sección 2 · Inventario de Ollama (qué pesa, qué consume)")
    models = list_ollama_models()
    if models is None:
        callout("Ollama no responde",
                "No hay servidor en localhost:11434. Arranca con\n"
                "  ollama serve\n"
                "y vuelve a ejecutar esta sección.")
        return

    if not models:
        step("No tienes modelos descargados todavía.")
        step("Probemos: ollama pull qwen2.5:3b   (~2 GB en disco)")
    else:
        if RICH:
            t = Table(title="Modelos instalados en Ollama",
                      title_style="ink", header_style="golddeep",
                      border_style="mute")
            t.add_column("Nombre", style="ink", no_wrap=True)
            t.add_column("Tamaño", style="gold", justify="right")
            t.add_column("Familia", style="mute")
            t.add_column("Parámetros", style="mute", justify="right")
            for m in models:
                details = m.get("details", {}) or {}
                t.add_row(
                    m.get("name", "?"),
                    fmt_gb(m.get("size", 0)),
                    details.get("family", "?"),
                    details.get("parameter_size", "?"),
                )
            CON.print(t)
        else:
            for m in models:
                print(f"  {m.get('name')}  {fmt_gb(m.get('size', 0))}")

    running = list_ollama_running() or []
    if running:
        step(f"Modelos cargados en memoria ahora mismo: {len(running)}")
        for r in running:
            name = r.get("name", "?")
            size_vram = fmt_gb(r.get("size_vram", 0))
            step(f"  · {name}   VRAM: {size_vram}")
    else:
        step("Ningún modelo está cargado en memoria todavía "
             "(se carga la primera vez que envías un prompt).")


# ---------------------------------------------------------------------------
# 3. Hablar con Ollama. Mide latencia y tokens/segundo.
# ---------------------------------------------------------------------------
def chat_ollama(prompt: str, system: str = "",
                model: str = DEFAULT_MODEL) -> dict:
    """Llama a Ollama y devuelve {content, latency_s, tokens_out, tps}.

    Las claves de timing vienen del propio campo `eval_count` y
    `eval_duration` (ns) que reporta Ollama.
    """
    messages: list[dict] = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})
    payload = {
        "model": model,
        "messages": messages,
        "stream": False,
        "options": {"temperature": 0.2},
    }
    req = urllib.request.Request(
        OLLAMA_CHAT,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
    )
    t0 = time.perf_counter()
    with urllib.request.urlopen(req, timeout=180) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    t1 = time.perf_counter()
    tokens_out = data.get("eval_count", 0)
    eval_ns = data.get("eval_duration", 0)
    tps = (tokens_out / (eval_ns / 1e9)) if eval_ns else 0.0
    return {
        "content": data["message"]["content"],
        "latency_s": t1 - t0,
        "tokens_out": tokens_out,
        "tps": tps,
    }


def section_3_three_prompts() -> None:
    heading("Sección 3 · Tres prompts: técnica, negocio y creativa")
    triples = [
        ("Técnica",
         "Explica la diferencia entre regresión y clasificación con un ejemplo de retail.",
         "Eres profesor de Deep Learning para Business Analytics. Sé breve y preciso."),
        ("Negocio",
         "¿Cuál es el ROI típico de implantar un asistente RAG corporativo sobre 5.000 documentos legales?",
         "Eres consultor senior de IA."),
        ("Creativa",
         "Escribe un nombre para una startup que combina visión por computador y retail. Solo nombre y tagline.",
         "Eres brand-naming creativo."),
    ]
    if RICH:
        t = Table(title="Tres prompts contra el mismo modelo",
                  title_style="ink", header_style="golddeep",
                  border_style="mute", show_lines=True)
        t.add_column("Tipo", style="ink", no_wrap=True)
        t.add_column("Respuesta del modelo", style="ink", overflow="fold")
        t.add_column("Latencia", justify="right", style="mute")
        t.add_column("tokens/s", justify="right", style="gold")
        for label, prompt, system in triples:
            try:
                r = chat_ollama(prompt, system=system)
            except (urllib.error.URLError, ConnectionError, KeyError):
                CON.print(f"[err]Skip {label}[/]: Ollama no responde.")
                continue
            short = (r["content"][:240] + "…") if len(r["content"]) > 240 else r["content"]
            t.add_row(label, short, f"{r['latency_s']:.1f} s",
                       f"{r['tps']:.1f}")
        CON.print(t)
    else:
        for label, prompt, system in triples:
            try:
                r = chat_ollama(prompt, system=system)
                print(f"\n--- {label}  ({r['latency_s']:.1f}s, "
                      f"{r['tps']:.1f} tok/s) ---")
                print(r["content"])
            except (urllib.error.URLError, ConnectionError, KeyError) as e:
                print(f"Skip {label}: {e}")


# ---------------------------------------------------------------------------
# 4. Dataset placeholder con instrumentación de tamaño y memoria.
# ---------------------------------------------------------------------------
def section_4_dataset() -> None:
    heading("Sección 4 · Dataset placeholder y su huella en memoria")
    try:
        import numpy as np
        import pandas as pd
    except ImportError:
        callout("Falta numpy/pandas",
                "pip install numpy pandas")
        return
    rng = np.random.default_rng(0)
    n = 200_000
    df = pd.DataFrame({
        "producto": rng.choice(["A", "B", "C", "D"], size=n),
        "precio":   rng.uniform(5, 200, size=n).round(2),
        "unidades": rng.poisson(3, size=n),
    })
    mem_mb = df.memory_usage(deep=True).sum() / 1024**2
    if RICH:
        t = Table(title=f"DataFrame placeholder · {n:,} filas",
                  title_style="ink", header_style="golddeep",
                  border_style="mute")
        t.add_column("Columna", style="ink")
        t.add_column("dtype", style="mute")
        t.add_column("Mem (MB)", style="gold", justify="right")
        for col in df.columns:
            t.add_row(col, str(df[col].dtype),
                       f"{df[col].memory_usage(deep=True)/1024**2:.2f}")
        t.add_row("[golddeep]TOTAL[/]", "",
                  f"[golddeep]{mem_mb:.2f}[/]")
        CON.print(t)
    else:
        print(df.dtypes)
        print(f"Total: {mem_mb:.2f} MB")

    callout("Sustitúyelo",
            "Esto es un placeholder. En el ejercicio 4.1 carga un dataset real "
            "(Online Retail II, Telco Churn, Airbnb Madrid o EuroSAT) y reporta "
            "su tamaño exacto.")


# ---------------------------------------------------------------------------
# 5. Reflexión personal (indelegable, sólo print de las preguntas).
# ---------------------------------------------------------------------------
def section_5_reflection() -> None:
    heading("Sección 5 · Reflexión personal (no delegable)")
    qs = [
        "¿Qué te resultó más fácil de lo que esperabas, y qué más difícil?",
        "Con 100 €/mes de presupuesto: ¿API cloud o GPU local con open source? Justifica.",
        "Plantea un caso de negocio del semestre: problema, KPI y arquitectura candidata.",
    ]
    if RICH:
        for i, q in enumerate(qs, 1):
            CON.print(f"[step]{i}.[/] {q}")
    else:
        for i, q in enumerate(qs, 1):
            print(f"{i}. {q}")


# ---------------------------------------------------------------------------
# Resumen final del pipeline.
# ---------------------------------------------------------------------------
def final_summary() -> None:
    heading("Resumen del pipeline montado hoy")
    if RICH:
        tree = Tree("[gold]Stack de la asignatura[/]")
        py = tree.add(f"[ink]Python {sys.version.split()[0]}[/]")
        py.add("[mute]numpy · pandas · matplotlib[/]")
        py.add("[mute]rich (UI) · psutil (memoria)[/]")
        ol = tree.add("[golddeep]Ollama (servidor local)[/]")
        models = list_ollama_models() or []
        if models:
            for m in models:
                ol.add(f"[gold]{m.get('name')}[/]  ([mute]{fmt_gb(m.get('size', 0))}[/])")
        else:
            ol.add("[warn](sin modelos descargados — ollama pull qwen2.5:3b)[/]")
        ag = tree.add("[ink]Agente CLI[/]")
        ag.add("[mute]Claude Code (cloud)[/]")
        ag.add("[mute]opencode (gratis, sobre Ollama)[/]")
        CON.print(tree)
    else:
        print("Stack: Python + Ollama + agente CLI (Claude Code u opencode).")
    callout("Cierre del Día 01",
            "Pipeline gratuito listo. Mañana entramos en redes neuronales "
            "(Tema 1). Recuerda rellenar la sección 6 del notebook con la "
            "declaración de uso de IA.")


def main() -> None:
    check_env()
    section_2_ollama_inventory()
    section_3_three_prompts()
    section_4_dataset()
    section_5_reflection()
    final_summary()


if __name__ == "__main__":
    main()
