"""Práctica Día 14 — Cliente MCP de filesystem y orquestador simple.

Como no se puede asumir que el alumno tenga un servidor MCP corriendo, este
script simula los mensajes JSON intercambiados y deja como ejercicio configurar
el servidor real (instrucciones en el notebook).
"""
from __future__ import annotations

import json


# Simulación de una sesión de tool_use con dos llamadas en cadena
def simulate():
    transcript = [
        {"role": "user",
         "content": "Resume el archivo data/online_retail.parquet y dime las 3 categorías más vendidas."},
        {"role": "assistant",
         "tool_call": {"name": "filesystem.read_csv",
                       "args": {"path": "data/online_retail.parquet"}}},
        {"role": "tool",
         "name": "filesystem.read_csv",
         "content": {"rows": 1067371, "cols": 9, "head": "..."}},
        {"role": "assistant",
         "tool_call": {"name": "filesystem.run",
                       "args": {"cmd": "python -c 'import pandas as pd; "
                                       "d=pd.read_parquet(\"data/online_retail.parquet\"); "
                                       "print(d.groupby(\"Description\")[\"Quantity\"].sum()"
                                       ".nlargest(3))'"}}},
        {"role": "tool",
         "name": "filesystem.run",
         "content": {"stdout": "WHITE HANGING HEART T-LIGHT HOLDER  82918\n"
                                "REGENCY CAKESTAND 3 TIER          77910\n"
                                "JUMBO BAG RED RETROSPOT           70000\n",
                     "stderr": ""}},
        {"role": "assistant",
         "content": "Las 3 categorías más vendidas en Online Retail II son: "
                    "T-light holder corazón blanco (82 918 ud), Cake stand 3 niveles "
                    "(77 910), Jumbo bag retro red (70 000)."},
    ]
    for turn in transcript:
        print(json.dumps(turn, indent=2, ensure_ascii=False))
        print("---")


if __name__ == "__main__":
    simulate()
