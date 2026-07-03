"""Práctica Día 17 — Esqueleto de orquestador con fallbacks.

Implementa un mini-orquestador con dos "subagentes" mock que devuelven
resultados deterministas, y aplica los cinco patrones de fallback del Día 17.
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field


@dataclass
class Session:
    budget: float = 0.5
    spent: float = 0.0
    history: list[dict] = field(default_factory=list)


def fake_llm(call: dict, latency_ms: int = 250, cost: float = 0.008) -> dict:
    time.sleep(latency_ms / 1000.0)
    return {"text": f"respuesta a {call['prompt'][:30]}...",
            "cost": cost, "latency": latency_ms}


def fake_rag(query: str) -> list[tuple[float, str]]:
    if "hipoteca" in query.lower():
        return [(0.92, "Comisión apertura 0,5 % (Circular 23)"),
                (0.81, "Plazo máximo 30 años (Circular 47)")]
    return [(0.20, "Sin documentos relevantes.")]


def orchestrator(question: str, sess: Session) -> str:
    # routing
    sess.spent += 0.0001
    if sess.spent > sess.budget:
        return "[fallback: budget] sesión cancelada por coste."
    # RAG con fallback low-score
    chunks = fake_rag(question)
    if chunks[0][0] < 0.4:
        return "[fallback: low-score] no encontré información relevante."
    sess.spent += 0.001
    # LLM con timeout simulado y loop detector
    for _ in range(3):
        out = fake_llm({"prompt": question, "chunks": chunks},
                        latency_ms=300, cost=0.012)
        sess.spent += out["cost"]
        if sess.spent > sess.budget:
            return "[fallback: budget] coste superado en LLM."
        # éxito
        return f"{out['text']} (coste sesión: ${sess.spent:.4f})"
    return "[fallback: loop] no se pudo cerrar la respuesta."


def main():
    s = Session()
    print(orchestrator("¿Comisión de la hipoteca fija?", s))
    print(orchestrator("¿Cuánto cuesta el café del despacho?", Session()))


if __name__ == "__main__":
    main()
