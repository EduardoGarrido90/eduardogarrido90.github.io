#!/usr/bin/env python3
"""Comprobacion mecanica de que las afirmaciones cuantitativas de
sueno/index.html aparecen literalmente en la fuente citada.

No basta con que la referencia exista y sus metadatos sean correctos: la cifra
que la pagina atribuye a un trabajo tiene que estar en ese trabajo. Este script
declara, para cada afirmacion de la pagina, (i) la clave de la fuente, (ii) los
fragmentos que deben aparecer en el texto descargado de esa fuente y (iii) el
texto de la pagina que sostiene la afirmacion. Comprueba las dos direcciones:
que el fragmento este en la fuente y que la afirmacion siga estando en el HTML.

Los textos fuente son ficheros de refs_cache/, descargados de PubMed
(E-utilities), de PubMed Central o de la web del editor. Su procedencia se
declara en SOURCE_FILES y se registra en refs_cache/PROVENANCE.json.

Uso:
    python3 validate_claims.py               # usa la cache local
    python3 validate_claims.py --refresh     # vuelve a descargar los textos
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
import unicodedata
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET

HERE = os.path.dirname(os.path.abspath(__file__))
CACHE = os.path.join(HERE, "refs_cache")
HTML = os.path.join(os.path.dirname(HERE), "index.html")
UA = {"User-Agent": "sueno-claim-validator/1.0 (mailto:ecgarrido@comillas.edu)"}
EUTILS = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/"

# Textos fuente adicionales al resumen de PubMed, con su URL de procedencia.
# Se descargan mediante la API de PubMed Central (formato JATS), que sirve el
# texto completo de los articulos de acceso abierto.
SOURCE_FILES = {
    "dunster2018_fulltext": (
        "PMC6291308",
        EUTILS + "efetch.fcgi?db=pmc&id=6291308&retmode=xml"),
    # El resumen breve (JCSM 12(6):785-786) no deposita su cuerpo en PMC; la
    # recomendacion literal por edades y el numero de articulos revisados
    # aparecen en la declaracion de metodologia y discusion, JCSM 12(11).
    "paruthi2016b_fulltext": (
        "PMC5078711",
        EUTILS + "efetch.fcgi?db=pmc&id=5078711&retmode=xml"),
}

# (clave de fuente, fragmentos exigidos en la fuente, texto de la pagina)
CLAIMS = [
    ("carskadon1993",
     ["183 sixth-grade boys", "275 sixth-grade girls",
      "No relationship between M/E and psychosocial factors was found"],
     "183 chicos y 275 chicas de sexto curso"),
    ("carskadon1993",
     ["significant relationship of pubertal status to M/E was found in girls"],
     "se asoció de forma significativa al estadio puberal en las chicas"),
    ("crowley2006",
     ["predicted DLMO phase within +/- 1 hour", "approximately 80%"],
     "predicen el DLMO con un margen de una hora en torno al 80 % de los casos"),
    ("paruthi2016b_fulltext",
     ["Teenagers 13 to 18 years of age should sleep 8 to 10 hours per 24 hours",
      "After review of 864 published articles",
      "modified RAND Appropriateness Method"],
     "de 8 a 10 horas de sueño por cada 24 horas para los adolescentes de 13 a "
     "18 años"),
    ("paruthi2016b_fulltext",
     ["After review of 864 published articles",
      "modified RAND Appropriateness Method"],
     "tras revisar 864 artículos publicados con un método RAND modificado"),
    ("hirshkowitz2015",
     ["8-10 hours"],
     "en 8 a 10 desde los 15"),
    ("wittmann2006",
     ["501"],
     "En su muestra de 501 voluntarios"),
    ("lo2016",
     ["Fifty-six healthy adolescents", "age = 15-19 y",
      "TIB = 5 h", "7 nights of sleep opportunity manipulation"],
     "56 adolescentes sanos de 15 a 19 años"),
    ("lo2016",
     ["Subjective sleepiness and sustained attention did not return to baseline "
      "levels even after 2 recovery nights"],
     "no volvieron a los valores basales ni siquiera tras dos noches de "
     "recuperación"),
    ("lo2016",
     ["incremental deterioration in sustained attention, working memory and "
      "executive function"],
     "deterioro incremental, noche a noche, en atención sostenida, memoria de "
     "trabajo y función ejecutiva"),
    ("minges2016",
     ["Six studies satisfied selection criteria",
      "School start times were delayed 25-60 min",
      "total sleep time increased from 25 to 77 min per weeknight"],
     "El tiempo total de sueño aumentó entre 25 y 77 minutos por noche de clase"),
    ("bowers2017",
     ["five longitudinal studies and 15 cross-sectional comparison group "
      "studies", "later starting school times are associated with longer sleep "
      "durations"],
     "agrega cinco estudios longitudinales y quince comparaciones "
     "transversales"),
    ("dunster2018_fulltext",
     ["07:50 to 08:45", "34-min increase in the sleep duration median",
      "6 hours and 50 min to 7 hours and 24 min",
      "4.5% increase in the median grades"],
     "pasó de 6 horas y 50 minutos a 7 horas y 24 minutos, un incremento de 34 "
     "minutos"),
    ("dunster2018_fulltext",
     ["P = 0.0261", "P = 0.0370", "P < 0.0001"],
     "p = 0,0261"),
    ("goldin2020",
     ["753 Argentinian students", "07:45", "12:40", "17:20",
      "an effect that is largest for maths"],
     "753 estudiantes de un instituto público de Buenos Aires"),
    ("carter2016",
     ["125 198 children", "14.5", "odds ratio [OR], 2.17; 95% CI, 1.42-3.32",
      "OR, 1.46; 95% CI, 1.14-1.88", "OR, 2.72; 95% CI, 1.32-5.61",
      "OR, 1.79; 95% CI, 1.39-2.31", "OR, 1.53; 95% CI, 1.11-2.10",
      "OR, 2.27; 95% CI, 1.54-3.35"],
     "veinte estudios y 125.198 niños y adolescentes con una edad media de "
     "14,5 años"),
    ("aap2014",
     ["before 8:30 am", "8.5-9.5 hours"],
     "alcanzar entre 8,5 y 9,5 horas de sueño"),
]


def strip_accents(s: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFKD", s)
                   if not unicodedata.combining(c))


def flat(s: str) -> str:
    """Minusculas, sin acentos, sin puntuacion suave y sin separadores de
    millares, para que «125 198», «125,198» y «125.198» sean lo mismo."""
    s = strip_accents(s.lower()).replace("’", "'").replace("–", "-")
    s = s.replace("−", "-").replace("—", "-")
    s = re.sub(r"(\d)[  ,.](\d{3})\b", r"\1\2", s)
    s = re.sub(r"[^a-z0-9<>%=;:.\-'/]+", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def http_get(url: str) -> bytes:
    return urllib.request.urlopen(
        urllib.request.Request(url, headers=UA), timeout=90).read()


def pubmed_abstract(key: str) -> str:
    """Titulo + resumen del XML de PubMed que ya cachea validate_refs.py."""
    path = os.path.join(CACHE, f"{key}_pubmed.xml")
    if not os.path.exists(path):
        raise FileNotFoundError(
            f"falta {path}; ejecuta primero validate_refs.py")
    root = ET.parse(path).getroot()
    art = root.find(".//PubmedArticle")
    if art is None:
        return ""
    chunks = []
    t = art.find(".//ArticleTitle")
    if t is not None:
        chunks.append("".join(t.itertext()))
    for ab in art.findall(".//Abstract/AbstractText"):
        label = ab.get("Label")
        chunks.append((label + ": " if label else "") + "".join(ab.itertext()))
    return "\n".join(chunks)


def fulltext(key: str, refresh: bool) -> str:
    """Texto completo desde PubMed Central, cacheado en refs_cache/."""
    path = os.path.join(CACHE, f"{key}.txt")
    if refresh or not os.path.exists(path):
        pmc, url = SOURCE_FILES[key]
        raw = http_get(url).decode("utf-8", "replace")
        text = re.sub(r"<[^>]+>", " ", raw)
        text = (text.replace("&#x2212;", "-").replace("&#x2013;", "-")
                .replace("&lt;", "<").replace("&gt;", ">")
                .replace("&amp;", "&").replace("&#x00a0;", " "))
        text = re.sub(r"\s+", " ", text)
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(f"# fuente: {pmc} via {url}\n{text}")
        time.sleep(0.5)
    with open(path, encoding="utf-8") as fh:
        return fh.read()


def load_source(key: str, refresh: bool) -> str:
    return fulltext(key, refresh) if key in SOURCE_FILES \
        else pubmed_abstract(key)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--refresh", action="store_true")
    args = ap.parse_args()

    with open(HTML, encoding="utf-8") as fh:
        page = flat(re.sub(r"<[^>]+>", " ", fh.read()))

    sources: dict[str, str] = {}
    fails, checked = [], 0
    print(f"Afirmaciones declaradas: {len(CLAIMS)}\n")
    print(f"{'fuente'.ljust(24)}{'estado'.ljust(9)}afirmación de la página")
    print("-" * 118)
    for key, fragments, page_claim in CLAIMS:
        if key not in sources:
            sources[key] = flat(load_source(key, args.refresh))
        src = sources[key]
        missing = [f for f in fragments if flat(f) not in src]
        in_page = flat(page_claim) in page
        checked += len(fragments)
        if missing or not in_page:
            status = "FALLO"
            fails.append((key, missing, None if in_page else page_claim))
        else:
            status = "OK"
        print(f"{key.ljust(24)}{status.ljust(9)}{page_claim[:70]}")
        if missing:
            for m in missing:
                print(f"{' '.ljust(33)}no está en la fuente: «{m[:70]}»")
        if not in_page:
            print(f"{' '.ljust(33)}no está en index.html: «{page_claim[:70]}»")
    print("-" * 118)

    prov = {k: {"pmc": v[0], "url": v[1]} for k, v in SOURCE_FILES.items()}
    prov["_pubmed_abstracts"] = {
        "api": EUTILS + "efetch.fcgi?db=pubmed&retmode=xml",
        "files": sorted(f for f in os.listdir(CACHE) if f.endswith("_pubmed.xml"))}
    with open(os.path.join(CACHE, "PROVENANCE.json"), "w",
              encoding="utf-8") as fh:
        json.dump(prov, fh, indent=1, ensure_ascii=False)

    print(f"\nFragmentos literales comprobados: {checked} | "
          f"afirmaciones con problemas: {len(fails)}")
    if fails:
        print("RESULTADO: FALLO. Hay cifras en la página que la fuente citada "
              "no respalda literalmente.")
        return 1
    print("RESULTADO: LIMPIO. Cada cifra de la página aparece literalmente en "
          "la fuente que se le atribuye.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
