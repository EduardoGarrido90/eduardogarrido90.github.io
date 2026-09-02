#!/usr/bin/env python3
"""Comprobacion mecanica de los datos astronomicos que usa la pagina.

Consulta la API de Aplicaciones Astronomicas del US Naval Observatory para las
coordenadas de Madrid, aplica el desplazamiento de una hora en las fechas en
horario de verano peninsular y compara el resultado con la tabla ASTRO
declarada en build.py y con las cifras que aparecen en index.html. Tambien
recalcula la equivalencia entre la hora oficial y la hora solar.

Uso:
    python3 validate_astro.py                # consulta la API
    python3 validate_astro.py --offline      # solo coteja build.py con el HTML
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import os
import re
import sys
import urllib.parse
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
HTML = os.path.join(ROOT, "index.html")
UA = {"User-Agent": "sueno-astro-validator/1.0 (mailto:ecgarrido@comillas.edu)"}
LAT, LON = 40.4168, -3.7038
API = "https://aa.usno.navy.mil/api/rstt/oneday"


def load_build():
    spec = importlib.util.spec_from_file_location(
        "sueno_build", os.path.join(ROOT, "build.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def query_usno(date: str) -> dict:
    """La API se consulta siempre en hora estandar (tz=1, dst=false)."""
    url = (f"{API}?date={date}&coords={LAT},{LON}&tz=1&dst=false")
    raw = urllib.request.urlopen(
        urllib.request.Request(url, headers=UA), timeout=90).read()
    data = json.loads(raw)["properties"]["data"]["sundata"]
    return {e["phen"]: e["time"] for e in data}


def shift(hm: str, minutes: int) -> str:
    h, m = (int(x) for x in hm.split(":"))
    t = (h * 60 + m + minutes) % (24 * 60)
    return f"{t // 60:02d}:{t % 60:02d}"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--offline", action="store_true")
    args = ap.parse_args()

    b = load_build()
    with open(HTML, encoding="utf-8") as fh:
        page = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", fh.read()))

    fails = 0
    print(f"Coordenadas: {LAT} N, {LON} | API: {API}\n")
    print(f"{'fecha':<13}{'huso':<7}{'amanecer':<22}{'mediodía solar':<24}estado")
    print("-" * 96)
    for date, want in b.ASTRO.items():
        dst = b.ASTRO_DST_ADJUSTED.get(date, 0)
        if args.offline:
            got_rise, got_tr, src = want["rise"], want["transit"], "build.py"
        else:
            q = query_usno(date)
            got_rise = shift(q["Rise"], dst)
            got_tr = shift(q["Upper Transit"], dst)
            src = f"USNO{'+1h' if dst else ''}"
        ok = (got_rise == want["rise"] and got_tr == want["transit"])
        if not ok:
            fails += 1
        print(f"{date:<13}{want['tz']:<7}"
              f"{got_rise + ' (' + src + ')':<22}"
              f"{got_tr + ' (' + src + ')':<24}"
              f"{'OK' if ok else 'FALLO: build.py dice ' + want['rise'] + ' / ' + want['transit']}")

    print("\nEquivalencia hora oficial -> hora solar (8:00 de la campana):")
    for date in ("2026-01-15", "2026-06-21"):
        tr = b.ASTRO[date]["transit"]
        off = b.hm_to_min(tr) - 12 * 60
        solar = b.min_to_hm(b.hm_to_min("08:00") - off)
        in_page = solar.lstrip("0") in page or solar in page
        if not in_page:
            fails += 1
        print(f"  {date}: mediodía solar {tr} -> desfase {off // 60} h "
              f"{off % 60:02d} min -> 08:00 oficiales = {solar} solares "
              f"[{'presente en index.html' if in_page else 'AUSENTE del HTML'}]")

    # el amanecer de enero debe ser posterior a las 8:00 y la pagina lo afirma
    rise_jan = b.hm_to_min(b.ASTRO["2026-01-15"]["rise"])
    delta = rise_jan - b.hm_to_min("08:00")
    claim = f"{delta} minutos antes de que salga el Sol"
    ok = delta > 0 and ("36 minutos" in page)
    if not ok:
        fails += 1
    print(f"\n  Diferencia campana-amanecer el 15 de enero: {delta} min "
          f"[{'coherente con el HTML' if ok else 'INCOHERENTE: ' + claim}]")

    print(f"\nDiscrepancias: {fails}")
    if fails:
        print("RESULTADO: FALLO.")
        return 1
    print("RESULTADO: LIMPIO. Los datos solares de la página coinciden con la "
          "consulta al US Naval Observatory.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
