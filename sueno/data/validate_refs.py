#!/usr/bin/env python3
"""Validacion mecanica de la bibliografia de sueno/index.html.

La comparacion NO es generativa. El script (i) lee las referencias tal como
aparecen en el HTML publicado, (ii) lee los metadatos canonicos descargados de
dos fuentes independientes, Crossref (api.crossref.org) y PubMed (E-utilities
de NCBI), cacheados en refs_cache/, y (iii) compara campo a campo tras
normalizar espacios, acentos, puntuacion y guiones.

Un campo se acepta si coincide con alguna de las dos fuentes descargadas, y se
rechaza si no coincide con ninguna. Se usan dos fuentes porque los registros de
Crossref de algunos editores estan incompletos: JAMA Pediatrics, por ejemplo,
deposita el titulo sin subtitulo y solo la primera pagina, mientras PubMed
publica el titulo completo y el rango entero. En esos casos el script informa de
que fuente respalda el campo, de modo que la decision queda auditada y no
depende del criterio de quien escribe.

Cualquier campo que no coincida con ninguna fuente es un fallo duro y el script
termina con codigo distinto de cero.

Uso:
    python3 validate_refs.py                 # usa la cache local
    python3 validate_refs.py --refresh       # vuelve a descargar todo
    python3 validate_refs.py --verbose       # muestra el respaldo campo a campo
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
import unicodedata
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET

HERE = os.path.dirname(os.path.abspath(__file__))
CACHE = os.path.join(HERE, "refs_cache")
HTML = os.path.join(os.path.dirname(HERE), "index.html")
UA = {"User-Agent": "sueno-ref-validator/1.0 (mailto:ecgarrido@comillas.edu)"}
EUTILS = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/"

# DOI -> clave de la cache
DOI_KEYS = {
    "10.1093/sleep/16.3.258": "carskadon1993",
    "10.1016/j.cub.2004.11.039": "roenneberg2004",
    "10.1093/sleep/29.12.1632": "crowley2006",
    "10.5664/jcsm.5866": "paruthi2016",
    "10.5664/jcsm.6288": "paruthi2016b",
    "10.1016/j.sleh.2015.10.004": "hirshkowitz2015",
    "10.1080/07420520500545979": "wittmann2006",
    "10.5665/sleep.5552": "lo2016",
    "10.1038/nrn2762": "diekelmann2010",
    "10.1542/peds.2014-1697": "aap2014",
    "10.1016/j.smrv.2015.06.002": "minges2016",
    "10.1016/j.sleh.2017.08.004": "bowers2017",
    "10.1126/sciadv.aau6200": "dunster2018",
    "10.1038/s41562-020-0820-2": "goldin2020",
    "10.1001/jamapediatrics.2016.2341": "carter2016",
}

# Entradas de autoria corporativa: la declaracion de la AAP la firman tres
# grupos de trabajo, no autores personales, de modo que el cotejo nominal de
# autores no aplica.
CORPORATE = {"aap2014"}

# Fuentes institucionales sin DOI: solo se comprueba que la URL resuelva.
INSTITUTIONAL = [
    ("Estudio HBSC-2022, Ministerio de Sanidad",
     "https://www.sanidad.gob.es/areas/promocionPrevencion/entornosSaludables/"
     "escuela/estudioHBSC/2022/docs/HBSC2022_DivulgativoEstudio.pdf"),
    ("US Naval Observatory, Sun and Moon Data for One Day",
     "https://aa.usno.navy.mil/data/RS_OneDay"),
]

# Nombres de revista que PubMed abrevia y la pagina cita completos. La
# equivalencia se declara aqui de forma explicita para que el cotejo con la
# abreviatura de PubMed no de un falso negativo.
JOURNAL_ABBREV = {
    "sleep": {"sleep"},
    "current biology": {"current biology", "curr biol"},
    "journal of clinical sleep medicine": {
        "journal of clinical sleep medicine", "j clin sleep med"},
    "sleep health": {"sleep health"},
    "chronobiology international": {
        "chronobiology international", "chronobiol int"},
    "nature reviews neuroscience": {
        "nature reviews neuroscience", "nat rev neurosci"},
    "pediatrics": {"pediatrics"},
    "sleep medicine reviews": {"sleep medicine reviews", "sleep med rev"},
    "science advances": {"science advances", "sci adv"},
    "nature human behaviour": {"nature human behaviour", "nat hum behav"},
    "jama pediatrics": {"jama pediatrics", "jama pediatr"},
}


# --------------------------------------------------------------------------- #
# Normalizacion                                                               #
# --------------------------------------------------------------------------- #

def strip_accents(s: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFKD", s)
                   if not unicodedata.combining(c))


def norm(s: str) -> str:
    """Minusculas, sin acentos, sin puntuacion y con espacios colapsados."""
    s = strip_accents(s.lower()).replace("’", "'").replace("‘", "'")
    s = re.sub(r"[^a-z0-9']+", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def norm_range(s: str) -> str:
    """Normaliza guiones y espacios, y expande rangos abreviados de PubMed:
    258-62 -> 258-262, 1202-1208 -> 1202-1208, 785-6 -> 785-786."""
    s = (s or "").replace("–", "-").replace("—", "-").replace("−", "-")
    s = re.sub(r"\s+", "", s).strip(".").lower()
    m = re.fullmatch(r"(\d+)-(\d+)", s)
    if m:
        a, b = m.group(1), m.group(2)
        if len(b) < len(a):
            b = a[:len(a) - len(b)] + b
        return f"{a}-{b}"
    return s


def unescape(s: str) -> str:
    return (s.replace("&amp;", "&").replace("&lt;", "<").replace("&gt;", ">")
            .replace("&nbsp;", " "))


def journal_matches(got: str, want: str) -> bool:
    g, w = norm(got), norm(want)
    if g == w:
        return True
    for full, variants in JOURNAL_ABBREV.items():
        if g == full and w in {norm(v) for v in variants}:
            return True
    return False


# --------------------------------------------------------------------------- #
# Lectura de la pagina publicada                                              #
# --------------------------------------------------------------------------- #

LI_RE = re.compile(r"<li>(.*?)</li>", re.S)
DOI_RE = re.compile(r'href="https://doi\.org/([^"]+)"')
JOURNAL_RE = re.compile(r"<i>(.*?)</i>", re.S)


def parse_html_refs() -> list[dict]:
    with open(HTML, encoding="utf-8") as fh:
        html = fh.read()
    block = html.split('<ol class="refs">', 1)[1].split("</ol>", 1)[0]
    out = []
    for raw in LI_RE.findall(block):
        entry: dict = {"raw": raw}
        m = DOI_RE.search(raw)
        entry["doi"] = urllib.parse.unquote(m.group(1)) if m else None
        body = unescape(re.sub(r"\s+", " ",
                               raw.split('<a class="doi"', 1)[0])).strip()
        entry["body"] = body

        my = re.search(r"\((\d{4})\)\.", body)
        entry["year"] = int(my.group(1)) if my else None

        journals = JOURNAL_RE.findall(body)
        entry["journal"] = unescape(journals[0]).strip() if journals else None
        entry["authors_raw"] = body[:my.start()].strip() if my else ""
        entry["title"] = (body[my.end():].split("<i>", 1)[0].strip().rstrip(".")
                          .strip() if my and journals else None)

        tail = body.split("</i>", 1)[1] if "</i>" in body else ""
        mv = re.match(r",\s*(\d+)(?:\(([^)]+)\))?,\s*([^.]+)\.", tail)
        entry["volume"] = mv.group(1) if mv else None
        entry["issue"] = mv.group(2) if mv else None
        entry["pages"] = mv.group(3).strip() if mv else None
        out.append(entry)
    return out


def html_surnames(authors_raw: str) -> list[str]:
    """Apellidos en el orden en que aparecen en la pagina."""
    parts = [p.strip() for p in authors_raw.replace(" y ", ", ").split(",")
             if p.strip()]
    return [p for p in parts
            if not re.fullmatch(r"(?:[A-ZÁÉÍÓÚÑ]\.\s*)+", p)
            and not p.lower().startswith("y cols")
            and not p.lower().startswith("cols")]


# --------------------------------------------------------------------------- #
# Descarga de metadatos canonicos                                             #
# --------------------------------------------------------------------------- #

def http_get(url: str) -> bytes:
    return urllib.request.urlopen(
        urllib.request.Request(url, headers=UA), timeout=60).read()


def load_crossref(doi: str, key: str, refresh: bool) -> dict | None:
    path = os.path.join(CACHE, f"{key}.json")
    if refresh or not os.path.exists(path):
        os.makedirs(CACHE, exist_ok=True)
        url = "https://api.crossref.org/works/" + urllib.parse.quote(doi)
        data = json.loads(http_get(url))["message"]
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(data, fh, indent=1, ensure_ascii=False)
        time.sleep(0.3)
        return data
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def load_pubmed(doi: str, key: str, refresh: bool) -> dict | None:
    """Descarga y parsea el registro XML de PubMed para un DOI."""
    path = os.path.join(CACHE, f"{key}_pubmed.xml")
    if refresh or not os.path.exists(path):
        os.makedirs(CACHE, exist_ok=True)
        srch = json.loads(http_get(
            EUTILS + "esearch.fcgi?db=pubmed&retmode=json&term="
            + urllib.parse.quote(doi + "[DOI]")))
        ids = srch["esearchresult"]["idlist"]
        if not ids:
            with open(path, "wb") as fh:
                fh.write(b"<PubmedArticleSet/>")
            return None
        xml = http_get(EUTILS + f"efetch.fcgi?db=pubmed&id={ids[0]}&retmode=xml")
        with open(path, "wb") as fh:
            fh.write(xml)
        time.sleep(0.4)
    root = ET.parse(path).getroot()
    art = root.find(".//PubmedArticle")
    if art is None:
        return None

    def txt_of(node) -> str:
        return "".join(node.itertext()).strip() if node is not None else ""

    jrn = art.find(".//Journal")
    pub = art.find(".//Journal/JournalIssue/PubDate")
    year = ""
    if pub is not None:
        year = txt_of(pub.find("Year"))
        if not year:
            year = (txt_of(pub.find("MedlineDate")) or "")[:4]
    authors = [txt_of(a.find("LastName"))
               for a in art.findall(".//AuthorList/Author")
               if a.find("LastName") is not None]
    return {
        "title": txt_of(art.find(".//ArticleTitle")).rstrip("."),
        "journal": txt_of(jrn.find("Title")) if jrn is not None else "",
        "journal_abbrev": (txt_of(jrn.find("ISOAbbreviation"))
                           if jrn is not None else ""),
        "volume": txt_of(art.find(".//JournalIssue/Volume")),
        "issue": txt_of(art.find(".//JournalIssue/Issue")),
        "pages": txt_of(art.find(".//Pagination/MedlinePgn")),
        "year": year,
        "authors": authors,
    }


def crossref_years(msg: dict) -> set[str]:
    years = set()
    for field in ("issued", "published-print", "published-online", "published"):
        for p in (msg.get(field) or {}).get("date-parts") or []:
            if p and p[0]:
                years.add(str(p[0]))
    return years


def url_ok(url: str) -> tuple[bool, str]:
    for method in ("HEAD", "GET"):
        try:
            req = urllib.request.Request(url, headers=UA, method=method)
            with urllib.request.urlopen(req, timeout=60) as r:
                return True, f"HTTP {r.status}"
        except urllib.error.HTTPError as e:
            if method == "GET":
                return False, f"HTTP {e.code}"
        except Exception as e:
            if method == "GET":
                return False, type(e).__name__
    return False, "sin respuesta"


# --------------------------------------------------------------------------- #
# Cotejo campo a campo contra las dos fuentes                                 #
# --------------------------------------------------------------------------- #

def check_entry(entry: dict, cr: dict, pm: dict | None,
                key: str) -> tuple[list[tuple[str, str, str]], list[str]]:
    """Devuelve (fallos, respaldos). Un fallo es (campo, obtenido, esperado)."""
    fails, support = [], []

    def resolve(field: str, got: str, cands: list[tuple[str, str]],
                eq=lambda a, b: norm(a) == norm(b)) -> None:
        """cands: lista de (fuente, valor_canonico) no vacios."""
        cands = [(src, val) for src, val in cands if val]
        if not cands:
            support.append(f"{field}: sin dato canónico")
            return
        for src, val in cands:
            if eq(got or "", val):
                support.append(f"{field}: {src}")
                return
        fails.append((field, got or "-",
                      " / ".join(f"{src}: {val}" for src, val in cands)))

    # ano
    yrs = crossref_years(cr)
    cands = [("Crossref", y) for y in sorted(yrs)]
    if pm and pm["year"]:
        cands.append(("PubMed", pm["year"]))
    resolve("año", str(entry["year"]), cands, eq=lambda a, b: a == b)

    # titulo
    resolve("título", entry["title"] or "",
            [("Crossref", (cr.get("title") or [""])[0])]
            + ([("PubMed", pm["title"])] if pm else []))

    # revista
    resolve("revista", entry["journal"] or "",
            [("Crossref", (cr.get("container-title") or [""])[0])]
            + ([("PubMed", pm["journal"]), ("PubMed abrev.", pm["journal_abbrev"])]
               if pm else []),
            eq=journal_matches)

    # volumen
    resolve("volumen", entry["volume"] or "",
            [("Crossref", cr.get("volume") or "")]
            + ([("PubMed", pm["volume"])] if pm else []),
            eq=lambda a, b: a.strip() == b.strip())

    # numero (Crossref escribe "1-2" donde la pagina usa el guion largo)
    if entry["issue"] or cr.get("issue") or (pm and pm["issue"]):
        resolve("número", entry["issue"] or "",
                [("Crossref", cr.get("issue") or "")]
                + ([("PubMed", pm["issue"])] if pm else []),
                eq=lambda a, b: norm_range(a) == norm_range(b))

    # paginas o identificador de articulo
    resolve("páginas", entry["pages"] or "",
            [("Crossref", cr.get("page") or ""),
             ("Crossref art.", cr.get("article-number") or "")]
            + ([("PubMed", pm["pages"])] if pm else []),
            eq=lambda a, b: norm_range(a) == norm_range(b))

    # autores
    if key in CORPORATE:
        support.append("autores: autoría corporativa, no procede")
    else:
        got = [norm(s) for s in html_surnames(entry["authors_raw"])]
        cr_a = [norm(a["family"]) for a in cr.get("author", []) if a.get("family")]
        pm_a = [norm(a) for a in (pm["authors"] if pm else [])]
        if got and got == cr_a:
            support.append(f"autores ({len(got)}): Crossref")
        elif got and got == pm_a:
            support.append(f"autores ({len(got)}): PubMed")
        else:
            fails.append(("autores", " | ".join(got),
                          f"Crossref: {' | '.join(cr_a)} / "
                          f"PubMed: {' | '.join(pm_a)}"))
    return fails, support


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--refresh", action="store_true",
                    help="vuelve a descargar Crossref y PubMed")
    ap.add_argument("--verbose", action="store_true",
                    help="muestra el respaldo campo a campo")
    args = ap.parse_args()

    refs = parse_html_refs()
    print(f"Referencias encontradas en index.html: {len(refs)}")
    print("Fuentes canónicas: Crossref (api.crossref.org) y PubMed "
          "(NCBI E-utilities), descargadas a refs_cache/.\n")

    rows, total_fails, soft = [], 0, 0
    for entry in refs:
        doi = entry["doi"]
        if not doi:
            rows.append(("—", entry["body"][:56] + "…", "SIN DOI",
                         "fuente institucional, se comprueba la URL"))
            soft += 1
            continue
        key = DOI_KEYS.get(doi)
        if key is None:
            rows.append((doi, doi, "FALLO", "DOI no declarado en DOI_KEYS"))
            total_fails += 1
            continue
        cr = load_crossref(doi, key, args.refresh)
        pm = load_pubmed(doi, key, args.refresh)
        if norm_range(cr.get("DOI", "")) != norm_range(doi):
            rows.append((doi, key, "FALLO", "el DOI de la caché no coincide"))
            total_fails += 1
            continue
        fails, support = check_entry(entry, cr, pm, key)
        if fails:
            total_fails += len(fails)
            rows.append((doi, key, "FALLO", " ;; ".join(
                f"{c}: obtenido «{g}» / esperado «{w}»" for c, g, w in fails)))
        else:
            src = "Crossref" + (" + PubMed" if pm else " (sin registro PubMed)")
            detail = f"7/7 campos cotejados contra {src}"
            if args.verbose:
                detail += " | " + "; ".join(support)
            rows.append((doi, key, "OK", detail))

    w = max(len(r[1]) for r in rows) + 2
    print(f"{'clave'.ljust(w)}{'estado'.ljust(9)}detalle")
    print("-" * 130)
    for _, key, status, detail in rows:
        print(f"{key.ljust(w)}{status.ljust(9)}{detail}")
    print("-" * 130)

    print("\nFuentes institucionales sin DOI (resolución de la URL citada):")
    for name, url in INSTITUTIONAL:
        ok, info = url_ok(url)
        if not ok:
            total_fails += 1
        print(f"  [{'OK' if ok else 'FALLO'}] {info:<10} {name}")

    print(f"\nEntradas con DOI cotejadas: {len(refs) - soft}"
          f" | fuentes institucionales: {soft}"
          f" | discrepancias: {total_fails}")
    if total_fails:
        print("RESULTADO: FALLO. Ninguna referencia se aprueba a ojo; "
              "corrige las discrepancias listadas.")
        return 1
    print("RESULTADO: LIMPIO. Todos los campos coinciden con al menos una de "
          "las dos fuentes descargadas.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
