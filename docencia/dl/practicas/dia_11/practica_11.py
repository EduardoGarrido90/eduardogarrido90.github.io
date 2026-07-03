"""Práctica Día 11 — Cliente unificado para LLMs (Anthropic / OpenAI / Ollama).

Mide tokens, latencia y coste estimado. Misma interfaz para los tres
proveedores: cada `chat_*` devuelve (texto, n_in, n_out, latencia_s).

Las claves de las APIs cloud se leen de las variables de entorno
ANTHROPIC_API_KEY y OPENAI_API_KEY. Ollama no necesita clave (corre local).
"""
from __future__ import annotations

import argparse
import json
import os
import time
import urllib.error
import urllib.request


# Tarifas estimadas (\$ por 1M tokens input, output) a fecha 2026.
TARIFAS = {
    "claude-sonnet-4-6": (3.0, 15.0),
    "gpt-5":             (2.5, 10.0),
    "mistral-large":     (2.0,  6.0),
    "ollama":            (0.0,  0.0),
}


def _post(url: str, payload: dict, headers: dict, timeout: int = 120):
    """POST JSON y devuelve (respuesta_decodificada, latencia_s)."""
    req = urllib.request.Request(
        url, data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json", **headers})
    t0 = time.time()
    with urllib.request.urlopen(req, timeout=timeout) as r:
        data = json.loads(r.read().decode("utf-8"))
    return data, time.time() - t0


def chat_ollama(model: str, prompt: str, system: str = ""):
    """Llama a un modelo local servido por Ollama (http://localhost:11434)."""
    msgs = ([{"role": "system", "content": system}] if system else []) + [
        {"role": "user", "content": prompt}]
    payload = {"model": model, "messages": msgs, "stream": False,
               "options": {"temperature": 0.2}}
    try:
        data, latency = _post("http://localhost:11434/api/chat", payload, {})
    except urllib.error.URLError as exc:
        raise SystemExit(
            "No se pudo contactar con Ollama en localhost:11434. "
            "Arranca el servidor con 'ollama serve' y descarga el modelo "
            f"con 'ollama pull {model}'. Detalle: {exc}")
    # Ollama devuelve tokens generados; estimamos input por longitud chars/4.
    n_in = (len(system) + len(prompt)) // 4
    n_out = data.get("eval_count", len(data["message"]["content"]) // 4)
    return data["message"]["content"], n_in, n_out, latency


def chat_anthropic(model: str, prompt: str, system: str = ""):
    """Llama a la Messages API de Anthropic. Necesita ANTHROPIC_API_KEY."""
    key = os.environ.get("ANTHROPIC_API_KEY")
    if not key:
        raise SystemExit("Falta la variable de entorno ANTHROPIC_API_KEY.")
    payload = {"model": model, "max_tokens": 1024,
               "messages": [{"role": "user", "content": prompt}]}
    if system:
        payload["system"] = system
    data, latency = _post(
        "https://api.anthropic.com/v1/messages", payload,
        {"x-api-key": key, "anthropic-version": "2023-06-01"})
    text = "".join(b.get("text", "") for b in data["content"])
    usage = data.get("usage", {})
    return (text, usage.get("input_tokens", 0),
            usage.get("output_tokens", 0), latency)


def chat_openai(model: str, prompt: str, system: str = ""):
    """Llama a la Chat Completions API de OpenAI. Necesita OPENAI_API_KEY."""
    key = os.environ.get("OPENAI_API_KEY")
    if not key:
        raise SystemExit("Falta la variable de entorno OPENAI_API_KEY.")
    msgs = ([{"role": "system", "content": system}] if system else []) + [
        {"role": "user", "content": prompt}]
    data, latency = _post(
        "https://api.openai.com/v1/chat/completions",
        {"model": model, "messages": msgs},
        {"Authorization": f"Bearer {key}"})
    usage = data.get("usage", {})
    return (data["choices"][0]["message"]["content"],
            usage.get("prompt_tokens", 0),
            usage.get("completion_tokens", 0), latency)


PROVIDERS = {
    "ollama": (chat_ollama, "ollama"),
    "anthropic": (chat_anthropic, "claude-sonnet-4-6"),
    "openai": (chat_openai, "gpt-5"),
}


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--provider", choices=list(PROVIDERS), default="ollama")
    p.add_argument("--model", default=None,
                   help="Nombre del modelo; por defecto, uno típico del proveedor.")
    p.add_argument("--prompt", default="Explica en una frase qué es un RAG.")
    args = p.parse_args()

    chat_fn, default_model = PROVIDERS[args.provider]
    model = args.model or ("qwen2.5:3b" if args.provider == "ollama"
                           else default_model)
    print(f"Llamando a {args.provider} con {model}...")
    out, n_in, n_out, latency = chat_fn(
        model, args.prompt, system="Eres un consultor experto en IA.")

    # Tarifa: por nombre de modelo si existe, si no la del proveedor (Ollama=0).
    cin, cout = TARIFAS.get(model, TARIFAS.get(args.provider, (0.0, 0.0)))
    coste = (n_in / 1e6) * cin + (n_out / 1e6) * cout
    print(f"\nRespuesta:\n{out}")
    print(f"\nTokens input ~{n_in}, output ~{n_out}; "
          f"latencia {latency:.2f}s; coste ${coste:.6f}")


if __name__ == "__main__":
    main()
