"""Práctica Día 13 — Crear un CLAUDE.md y pedir al agente que documente tu repo.

Este script no entrena ni invoca Claude Code directamente (depende del CLI del
alumno). Genera la plantilla de CLAUDE.md y ofrece los comandos a ejecutar.
"""
from __future__ import annotations

import argparse
from pathlib import Path

TEMPLATE = """\
# CLAUDE.md — guía para el agente

## Rol

Eres el asistente técnico de un proyecto de Business Analytics para la
asignatura Deep Learning del Bachelor in Business Analytics (Comillas).

## Convenciones

- Código Python 3.10+, type hints obligatorios, formateo con black.
- Tests con pytest, ubicados en `tests/`.
- Docstrings de Google style, máximo 5 líneas.
- No instalar librerías nuevas sin proponerlo y esperar OK explícito.

## Restricciones

- No tocar `docker-compose.yml` ni `Dockerfile` sin aprobación.
- No subir secretos. Si encuentras tokens, marca como TODO y avisa.
- No correr migraciones de base de datos.

## Contexto del proyecto

- Dataset principal: `data/online_retail.parquet`.
- Modelo base: `scripts/train.py`.
- Entorno: venv en `.venv/`, requirements en `requirements.txt`.

## Política de uso de IA

- Declara en cada commit con prefijo `ai:` si usaste IA.
- Conserva los prompts relevantes en `prompts/`.
- Cualquier resultado debe poder defenderse oralmente.
"""


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--out", type=Path, default=Path("CLAUDE.md"))
    args = p.parse_args()
    if args.out.exists():
        print(f"{args.out} ya existe. No lo sobrescribo.")
        return
    args.out.write_text(TEMPLATE, encoding="utf-8")
    print(f"Escrito {args.out} ({len(TEMPLATE)} caracteres).")
    print("\nAhora abre tu proyecto y lanza una de estas opciones:")
    print("  claude                                  # Anthropic CLI")
    print("  opencode --model ollama/qwen2.5-coder:7b  # libre")
    print("\nPrimera tarea sugerida al agente:")
    print('  "Lee mi repo entero. Produce un README.md con: estructura,')
    print('   propósito, cómo correrlo, principales decisiones técnicas."')


if __name__ == "__main__":
    main()
