"""Práctica Día 18 — Generar el checklist AI Act del proyecto AI-first.

Plantilla en markdown con los puntos clave del Reglamento.
"""
from __future__ import annotations

from pathlib import Path

CHECKLIST = """\
# Checklist AI Act — Proyecto AI-first

**Sistema:** ___ (nombre del grupo)
**Caso:** ___ (descripción 1 línea)
**Nivel de riesgo (AI Act):** Mínimo / Limitado / Alto / Inaceptable

## Documentación obligatoria

- [ ] Memoria técnica (arquitectura, datos, evaluación) — Art. 11.
- [ ] Documentación del dataset (origen, calidad, derechos) — Art. 10.
- [ ] Registro automático de operaciones (logs) — Art. 12.
- [ ] Aviso de transparencia al usuario — Art. 13.
- [ ] Plan de supervisión humana (HITL) — Art. 14.
- [ ] Tests de robustez y ciberseguridad — Art. 15.

## Riesgos identificados y mitigación

| Riesgo | Probabilidad | Impacto | Mitigación |
|---|---|---|---|
| Alucinación | media | alto | RAG con cita verificable |
| Prompt injection | media | medio | Sanitización + sandbox |
| Fuga de PII | baja | crítico | ABAC + redacción de logs |
| Sesgo / discriminación | baja | crítico | Evaluación por subgrupos |
| Dependencia de proveedor | alta | medio | Plan B con Ollama local |

## Decisión final

- [ ] Sistema es **desplegable** según el Reglamento.
- [ ] Sistema requiere **modificaciones** antes del despliegue.
- [ ] Sistema NO debe desplegarse.

## Firma del equipo y fecha

___
"""


def main():
    out = Path("CHECKLIST_AI_ACT.md")
    if out.exists():
        print(f"{out} ya existe.")
        return
    out.write_text(CHECKLIST, encoding="utf-8")
    print(f"Escrito {out}.")


if __name__ == "__main__":
    main()
