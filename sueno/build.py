#!/usr/bin/env python3
"""Genera sueno/index.html: pagina divulgativa autocontenida sobre el desajuste
entre el reloj circadiano adolescente y la campana escolar de las 8:00.

Todas las figuras se emiten como SVG en linea a partir de los diccionarios de
datos declarados abajo. Las cifras de origen estan cacheadas en
data/refs_cache/ (Crossref + PubMed) y en data/astro_madrid.json (US Naval
Observatory), y la bibliografia se comprueba con data/validate_refs.py.

Uso:  python3 build.py            # escribe index.html junto a este fichero
"""

from __future__ import annotations

import json
import math
import os
from typing import Sequence

HERE = os.path.dirname(os.path.abspath(__file__))

# --------------------------------------------------------------------------- #
# Paleta dignum-Comillas                                                      #
# --------------------------------------------------------------------------- #
INK = "#1A1A1A"
GOLD = "#B8860B"
GOLD_DEEP = "#8C6508"
GOLD_PALE = "#F5EBD3"
MUTE = "#8A8A8A"
RULE = "#D9C28A"
PAPER = "#FFFFFF"
GREY_L = "#C9C9C9"
GREY_M = "#A3A3A3"

SERIF = ('"Linux Libertine O","Libertinus Serif","Linux Libertine",'
         'Georgia,"Times New Roman",serif')

# --------------------------------------------------------------------------- #
# DATOS                                                                       #
# --------------------------------------------------------------------------- #

# Estudio HBSC-2022 en Espana, n = 33.630 adolescentes de 11 a 18 anos.
# Tablas 19 (entre semana) y 20 (fin de semana) del informe divulgativo.
HBSC_CATS = ["5 h o menos", "6 h", "7 h", "8 h", "9 h", "10 h o más"]

HBSC_WEEKDAY = {          # Tabla 19, %
    "11-12": [3.4, 5.9, 12.4, 34.2, 30.8, 13.3],
    "13-14": [6.8, 11.3, 26.1, 36.3, 15.5, 4.0],
    "15-16": [9.9, 19.6, 33.8, 28.5, 6.6, 1.6],
    "17-18": [15.5, 27.3, 33.7, 18.7, 3.5, 1.2],
}
HBSC_WEEKEND = {          # Tabla 20, %
    "11-12": [4.9, 4.7, 9.1, 14.9, 25.9, 40.5],
    "13-14": [6.7, 5.9, 9.2, 15.0, 28.9, 34.4],
    "15-16": [5.5, 4.6, 8.1, 17.9, 32.4, 31.6],
    "17-18": [4.8, 4.9, 9.5, 26.6, 31.5, 22.7],
}
HBSC_TOTAL_WEEKDAY = [9.0, 16.1, 26.7, 29.4, 13.9, 4.9]   # Tabla 19, Total


def pct_at_least_8h(row: Sequence[float]) -> float:
    """Suma de las categorias 8 h, 9 h y 10 h o mas."""
    return round(row[3] + row[4] + row[5], 1)


def pct_at_most_7h(row: Sequence[float]) -> float:
    """Suma de las categorias 5 h o menos, 6 h y 7 h."""
    return round(row[0] + row[1] + row[2], 1)


def es(v: float, dec: int = 1) -> str:
    """Formatea un numero con coma decimal, como corresponde en espanol."""
    return f"{v:.{dec}f}".replace(".", ",")


# Datos astronomicos para Madrid (40.4168 N, 3.7038 W) en hora del reloj
# oficial espanol. Fuente: US Naval Observatory, AA API rstt/oneday.
ASTRO = {
    "2026-01-15": {"tz": "UTC+1", "rise": "08:36", "transit": "13:24"},
    "2026-04-15": {"tz": "UTC+2", "rise": "07:37", "transit": "14:15"},
    "2026-06-21": {"tz": "UTC+2", "rise": "06:45", "transit": "14:17"},
    "2026-12-21": {"tz": "UTC+1", "rise": "08:34", "transit": "13:13"},
}
# La API se consulta con tz=1 y dst=false; a las fechas en horario de verano se
# les suma una hora para expresarlas en la hora del reloj oficial.
ASTRO_DST_ADJUSTED = {"2026-04-15": 60, "2026-06-21": 60}

# Metaanalisis de Carter et al. (2016), JAMA Pediatrics: 20 estudios,
# 125.198 ninos y adolescentes (edad media 14,5 anos).
CARTER = [
    ("Uso del dispositivo al acostarse", "Sueño insuficiente", 2.17, 1.42, 3.32),
    ("Uso del dispositivo al acostarse", "Mala calidad del sueño", 1.46, 1.14, 1.88),
    ("Uso del dispositivo al acostarse", "Somnolencia diurna excesiva", 2.72, 1.32, 5.61),
    ("Solo acceso, sin uso declarado", "Sueño insuficiente", 1.79, 1.39, 2.31),
    ("Solo acceso, sin uso declarado", "Mala calidad del sueño", 1.53, 1.11, 2.10),
    ("Solo acceso, sin uso declarado", "Somnolencia diurna excesiva", 2.27, 1.54, 3.35),
]

# --------------------------------------------------------------------------- #
# Utilidades SVG                                                              #
# --------------------------------------------------------------------------- #


def xml_esc(s: str) -> str:
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def txt(x: float, y: float, s: str, size: float = 13, fill: str = INK,
        anchor: str = "start", weight: str = "normal", style: str = "normal",
        spacing: str = "0") -> str:
    return (f'<text x="{x:.1f}" y="{y:.1f}" font-family=\'{SERIF}\' '
            f'font-size="{size}" fill="{fill}" text-anchor="{anchor}" '
            f'font-weight="{weight}" font-style="{style}" '
            f'letter-spacing="{spacing}">{xml_esc(s)}</text>')


def svg_open(w: float, h: float, label: str) -> str:
    """Abre un SVG con width/height explicitos para fijar la razon de aspecto
    intrinseca; el tamano final lo controla el CSS (width:100%, height:auto)."""
    return (f'<svg viewBox="0 0 {w:.0f} {h:.0f}" width="{w:.0f}" '
            f'height="{h:.0f}" preserveAspectRatio="xMidYMid meet" role="img" '
            f'aria-label="{xml_esc(label)}" xmlns="http://www.w3.org/2000/svg">')


def hm_to_min(hm: str) -> int:
    h, m = hm.split(":")
    return int(h) * 60 + int(m)


def min_to_hm(t: int) -> str:
    t = int(round(t)) % (24 * 60)
    return f"{t // 60:02d}:{t % 60:02d}"


# --------------------------------------------------------------------------- #
# FIGURA 1. Esquema del desajuste                                             #
# --------------------------------------------------------------------------- #

def fig_desajuste() -> str:
    W, H = 860, 348
    L, R = 168, 44
    T0 = hm_to_min("21:00")           # origen de la linea temporal
    SPAN = 12 * 60                    # 21:00 -> 09:00

    def P(hm: str) -> int:
        """Minutos desde el origen, resolviendo el paso por medianoche."""
        m = hm_to_min(hm)
        return m + 24 * 60 if m < T0 else m

    def X(t: int) -> float:
        return L + (t - T0) / SPAN * (W - L - R)

    s = [svg_open(W, H, "Esquema del desajuste entre la ventana de sueño "
                        "recomendada, el sueño real y la campana escolar de las "
                        "ocho de la mañana")]

    y_top, y_bot = 68, 250
    s.append(f'<rect x="{X(T0):.1f}" y="{y_top}" width="{X(T0+SPAN)-X(T0):.1f}" '
             f'height="{y_bot-y_top}" fill="{GOLD_PALE}" opacity="0.32"/>')

    # marcadores verticales
    marks = [("07:00", MUTE, 1.0), ("08:00", INK, 2.0), ("08:36", GOLD, 1.4)]
    for hm, col, wd in marks:
        x = X(P(hm))
        s.append(f'<line x1="{x:.1f}" y1="{y_top-16}" x2="{x:.1f}" '
                 f'y2="{y_bot}" stroke="{col}" stroke-width="{wd}" '
                 f'stroke-dasharray="5 3"/>')
        s.append(txt(x, y_top - 22, hm, 12.5, col, "middle", "bold"))

    # barras
    rows = [
        ("Recomendación", "22:00", "07:00", GOLD, 96,
         "8-10 h (AASM, 13-18 años): exige acostarse hacia las 22:00-23:00"),
        ("Sueño real", "00:00", "07:00", GOLD_DEEP, 168,
         "7 h: categoría modal a los 17-18 años en España (33,7 %)"),
    ]
    hgt = 34
    for label, a, b, col, y, note in rows:
        xa, xb = X(P(a)), X(P(b))
        s.append(f'<rect x="{xa:.1f}" y="{y}" width="{xb-xa:.1f}" height="{hgt}" '
                 f'fill="{col}" opacity="0.9" rx="2"/>')
        s.append(txt(L - 14, y + 22, label, 14, INK, "end", "bold"))
        s.append(txt(xa + 8, y + hgt + 18, note, 12, MUTE))

    # deficit: tramo de la recomendacion que el sueno real no cubre
    xa, xb = X(P("22:00")), X(P("00:00"))
    s.append(f'<rect x="{xa:.1f}" y="168" width="{xb-xa:.1f}" height="{hgt}" '
             f'fill="none" stroke="{GOLD_DEEP}" stroke-width="1.2" '
             f'stroke-dasharray="4 3"/>')
    s.append(txt((xa + xb) / 2, 189, "déficit", 12.5, GOLD_DEEP, "middle",
                 style="italic"))

    # eje
    yax = 268
    s.append(f'<line x1="{X(T0):.1f}" y1="{yax}" x2="{X(T0+SPAN):.1f}" y2="{yax}" '
             f'stroke="{INK}" stroke-width="0.8"/>')
    for k in range(0, 13):
        t = T0 + k * 60
        s.append(f'<line x1="{X(t):.1f}" y1="{yax}" x2="{X(t):.1f}" y2="{yax+5}" '
                 f'stroke="{MUTE}" stroke-width="0.8"/>')
        s.append(txt(X(t), yax + 19, min_to_hm(t), 12, MUTE, "middle"))

    s.append(txt(L - 14, 34, "Esquema", 12.5, GOLD, "end", "bold", spacing="0.6"))
    s.append(txt(L, 34, "las horas de inicio y fin son ilustrativas; las "
                        "duraciones proceden de las fuentes citadas", 12, MUTE))
    s.append(txt(L - 14, 320,
                 "07:00 despertar   ·   08:00 campana escolar   ·   "
                 "08:36 amanece en Madrid (15 de enero)", 12.5, INK, "start"))
    s.append("</svg>")
    return "\n".join(s)


# --------------------------------------------------------------------------- #
# FIGURA 2. Distribucion de horas de sueno entre semana (barras apiladas)     #
# --------------------------------------------------------------------------- #

def fig_hbsc_weekday() -> str:
    W, H = 860, 396
    L, R, T = 118, 34, 74
    bar_h, gap = 42, 34
    seg_cols = [GOLD_DEEP, GOLD, RULE, GREY_L, GREY_M, INK]
    dark = {GOLD_DEEP, GREY_M, INK}

    s = [svg_open(W, H, "Distribución del número de horas de sueño entre semana "
                        "por grupo de edad en España, 2022")]
    plot_w = W - L - R

    lx = L
    for cat, col in zip(HBSC_CATS, seg_cols):
        s.append(f'<rect x="{lx}" y="24" width="11" height="11" fill="{col}"/>')
        s.append(txt(lx + 16, 34, cat, 12, INK))
        lx += 16 + 6.4 * len(cat) + 16

    for i, (age, row) in enumerate(HBSC_WEEKDAY.items()):
        y = T + i * (bar_h + gap)
        x = L
        for v, col in zip(row, seg_cols):
            w = v / 100 * plot_w
            s.append(f'<rect x="{x:.1f}" y="{y}" width="{w:.2f}" height="{bar_h}" '
                     f'fill="{col}"/>')
            if v >= 6:
                s.append(txt(x + w / 2, y + bar_h / 2 + 4.5, es(v), 12,
                             PAPER if col in dark else INK, "middle"))
            x += w
        s.append(txt(L - 12, y + bar_h / 2 + 5, f"{age} años", 13.5, INK, "end",
                     "bold"))
        xb = L + pct_at_most_7h(row) / 100 * plot_w
        s.append(f'<line x1="{xb:.1f}" y1="{y-6}" x2="{xb:.1f}" y2="{y+bar_h+6}" '
                 f'stroke="{INK}" stroke-width="1.8"/>')
        s.append(txt(xb, y - 12, f"{es(pct_at_most_7h(row))} % duerme 7 h o menos",
                     12.5, INK, "middle", "bold"))

    ybase = T + 4 * (bar_h + gap) - gap + 10
    s.append(f'<line x1="{L}" y1="{ybase}" x2="{W-R}" y2="{ybase}" '
             f'stroke="{RULE}" stroke-width="1"/>')
    for p in (0, 25, 50, 75, 100):
        anchor = "middle" if 0 < p < 100 else ("start" if p == 0 else "end")
        s.append(txt(L + p / 100 * plot_w, ybase + 20, f"{p} %", 12, MUTE, anchor))
    s.append("</svg>")
    return "\n".join(s)


# --------------------------------------------------------------------------- #
# FIGURA 3. 8 h o mas: entre semana frente a fin de semana                    #
# --------------------------------------------------------------------------- #

def fig_weekday_vs_weekend() -> str:
    W, H = 860, 410
    L, R, T, B = 72, 34, 62, 96
    plot_w, plot_h = W - L - R, H - T - B
    ages = list(HBSC_WEEKDAY.keys())

    def Y(v: float) -> float:
        return T + plot_h - v / 100 * plot_h

    s = [svg_open(W, H, "Porcentaje de adolescentes que duerme ocho horas o más, "
                        "entre semana frente a fin de semana, por grupo de edad")]
    for v in range(0, 101, 20):
        s.append(f'<line x1="{L}" y1="{Y(v):.1f}" x2="{W-R}" y2="{Y(v):.1f}" '
                 f'stroke="{RULE}" stroke-width="0.6" opacity="0.75"/>')
        s.append(txt(L - 10, Y(v) + 4, f"{v} %", 12, MUTE, "end"))

    group_w = plot_w / len(ages)
    bw = 54
    for i, age in enumerate(ages):
        cx = L + group_w * (i + 0.5)
        wd = pct_at_least_8h(HBSC_WEEKDAY[age])
        we = pct_at_least_8h(HBSC_WEEKEND[age])
        for j, (v, col) in enumerate(((wd, GOLD_DEEP), (we, MUTE))):
            x = cx - bw - 5 + j * (bw + 10)
            s.append(f'<rect x="{x:.1f}" y="{Y(v):.1f}" width="{bw}" '
                     f'height="{plot_h - (Y(v)-T):.1f}" fill="{col}" '
                     f'opacity="{0.92 if j == 0 else 0.42}"/>')
            s.append(txt(x + bw / 2, Y(v) - 9, f"{es(v)} %", 13.5,
                         GOLD_DEEP if j == 0 else INK, "middle", "bold"))
        s.append(txt(cx, T + plot_h + 24, f"{age} años", 14, INK, "middle", "bold"))

    s.append(f'<line x1="{L}" y1="{T+plot_h:.1f}" x2="{W-R}" y2="{T+plot_h:.1f}" '
             f'stroke="{INK}" stroke-width="0.9"/>')

    s.append(f'<rect x="{L}" y="24" width="12" height="12" fill="{GOLD_DEEP}" '
             f'opacity="0.92"/>')
    s.append(txt(L + 18, 34, "Días de clase", 13, INK))
    s.append(f'<rect x="{L+150}" y="24" width="12" height="12" fill="{MUTE}" '
             f'opacity="0.42"/>')
    s.append(txt(L + 168, 34, "Fin de semana", 13, INK))

    s.append(txt(L, T + plot_h + 58,
                 "El fin de semana la proporción se mantiene en torno al 80 % en "
                 "todas las edades.", 13, INK))
    s.append(txt(L, T + plot_h + 78,
                 "Entre semana se hunde del 78,3 % a los 11-12 años al 23,4 % a "
                 "los 17-18: la capacidad de dormir no cambia, lo que cambia es "
                 "el horario.", 13, GOLD_DEEP))
    s.append("</svg>")
    return "\n".join(s)


# --------------------------------------------------------------------------- #
# FIGURA 4. Reloj oficial frente a reloj solar en Madrid                      #
# --------------------------------------------------------------------------- #

def fig_solar() -> str:
    W, H = 860, 336
    L, R = 126, 150
    t0, t1 = hm_to_min("05:00"), hm_to_min("15:00")

    def X(t: int) -> float:
        return L + (t - t0) / (t1 - t0) * (W - L - R)

    rows = [("15 de enero", "2026-01-15", 98), ("21 de junio", "2026-06-21", 182)]
    s = [svg_open(W, H, "Hora oficial frente a hora solar en Madrid: amanecer y "
                        "mediodía solar en enero y en junio")]
    s.append(txt(L - 12, 34, "Madrid (40,42 N; 3,70 O). Horas del reloj oficial. "
                             "Fuente: US Naval Observatory.", 12.5, MUTE, "start"))

    for name, key, y in rows:
        a = ASTRO[key]
        rise, transit = hm_to_min(a["rise"]), hm_to_min(a["transit"])
        offset = transit - 12 * 60
        s.append(txt(L - 14, y + 20, name, 14, INK, "end", "bold"))
        s.append(txt(L - 14, y + 37, a["tz"], 12, MUTE, "end"))
        s.append(f'<rect x="{X(t0):.1f}" y="{y}" width="{X(rise)-X(t0):.1f}" '
                 f'height="30" fill="{INK}" opacity="0.82"/>')
        s.append(f'<rect x="{X(rise):.1f}" y="{y}" width="{X(t1)-X(rise):.1f}" '
                 f'height="30" fill="{GOLD_PALE}"/>')
        s.append(f'<rect x="{X(t0):.1f}" y="{y}" width="{X(t1)-X(t0):.1f}" '
                 f'height="30" fill="none" stroke="{RULE}" stroke-width="0.8"/>')
        s.append(f'<line x1="{X(rise):.1f}" y1="{y-7}" x2="{X(rise):.1f}" '
                 f'y2="{y+37}" stroke="{GOLD}" stroke-width="1.5"/>')
        s.append(txt(X(rise), y - 12, f"amanece {a['rise']}", 12.5, GOLD_DEEP,
                     "middle", "bold"))
        s.append(f'<circle cx="{X(transit):.1f}" cy="{y+15}" r="4.5" '
                 f'fill="{GOLD_DEEP}"/>')
        s.append(txt(X(transit) + 11, y + 19, f"mediodía solar {a['transit']}",
                     12.5, GOLD_DEEP, "start"))
        bell = hm_to_min("08:00")
        s.append(f'<line x1="{X(bell):.1f}" y1="{y-7}" x2="{X(bell):.1f}" '
                 f'y2="{y+37}" stroke="{INK}" stroke-width="2.2"/>')
        s.append(txt(X(bell), y + 54,
                     f"08:00 oficiales = {min_to_hm(bell - offset)} solares",
                     12.5, INK, "middle", "bold"))

    yax = 264
    s.append(f'<line x1="{X(t0):.1f}" y1="{yax}" x2="{X(t1):.1f}" y2="{yax}" '
             f'stroke="{INK}" stroke-width="0.8"/>')
    for hh in range(5, 16):
        t = hh * 60
        s.append(f'<line x1="{X(t):.1f}" y1="{yax}" x2="{X(t):.1f}" y2="{yax+5}" '
                 f'stroke="{MUTE}" stroke-width="0.8"/>')
        s.append(txt(X(t), yax + 19, f"{hh:02d}:00", 12, MUTE, "middle"))
    s.append(f'<rect x="{L}" y="298" width="12" height="12" fill="{INK}" '
             f'opacity="0.82"/>')
    s.append(txt(L + 18, 308, "noche", 12.5, INK))
    s.append(txt(L + 78, 308,
                 "En enero la campana suena 36 minutos antes de que salga el Sol.",
                 12.5, GOLD_DEEP))
    s.append("</svg>")
    return "\n".join(s)


# --------------------------------------------------------------------------- #
# FIGURA 5. Sueno ganado al retrasar la campana                               #
# --------------------------------------------------------------------------- #

def fig_gain() -> str:
    W, H = 860, 224
    L, R, T = 280, 76, 74
    xmax = 90

    def X(v: float) -> float:
        return L + v / xmax * (W - L - R)

    s = [svg_open(W, H, "Minutos de sueño ganados por noche escolar al retrasar "
                        "la hora de entrada")]
    s.append(txt(L - 14, 34, "minutos de sueño ganados por noche de clase", 12.5,
                 MUTE, "start"))
    for v in range(0, xmax + 1, 15):
        s.append(f'<line x1="{X(v):.1f}" y1="{T-18}" x2="{X(v):.1f}" y2="176" '
                 f'stroke="{RULE}" stroke-width="0.6"/>')
        s.append(txt(X(v), 194, f"+{v}", 12, MUTE, "middle"))

    items = [
        ("Minges y Redeker (2016)",
         "6 estudios experimentales, retrasos de 25-60 min", 25.0, 77.0, None, T),
        ("Dunster et al. (2018)", "Seattle, 07:50 → 08:45, actigrafía",
         None, None, 34.0, T + 62),
    ]
    for label, sub, lo, hi, point, y in items:
        s.append(txt(L - 16, y + 6, label, 13.5, INK, "end", "bold"))
        s.append(txt(L - 16, y + 23, sub, 11.5, MUTE, "end"))
        if lo is not None:
            s.append(f'<rect x="{X(lo):.1f}" y="{y-9}" width="{X(hi)-X(lo):.1f}" '
                     f'height="26" fill="{GOLD}" opacity="0.55" rx="2"/>')
            s.append(txt((X(lo) + X(hi)) / 2, y + 9, "+25 a +77 min", 13, INK,
                         "middle", "bold"))
        if point is not None:
            s.append(f'<rect x="{X(0):.1f}" y="{y-9}" width="{X(point)-X(0):.1f}" '
                     f'height="26" fill="{GOLD_DEEP}" opacity="0.85" rx="2"/>')
            s.append(txt(X(point) + 12, y + 9, "+34 min", 13, GOLD_DEEP, "start",
                         "bold"))
    s.append(f'<line x1="{X(0):.1f}" y1="{T-18}" x2="{X(0):.1f}" y2="176" '
             f'stroke="{INK}" stroke-width="1.1"/>')
    s.append("</svg>")
    return "\n".join(s)


# --------------------------------------------------------------------------- #
# FIGURA 6. Pantallas: razones de probabilidad de Carter et al. (2016)        #
# --------------------------------------------------------------------------- #

def fig_carter() -> str:
    W, H = 860, 386
    L, R, T = 288, 178, 92
    row_h, grp_gap = 30, 30
    lo_x, hi_x = 0.92, 6.4

    def X(v: float) -> float:
        return (L + (math.log(v) - math.log(lo_x))
                / (math.log(hi_x) - math.log(lo_x)) * (W - L - R))

    y_end = T + 2 * grp_gap + 6 * row_h
    s = [svg_open(W, H, "Gráfico de bosque con las razones de probabilidad de "
                        "sueño insuficiente, mala calidad del sueño y somnolencia "
                        "diurna asociadas al uso o al acceso a dispositivos "
                        "móviles al acostarse")]
    s.append(txt(L - 16, 36, "razón de probabilidad (OR) con intervalo de "
                             "confianza al 95 %", 12.5, MUTE, "end"))
    for v in (1, 1.5, 2, 3, 4, 6):
        first = v == 1
        s.append(f'<line x1="{X(v):.1f}" y1="{T-24}" x2="{X(v):.1f}" '
                 f'y2="{y_end+6:.0f}" stroke="{INK if first else RULE}" '
                 f'stroke-width="{1.4 if first else 0.6}"/>')
        s.append(txt(X(v), y_end + 26, es(v, 0 if float(v).is_integer() else 1),
                     12, INK if first else MUTE, "middle",
                     "bold" if first else "normal"))
    s.append(txt(X(1), T - 32, "sin asociación", 11.5, INK, "middle",
                 style="italic"))

    prev, y = None, T
    for group, outcome, or_, lo, hi in CARTER:
        if group != prev:
            if prev is not None:
                y += 8
            s.append(txt(L - 16, y + 4, group, 13, GOLD_DEEP, "end", "bold"))
            y += grp_gap - 8 if prev is None else grp_gap - 8
            prev = group
        col = GOLD_DEEP if group.startswith("Uso") else MUTE
        yc = y + row_h / 2
        s.append(f'<line x1="{X(lo):.1f}" y1="{yc:.1f}" x2="{X(hi):.1f}" '
                 f'y2="{yc:.1f}" stroke="{col}" stroke-width="1.6"/>')
        for e in (lo, hi):
            s.append(f'<line x1="{X(e):.1f}" y1="{yc-6:.1f}" x2="{X(e):.1f}" '
                     f'y2="{yc+6:.1f}" stroke="{col}" stroke-width="1.6"/>')
        s.append(f'<circle cx="{X(or_):.1f}" cy="{yc:.1f}" r="5.5" fill="{col}"/>')
        s.append(txt(L - 16, yc + 4.5, outcome, 12.5, INK, "end"))
        s.append(txt(W - 14, yc + 4.5,
                     f"{es(or_, 2)}  [{es(lo, 2)} – {es(hi, 2)}]", 11.5, MUTE,
                     "end"))
        y += row_h
    s.append(f'<line x1="{L-4}" y1="{y_end+6}" x2="{W-R+8}" y2="{y_end+6}" '
             f'stroke="{INK}" stroke-width="0.8"/>')
    s.append("</svg>")
    return "\n".join(s)


# --------------------------------------------------------------------------- #
# Componentes HTML                                                            #
# --------------------------------------------------------------------------- #

SECTIONS = [
    ("reloj", "El reloj"),
    ("deuda", "La deuda"),
    ("prueba", "La prueba"),
    ("espana", "España"),
    ("coste", "El coste"),
    ("evidencia", "La evidencia"),
    ("pantallas", "Las pantallas"),
    ("fuentes", "Las fuentes"),
]


def figure(svg: str, num: str, visual: str, quant: str, take: str) -> str:
    return f"""<figure class="fig">
  <div class="fig-plate">{svg}</div>
  <p class="swipe">Desliza horizontalmente para ver la figura completa.</p>
  <figcaption>
    <span class="fig-num">Figura {num}</span>
    <span class="cap"><span class="cap-k">Visual.</span> {visual}</span>
    <span class="cap"><span class="cap-k">Cuantitativo.</span> {quant}</span>
    <span class="cap"><span class="cap-k">Conclusión.</span> {take}</span>
  </figcaption>
</figure>"""


REFS = [
    ("Carskadon, M. A., Vieira, C. y Acebo, C. (1993). Association between "
     "puberty and delayed phase preference. <i>Sleep</i>, 16(3), 258–262.",
     "https://doi.org/10.1093/sleep/16.3.258"),
    ("Roenneberg, T., Kuehnle, T., Pramstaller, P. P., Ricken, J., Havel, M., "
     "Guth, A. y Merrow, M. (2004). A marker for the end of adolescence. "
     "<i>Current Biology</i>, 14(24), R1038–R1039.",
     "https://doi.org/10.1016/j.cub.2004.11.039"),
    ("Crowley, S. J., Acebo, C., Fallone, G. y Carskadon, M. A. (2006). "
     "Estimating dim light melatonin onset (DLMO) phase in adolescents using "
     "summer or school-year sleep/wake schedules. <i>Sleep</i>, 29(12), "
     "1632–1641.", "https://doi.org/10.1093/sleep/29.12.1632"),
    ("Paruthi, S., Brooks, L. J., D’Ambrosio, C., Hall, W. A., Kotagal, S., "
     "Lloyd, R. M., Malow, B. A., Maski, K., Nichols, C., Quan, S. F., Rosen, "
     "C. L., Troester, M. M. y Wise, M. S. (2016). Recommended amount of sleep "
     "for pediatric populations: a consensus statement of the American Academy "
     "of Sleep Medicine. <i>Journal of Clinical Sleep Medicine</i>, 12(6), "
     "785–786.", "https://doi.org/10.5664/jcsm.5866"),
    ("Paruthi, S., Brooks, L. J., D’Ambrosio, C., Hall, W. A., Kotagal, S., "
     "Lloyd, R. M., Malow, B. A., Maski, K., Nichols, C., Quan, S. F., Rosen, "
     "C. L., Troester, M. M. y Wise, M. S. (2016). Consensus statement of the "
     "American Academy of Sleep Medicine on the recommended amount of sleep "
     "for healthy children: methodology and discussion. <i>Journal of Clinical "
     "Sleep Medicine</i>, 12(11), 1549–1561.",
     "https://doi.org/10.5664/jcsm.6288"),
    ("Hirshkowitz, M., Whiton, K., Albert, S. M., Alessi, C., Bruni, O., "
     "DonCarlos, L., Hazen, N., Herman, J., Adams Hillard, P. J., Katz, E. S., "
     "Kheirandish-Gozal, L., Neubauer, D. N., O’Donnell, A. E., Ohayon, M., "
     "Peever, J., Rawding, R., Sachdeva, R. C., Setters, B., Vitiello, M. V. y "
     "Ware, J. C. (2015). National Sleep Foundation’s updated sleep duration "
     "recommendations: final report. <i>Sleep Health</i>, 1(4), 233–243.",
     "https://doi.org/10.1016/j.sleh.2015.10.004"),
    ("Moreno, C., Rivera, F., Sánchez-Queija, I. y cols. (2025). "
     "<i>La adolescencia española analizada desde el Estudio HBSC-2022: "
     "estilos de vida, contextos de desarrollo y bienestar emocional</i>. "
     "Informe divulgativo de los resultados más significativos obtenidos. "
     "Ministerio de Sanidad. Tablas 19 y 20; n = 33.630 adolescentes de 11 a "
     "18 años.",
     "https://www.sanidad.gob.es/areas/promocionPrevencion/entornosSaludables/"
     "escuela/estudioHBSC/2022/docs/HBSC2022_DivulgativoEstudio.pdf"),
    ("Wittmann, M., Dinich, J., Merrow, M. y Roenneberg, T. (2006). Social "
     "jetlag: misalignment of biological and social time. <i>Chronobiology "
     "International</i>, 23(1–2), 497–509.",
     "https://doi.org/10.1080/07420520500545979"),
    ("Lo, J. C., Ong, J. L., Leong, R. L. F., Gooley, J. J. y Chee, M. W. L. "
     "(2016). Cognitive performance, sleepiness, and mood in partially sleep "
     "deprived adolescents: the Need for Sleep Study. <i>Sleep</i>, 39(3), "
     "687–698.", "https://doi.org/10.5665/sleep.5552"),
    ("Diekelmann, S. y Born, J. (2010). The memory function of sleep. "
     "<i>Nature Reviews Neuroscience</i>, 11(2), 114–126.",
     "https://doi.org/10.1038/nrn2762"),
    ("Adolescent Sleep Working Group, Committee on Adolescence y Council on "
     "School Health (2014). School start times for adolescents. "
     "<i>Pediatrics</i>, 134(3), 642–649.",
     "https://doi.org/10.1542/peds.2014-1697"),
    ("Minges, K. E. y Redeker, N. S. (2016). Delayed school start times and "
     "adolescent sleep: a systematic review of the experimental evidence. "
     "<i>Sleep Medicine Reviews</i>, 28, 86–95.",
     "https://doi.org/10.1016/j.smrv.2015.06.002"),
    ("Bowers, J. M. y Moyer, A. (2017). Effects of school start time on "
     "students’ sleep duration, daytime sleepiness, and attendance: a "
     "meta-analysis. <i>Sleep Health</i>, 3(6), 423–431.",
     "https://doi.org/10.1016/j.sleh.2017.08.004"),
    ("Dunster, G. P., de la Iglesia, L., Ben-Hamo, M., Nave, C., Fleischer, "
     "J. G., Panda, S. y de la Iglesia, H. O. (2018). Sleepmore in Seattle: "
     "later school start times are associated with more sleep and better "
     "performance in high school students. <i>Science Advances</i>, 4(12), "
     "eaau6200.", "https://doi.org/10.1126/sciadv.aau6200"),
    ("Goldin, A. P., Sigman, M., Braier, G., Golombek, D. A. y Leone, M. J. "
     "(2020). Interplay of chronotype and school timing predicts school "
     "performance. <i>Nature Human Behaviour</i>, 4(4), 387–396.",
     "https://doi.org/10.1038/s41562-020-0820-2"),
    ("Carter, B., Rees, P., Hale, L., Bhattacharjee, D. y Paradkar, M. S. "
     "(2016). Association between portable screen-based media device access or "
     "use and sleep outcomes: a systematic review and meta-analysis. "
     "<i>JAMA Pediatrics</i>, 170(12), 1202–1208.",
     "https://doi.org/10.1001/jamapediatrics.2016.2341"),
    ("US Naval Observatory, Astronomical Applications Department. "
     "<i>Sun and Moon Data for One Day</i> (API rstt/oneday). Consultas para "
     "Madrid (40,4168 N; −3,7038) en las fechas citadas.",
     "https://aa.usno.navy.mil/data/RS_OneDay"),
]


def build_html() -> str:
    f1, f2, f3 = fig_desajuste(), fig_hbsc_weekday(), fig_weekday_vs_weekend()
    f4, f5, f6 = fig_solar(), fig_gain(), fig_carter()

    nav = "".join(f'<a href="#{sid}" data-sec="{sid}">{name}</a>'
                  for sid, name in SECTIONS)
    refs = "".join(
        f'<li>{body} <a class="doi" href="{url}" target="_blank" '
        f'rel="noopener">'
        f'{url.replace("https://doi.org/", "doi: ").replace("https://", "")}'
        f'</a></li>' for body, url in REFS)

    d17_wd = pct_at_least_8h(HBSC_WEEKDAY["17-18"])
    d17_we = pct_at_least_8h(HBSC_WEEKEND["17-18"])
    d1112_wd = pct_at_least_8h(HBSC_WEEKDAY["11-12"])
    le7 = {a: pct_at_most_7h(r) for a, r in HBSC_WEEKDAY.items()}

    table_rows = "".join(
        f'<tr><td>{cat}</td>'
        + "".join(f'<td class="num">{es(HBSC_WEEKDAY[a][i])}</td>'
                  for a in HBSC_WEEKDAY)
        + f'<td class="num">{es(HBSC_TOTAL_WEEKDAY[i])}</td></tr>'
        for i, cat in enumerate(HBSC_CATS))

    return f"""<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>¿Por qué tus alumnos están dormidos a las 8 de la mañana?</title>
<meta name="description" content="Por qué los adolescentes están dormidos a
primera hora: el retraso circadiano de la pubertad, los datos del Estudio
HBSC-2022 en España, la anomalía horaria española y la evidencia experimental
sobre retrasar la hora de entrada.">
<meta name="author" content="Eduardo C. Garrido-Merchán">
<style>
:root{{
  --ink:{INK}; --gold:{GOLD}; --gold-deep:{GOLD_DEEP};
  --gold-pale:{GOLD_PALE}; --mute:{MUTE}; --rule:{RULE}; --paper:{PAPER};
}}
*{{box-sizing:border-box}}
html{{scroll-behavior:smooth; -webkit-text-size-adjust:100%}}
body{{
  margin:0; background:var(--paper); color:var(--ink);
  font-family:{SERIF};
  font-size:18px; line-height:1.62; text-rendering:optimizeLegibility;
}}
a{{color:var(--gold-deep); text-decoration:none;
  border-bottom:1px solid var(--rule)}}
a:hover{{color:var(--gold); border-bottom-color:var(--gold)}}
.wrap{{max-width:1080px; margin:0 auto; padding:0 1.4rem}}

/* ---------- navegación ---------- */
nav{{
  position:sticky; top:0; z-index:50; background:rgba(255,255,255,.96);
  backdrop-filter:saturate(140%) blur(6px);
  border-bottom:1px solid var(--rule);
}}
nav .strip{{
  max-width:1080px; margin:0 auto; padding:.7rem 1.4rem;
  display:flex; flex-wrap:wrap; gap:.15rem 1.5rem;
  font-size:.79rem; letter-spacing:.09em; text-transform:uppercase;
}}
nav a{{color:var(--mute); border:0}}
nav a:hover{{color:var(--gold-deep)}}
nav a.on{{color:var(--gold); font-weight:700}}

/* ---------- portada ---------- */
header.hero{{padding:4.4rem 0 2.2rem}}
.kicker{{
  font-size:.8rem; letter-spacing:.22em; text-transform:uppercase;
  color:var(--gold); font-weight:700; margin-bottom:1.1rem;
}}
h1{{
  font-size:clamp(2.15rem,5.4vw,4rem); line-height:1.08; margin:0 0 1.1rem;
  font-weight:700; letter-spacing:-.012em; max-width:24ch;
}}
h1 em{{font-style:italic; color:var(--gold-deep)}}
.hr-gold{{border:0; border-top:1.4px solid var(--gold); margin:1.5rem 0;
  max-width:7rem}}
.standfirst{{font-size:1.16rem; max-width:64ch; margin:0 0 1.2rem}}
.byline{{font-size:.94rem; color:var(--mute); font-style:italic}}

/* ---------- cifras de portada ---------- */
.stats{{
  display:grid; grid-template-columns:repeat(4,1fr); gap:1px;
  background:var(--rule); border:1px solid var(--rule);
  margin:2.6rem 0 3.4rem;
}}
.stat{{background:var(--paper); padding:1.5rem 1.2rem}}
.stat b{{
  display:block; font-size:2.5rem; line-height:1; color:var(--gold-deep);
  font-weight:700; letter-spacing:-.02em;
}}
.stat span{{display:block; margin-top:.55rem; font-size:.88rem}}
.stat i{{display:block; margin-top:.35rem; font-size:.76rem; color:var(--mute);
  font-style:italic}}

/* ---------- cuerpo ---------- */
main{{padding-bottom:4rem}}
section{{padding:2.6rem 0 1rem; border-top:1px solid var(--rule)}}
section:first-of-type{{border-top:0}}
h2{{
  font-size:clamp(1.5rem,2.9vw,2.1rem); line-height:1.16; margin:0 0 .35rem;
  font-weight:700; letter-spacing:-.008em; max-width:34ch;
}}
h2 .n{{
  display:inline-block; font-size:.74rem; letter-spacing:.2em;
  color:var(--gold); vertical-align:.9rem; margin-right:.7rem; font-weight:700;
}}
h2 + .rule{{border:0; border-top:.9px solid var(--gold); margin:.9rem 0 1.5rem}}
p{{max-width:76ch; margin:0 0 1.15rem}}
.lead::first-letter{{
  float:left; font-size:3.6rem; line-height:.82; padding:.14em .12em 0 0;
  color:var(--gold-deep); font-weight:700;
}}
.pull{{
  margin:2rem 0; padding:1.1rem 0 1.1rem 1.5rem;
  border-left:3px solid var(--gold); font-size:1.18rem; max-width:62ch;
}}
.pull cite{{display:block; margin-top:.6rem; font-size:.85rem;
  color:var(--mute); font-style:italic}}
.two{{display:grid; grid-template-columns:1.05fr .95fr; gap:2.6rem;
  align-items:start}}
.aside{{
  background:var(--gold-pale); padding:1.3rem 1.4rem; font-size:.95rem;
  border-top:2px solid var(--gold);
}}
.aside h3{{margin:0 0 .6rem; font-size:1rem; letter-spacing:.04em;
  text-transform:uppercase; color:var(--gold-deep)}}
.aside p{{margin:0 0 .7rem; max-width:none}}
.aside p:last-child{{margin:0}}

/* ---------- figuras ---------- */
.fig{{margin:2.2rem 0 2.6rem}}
.fig-plate{{
  border:1px solid var(--rule); border-top:2.5px solid var(--gold);
  padding:1.1rem .9rem .6rem; background:var(--paper);
}}
.fig svg{{display:block; width:100%; height:auto; max-width:100%}}
figcaption{{margin-top:.85rem; font-size:.83rem; color:var(--mute);
  line-height:1.5}}
.fig-num{{
  display:block; font-size:.72rem; letter-spacing:.2em;
  text-transform:uppercase; color:var(--gold); font-weight:700;
  margin-bottom:.4rem;
}}
.cap{{display:block; margin-bottom:.22rem}}
.cap-k{{font-variant:small-caps; letter-spacing:.05em; color:var(--ink);
  font-weight:700}}
.swipe{{display:none}}

/* ---------- tabla ---------- */
.tablebox{{overflow-x:auto}}
table{{border-collapse:collapse; width:100%; min-width:34rem; font-size:.92rem;
  margin:1.4rem 0 1rem}}
caption{{
  caption-side:top; text-align:left; font-size:.83rem; color:var(--mute);
  padding-bottom:.6rem; font-style:italic;
}}
th{{
  text-align:left; padding:.55rem .7rem; border-bottom:1.4px solid var(--gold);
  font-weight:700; font-size:.86rem; letter-spacing:.03em;
}}
td{{padding:.5rem .7rem; border-bottom:1px solid #EEE7D6}}
tbody tr:nth-child(odd) td{{background:var(--gold-pale)}}
td.num, th.num{{text-align:right; font-variant-numeric:tabular-nums}}

/* ---------- referencias ---------- */
ol.refs{{padding-left:1.6rem; font-size:.92rem}}
ol.refs li{{margin-bottom:.85rem; line-height:1.5}}
a.doi{{font-size:.82rem; color:var(--mute);
  border-bottom:1px dotted var(--rule); word-break:break-word}}
.method{{
  border:1px solid var(--rule); padding:1.2rem 1.4rem; margin:2rem 0 0;
  font-size:.9rem; background:#FDFCF8;
}}
.method h3{{margin:0 0 .6rem; font-size:.82rem; letter-spacing:.18em;
  text-transform:uppercase; color:var(--gold-deep)}}
.method p{{max-width:none; margin:0 0 .7rem}}
.method p:last-child{{margin:0}}
code{{font-size:.86em; background:var(--gold-pale); padding:.05em .3em}}

footer{{
  border-top:1px solid var(--rule); margin-top:2rem;
  padding:2.4rem 1.4rem 3.4rem; text-align:center;
}}
footer .rule2{{border:0; border-top:1.2px solid var(--gold); max-width:5rem;
  margin:1.2rem auto}}
footer p{{max-width:none; margin:.3rem 0; font-size:.9rem; color:var(--mute)}}
footer .name{{color:var(--ink); font-size:1.02rem}}

@media (max-width:700px){{
  body{{font-size:16.5px}}
  .stats{{grid-template-columns:repeat(2,1fr)}}
  .two{{grid-template-columns:1fr; gap:1.6rem}}
  header.hero{{padding-top:2.6rem}}
  nav .strip{{gap:.1rem .95rem; font-size:.72rem}}
  .lead::first-letter{{font-size:3rem}}
  .fig-plate{{padding:.6rem .4rem .3rem; overflow-x:auto}}
  .fig svg{{min-width:640px; max-width:none}}
  .stat b{{font-size:2rem; white-space:nowrap}}
  .swipe{{display:block; font-size:.74rem; color:var(--mute);
    font-style:italic; margin:.35rem 0 0}}
  .pull{{font-size:1.06rem}}
}}
</style>
</head>
<body>

<nav><div class="strip">{nav}</div></nav>

<header class="hero wrap">
  <div class="kicker">Cronobiología y horario escolar</div>
  <h1>¿Por qué tus alumnos están <em>dormidos</em> a las 8 de la mañana?</h1>
  <hr class="hr-gold">
  <p class="standfirst">No es pereza, ni falta de disciplina, ni únicamente el
  móvil. Es que a las 8:00 el organismo de un adolescente todavía está,
  literalmente, en su noche biológica, y en España la campana suena además antes
  de que amanezca. Lo que sigue es la evidencia, con las cifras y sus
  fuentes.</p>
  <p class="byline">Eduardo C. Garrido-Merchán · Universidad Pontificia
  Comillas · Madrid, 2026</p>
</header>

<div class="wrap">
 <div class="stats">
  <div class="stat"><b>{es(le7['17-18'])}&nbsp;%</b>
    <span>de los adolescentes de 17-18 años duerme 7 horas o menos los días de
    clase</span>
    <i>Estudio HBSC-2022, España, n = 33.630</i></div>
  <div class="stat"><b>{es(d17_wd)}&nbsp;%</b>
    <span>llega a las 8 horas recomendadas entre semana, frente al
    {es(d1112_wd)}&nbsp;% a los 11-12 años</span>
    <i>Suma de las categorías de la Tabla 19</i></div>
  <div class="stat"><b>08:36</b>
    <span>amanece en Madrid el 15 de enero: 36 minutos después de la
    campana</span>
    <i>US Naval Observatory</i></div>
  <div class="stat"><b>+34 min</b>
    <span>de sueño medido con actigrafía al retrasar la entrada de 07:50 a
    08:45</span>
    <i>Dunster et al., 2018, Science Advances</i></div>
 </div>
</div>

<main class="wrap">

<section id="reloj">
  <h2><span class="n">01</span>El reloj interno se retrasa en la pubertad, y no
  se retrasa porque el adolescente lo decida.</h2>
  <hr class="rule">
  <p class="lead">La adolescencia trae consigo un desplazamiento del reloj
  circadiano hacia horas más tardías. La primera evidencia de que ese
  desplazamiento tiene raíz biológica y no meramente social la aportaron
  Carskadon, Vieira y Acebo en 1993: en una muestra de 183 chicos y 275 chicas
  de sexto curso, la preferencia de fase (matutinidad frente a vespertinidad) se
  asoció de forma significativa al estadio puberal en las chicas, con una
  tendencia del mismo signo en los chicos, mientras que no apareció ninguna
  relación con los factores psicosociales evaluados. La conclusión de aquel
  trabajo era explícita: hay un factor biológico detrás del retraso de fase
  adolescente.</p>
  <p>Once años después, Roenneberg y colaboradores cuantificaron la trayectoria
  completa. Con el Cuestionario de Cronotipo de Múnich sobre unas 25.000
  personas de 10 a 90 años, mostraron que el cronotipo se retrasa
  progresivamente durante la adolescencia, alcanza su máximo retraso en torno a
  los 20 años y a partir de ahí se invierte de forma abrupta. Las mujeres
  alcanzan ese máximo antes, hacia los 19,5 años, coherentemente con su
  maduración puberal más temprana. Los autores propusieron precisamente ese
  punto de inflexión como el primer marcador biológico del final de la
  adolescencia.</p>
  <p>El mecanismo se lee en la melatonina. Crowley y colaboradores midieron el
  inicio de la secreción de melatonina en luz tenue (DLMO) en niños y
  adolescentes y encontraron que la hora de acostarse, la mitad del sueño y la
  hora de despertar correlacionan positivamente con la fase circadiana; sus
  ecuaciones predicen el DLMO con un margen de una hora en torno al 80 % de los
  casos. Dicho de otro modo: cuando un adolescente no se duerme a las once,
  muchas veces no es que no quiera, es que su cerebro aún no ha empezado la
  noche. Y si su noche interna empieza más tarde, un despertador que no se mueve
  recorta el sueño por el único extremo que puede recortarlo.</p>
  {figure(f1, "1",
          "Línea temporal desde las 21:00 hasta las 09:00 con la ventana de "
          "sueño recomendada, la ventana real y la posición de la campana "
          "escolar.",
          "La recomendación de la Academia Americana de Medicina del Sueño para "
          "13-18 años es de 8 a 10 horas; la categoría modal a los 17-18 años "
          "en España es de 7 horas (33,7 %).",
          "Con despertar a las 7:00 para entrar a las 8:00, cumplir la "
          "recomendación exige un inicio del sueño hacia las 22:00-23:00, justo "
          "cuando la fase circadiana adolescente aún no lo permite.")}
</section>

<section id="deuda">
  <h2><span class="n">02</span>La deuda de sueño española está medida, es grande
  y crece con la edad.</h2>
  <hr class="rule">
  <div class="two">
    <div>
      <p>El consenso clínico es nítido. La Academia Americana de Medicina del
      Sueño, tras revisar 864 artículos publicados con un método RAND
      modificado, recomienda de 8 a 10 horas de sueño por cada 24 horas para
      los adolescentes de 13 a 18 años. La National Sleep Foundation
      sitúa el rango en 9 a 11 horas hasta los 13-14 años y en 8 a 10 desde los
      15, y es este último criterio, escalonado por edad, el que utiliza el
      Ministerio de Sanidad para evaluar a los adolescentes españoles.</p>
      <p>El Estudio HBSC-2022 en España, con una muestra aleatoria, polietápica
      y estratificada de 33.630 adolescentes de 11 a 18 años, mide exactamente
      eso. Entre semana, sumando las categorías publicadas, un
      {es(le7['17-18'])} % de los adolescentes de 17-18 años duerme siete horas
      o menos. Solo un {es(d17_wd)} % alcanza las ocho horas o más, frente a un
      {es(d1112_wd)} % a los 11-12 años. Y un 15,5 % de los mayores duerme cinco
      horas o menos en una noche de clase.</p>
    </div>
    <div class="aside">
      <h3>Cómo leer estas cifras</h3>
      <p>Las tablas 19 y 20 del informe divulgativo del HBSC-2022 publican la
      distribución completa de horas de sueño por sexo y grupo de edad, entre
      semana y en fin de semana.</p>
      <p>Los agregados que aparecen aquí (por ejemplo «7 horas o menos» o «8
      horas o más») son sumas directas de esas categorías publicadas, no
      reanálisis de los microdatos.</p>
      <p>El informe declara la tendencia de fondo: desde 2010, primer año en que
      se mide el indicador, la proporción de adolescentes que duerme las horas
      que necesita desciende en todas las edades.</p>
    </div>
  </div>
  {figure(f2, "2",
          "Cuatro barras apiladas, una por grupo de edad, con la distribución "
          "del número de horas de sueño entre semana; la línea vertical marca "
          "el umbral de siete horas o menos.",
          f"La proporción que duerme siete horas o menos pasa del "
          f"{es(le7['11-12'])} % a los 11-12 años al {es(le7['13-14'])} % a los "
          f"13-14, al {es(le7['15-16'])} % a los 15-16 y al {es(le7['17-18'])} % "
          f"a los 17-18.",
          "El déficit no es un rasgo de la adolescencia en bloque: aparece y se "
          "agrava exactamente en los cursos en los que el horario escolar se "
          "adelanta y la carga académica aumenta.")}
  <div class="tablebox">
  <table>
    <caption>Número de horas de sueño entre semana. Porcentajes por grupo de
    edad. Estudio HBSC-2022 en España, Tabla 19 (n = 33.630).</caption>
    <thead><tr><th>Horas</th>
      <th class="num">11-12</th><th class="num">13-14</th>
      <th class="num">15-16</th><th class="num">17-18</th>
      <th class="num">Total</th></tr></thead>
    <tbody>{table_rows}</tbody>
  </table>
  </div>
</section>

<section id="prueba">
  <h2><span class="n">03</span>El fin de semana demuestra que el problema es el
  horario, no el adolescente.</h2>
  <hr class="rule">
  <p>Si los adolescentes durmieran poco por incapacidad o por desinterés,
  dormirían poco también cuando nadie los despierta. Ocurre lo contrario. Con
  los mismos umbrales por edad, la proporción que alcanza ocho horas o más se
  sostiene en torno al 80 % en todos los grupos de edad durante el fin de
  semana, mientras entre semana se desmorona: {es(d17_wd)} % frente a
  {es(d17_we)} % a los 17-18 años. La diferencia, más de cincuenta puntos
  porcentuales en el mismo grupo de chicos y chicas, no la explica ninguna
  teoría sobre su carácter. La explica el despertador.</p>
  <p class="pull">Este patrón tiene nombre desde 2006. Wittmann, Dinich, Merrow
  y Roenneberg lo llamaron <em>jet lag social</em>: la discrepancia sistemática
  entre el tiempo biológico y el tiempo social. En su muestra de 501
  voluntarios, los cronotipos tardíos mostraban la mayor diferencia de horarios
  entre días laborables y días libres, acumulaban deuda de sueño en los primeros
  y la compensaban en los segundos, y las asociaciones con el malestar y el
  consumo de estimulantes eran más intensas precisamente en adolescentes y
  jóvenes hasta los 25 años.
  <cite>Wittmann et al., Chronobiology International, 2006</cite></p>
  {figure(f3, "3",
          "Barras agrupadas por grupo de edad que comparan el porcentaje que "
          "duerme ocho horas o más entre semana y en fin de semana.",
          f"A los 17-18 años: {es(d17_wd)} % entre semana frente a "
          f"{es(d17_we)} % en fin de semana. A los 11-12 años la brecha es de "
          "apenas tres puntos.",
          "La capacidad de dormir permanece intacta a lo largo de la "
          "adolescencia. Lo que se estrecha, curso a curso, es la ventana que el "
          "calendario escolar deja libre.")}
</section>

<section id="espana">
  <h2><span class="n">04</span>España añade su propia agravante: el reloj
  oficial va muy por delante del Sol.</h2>
  <hr class="rule">
  <p>La España peninsular usa la hora central europea desde 1940, un huso que no
  le corresponde geográficamente. La consecuencia es medible con precisión
  astronómica. Según los datos del Observatorio Naval de los Estados Unidos, en
  Madrid el paso del Sol por el meridiano (el mediodía solar verdadero) ocurre
  el 15 de enero a las 13:24 de la hora oficial. Es decir, el reloj civil va una
  hora y veinticuatro minutos por delante del Sol, y las 8:00 de la mañana
  oficiales equivalen a las 6:36 solares. En verano, con el cambio horario, el
  desfase se amplía: el 21 de junio el mediodía solar cae a las 14:17, y las 8:00
  oficiales son las 5:43 solares.</p>
  <p>Añádase el detalle más elemental y más incómodo. El 15 de enero el Sol sale
  en Madrid a las 8:36, y el 21 de diciembre a las 8:34. Durante buena parte del
  curso, un instituto que empieza a las 8:00 hace entrar a sus alumnos a un aula
  media hora antes de que salga el Sol, en plena oscuridad, en el tramo horario
  en que la melatonina de un adolescente todavía está circulando. Puesto que la
  luz matinal es la señal principal que adelanta el reloj circadiano, el horario
  español no solo recorta el sueño por el extremo del despertar, sino que
  entrega la señal correctora más tarde de lo que la entregaría cualquier país
  al oeste del meridiano de Greenwich con su huso natural.</p>
  {figure(f4, "4",
          "Dos líneas temporales, enero y junio, con la franja nocturna, el "
          "amanecer, el mediodía solar y la posición de la campana de las 8:00 "
          "en Madrid.",
          "Mediodía solar a las 13:24 el 15 de enero y a las 14:17 el 21 de "
          "junio; amanecer a las 8:36 y a las 6:45 respectivamente. Las 8:00 "
          "oficiales son las 6:36 y las 5:43 solares.",
          "El adelanto estructural del reloj español sobre el solar traslada la "
          "entrada al instituto a un momento que, en tiempo biológico, "
          "corresponde a la madrugada.")}
  <div class="method">
    <h3>Sobre la hora de entrada en España</h3>
    <p>La hora exacta de inicio de la jornada no está fijada por norma estatal:
    es competencia autonómica y, en la práctica, cada centro concreta su horario
    general dentro de las instrucciones de su comunidad. La Orden andaluza de 20
    de agosto de 2010, por ejemplo, regula el horario general de los institutos
    sin fijar hora de comienzo. No existe, por tanto, una estadística oficial
    consolidada de horas de entrada.</p>
    <p>Lo que sí está documentado es el modelo: la jornada continua es
    mayoritaria en la secundaria española y lleva a que muchos institutos
    empiecen antes de las nueve de la mañana, con inicios habituales entre las
    8:00 y las 8:30. Esta caracterización procede del encuentro del Science
    Media Center España con Marta Ferrero (Universidad Autónoma de Madrid) y
    Daniel Gabaldón (Universitat de València), y debe leerse como valoración
    experta, no como dato administrativo.</p>
  </div>
</section>

<section id="coste">
  <h2><span class="n">05</span>El coste cognitivo de dormir cinco horas está
  medido en laboratorio, y no se paga solo al día siguiente.</h2>
  <hr class="rule">
  <p>El experimento más limpio sobre esta cuestión es el <em>Need for Sleep
  Study</em>. Lo y colaboradores reclutaron 56 adolescentes sanos de 15 a 19
  años, estudiantes de institutos de alto rendimiento y que no eran dormidores
  cortos habituales, y los asignaron aleatoriamente a dos grupos en un internado
  durante dos semanas: tres noches basales con nueve horas de oportunidad de
  sueño, siete noches con cinco horas en el grupo restringido y nueve en el
  control, y tres noches de recuperación con nueve horas. Se les administró una
  batería cognitiva tres veces al día.</p>
  <p>El resultado tiene dos partes, y la segunda es la relevante para cualquiera
  que dé clase. Durante la restricción, el grupo de cinco horas mostró un
  deterioro incremental, noche a noche, en atención sostenida, memoria de
  trabajo y función ejecutiva, junto a un aumento de la somnolencia subjetiva y
  una caída del afecto positivo. Y después: la somnolencia subjetiva y la
  atención sostenida no volvieron a los valores basales ni siquiera tras dos
  noches de recuperación. Además, la mejora por repetición de las pruebas, es
  decir el aprendizaje, apareció en el grupo control pero quedó atenuada en el
  restringido, que siguió rindiendo peor pese a haber recuperado sueño.</p>
  <p class="pull">Dormir de más el sábado no cancela la factura de la semana. Y
  el sueño no es tiempo muerto: la consolidación de lo aprendido, la
  estabilización de las trazas de memoria y su integración en el conocimiento
  previo ocurren durante el sueño, no a pesar de él.
  <cite>Lo et al., Sleep, 2016; Diekelmann y Born, Nature Reviews Neuroscience,
  2010</cite></p>
  <p>Conviene subrayar el diseño: los participantes no eran adolescentes con mal
  rendimiento ni con hábitos de sueño patológicos, sino alumnos selectos y
  buenos dormidores. La conclusión de los autores es que una semana de privación
  parcial de sueño deteriora un amplio rango de funciones cognitivas, la alerta
  subjetiva y el estado de ánimo incluso en adolescentes de alto rendimiento. El
  alumno que mira al vacío a las 8:15 no está desmotivado: está ejecutando una
  tarea de atención sostenida en el peor momento posible de su curva circadiana
  y con déficit acumulado.</p>
</section>

<section id="evidencia">
  <h2><span class="n">06</span>Retrasar la campana funciona, y la evidencia es
  experimental, no solo correlacional.</h2>
  <hr class="rule">
  <p>La objeción intuitiva es conocida: si se entra más tarde, se acostarán más
  tarde y el sueño total no cambiará. Es una hipótesis contrastable, y está
  contrastada. Minges y Redeker revisaron sistemáticamente la evidencia
  experimental disponible, seis estudios con diseños pre-post, ensayos
  aleatorizados y cuasiexperimentales, en los que la entrada se retrasó entre 25
  y 60 minutos. El tiempo total de sueño aumentó entre 25 y 77 minutos por noche
  de clase. Es decir, la hora de acostarse no se desplaza en la misma medida, y
  la ganancia se conserva.</p>
  <p>El caso mejor documentado es Seattle. En 2016 el distrito retrasó la
  entrada de los institutos de las 7:50 a las 8:45, y Dunster y colaboradores
  midieron el sueño con actímetros de pulsera, no con autoinforme, en dos
  cohortes comparables de alumnos de segundo curso, 94 en 2016 y 84 en 2017. La
  duración mediana del sueño en días de clase pasó de 6 horas y 50 minutos a 7
  horas y 24 minutos, un incremento de 34 minutos. Las calificaciones medianas
  subieron un 4,5 % (p = 0,0261), la somnolencia diurna medida con la escala de
  Epworth bajó de 7,0 a 6,0 (p = 0,0370), y en uno de los dos institutos se
  registró una reducción significativa de faltas y retrasos (p &lt; 0,0001).</p>
  {figure(f5, "5",
          "Barras horizontales con los minutos de sueño ganados por noche de "
          "clase en la revisión de estudios experimentales y en el caso de "
          "Seattle.",
          "Retrasos de 25 a 60 minutos producen entre 25 y 77 minutos más de "
          "sueño por noche en seis estudios experimentales. En Seattle, un "
          "retraso de 55 minutos produjo 34 minutos más, medidos con "
          "actigrafía.",
          "La ganancia de sueño es real y persistente: los adolescentes no "
          "compensan íntegramente retrasando la hora de acostarse.")}
  <p>El metaanálisis de Bowers y Moyer, que agrega cinco estudios
  longitudinales y quince comparaciones transversales, apunta en la misma
  dirección: horarios de entrada más tardíos se asocian a más horas de sueño,
  menos somnolencia diurna y menos retrasos, si bien los autores piden cautela
  interpretativa por la necesidad de más investigación longitudinal
  primaria.</p>
  <p>Queda por descartar una explicación alternativa: que lo que mejora sea el
  alumno mañanero y no el horario. El diseño que lo resuelve es argentino.
  Goldin, Sigman, Braier, Golombek y Leone estudiaron 753 estudiantes de un
  instituto público de Buenos Aires asignados <em>por sorteo</em> a uno de tres
  turnos, con entrada a las 07:45, a las 12:40 o a las 17:20. La asignación
  aleatoria elimina la autoselección. En el turno de mañana, los cronotipos
  tempranos rinden mejor que los tardíos en todas las asignaturas, con el efecto
  más grande en matemáticas; ese efecto se desvanece en el turno de tarde; y los
  cronotipos tardíos se benefician de las clases vespertinas. El rendimiento no
  depende solo del alumno ni solo del horario, sino del ajuste entre ambos.</p>
  <p>Por eso la Academia Americana de Pediatría, en su declaración de política
  de 2014, señala los horarios de entrada anteriores a las 8:30 como el factor
  modificable clave del sueño insuficiente y de la disrupción circadiana en esta
  población, e insta a institutos y centros de secundaria a fijar horarios que
  permitan a los alumnos alcanzar entre 8,5 y 9,5 horas de sueño.</p>
</section>

<section id="pantallas">
  <h2><span class="n">07</span>Sí, el móvil también. Pero el móvil no explica el
  gradiente por edad ni la brecha del fin de semana.</h2>
  <hr class="rule">
  <div class="two">
    <div>
      <p>Nada de lo anterior exculpa a las pantallas. El metaanálisis de Carter
      y colaboradores, veinte estudios y 125.198 niños y adolescentes con una
      edad media de 14,5 años, encuentra una asociación fuerte y consistente
      entre el uso de dispositivos móviles al acostarse y el sueño insuficiente
      (OR = 2,17; IC 95 % 1,42-3,32), la mala calidad del sueño (OR = 1,46;
      1,14-1,88) y la somnolencia diurna excesiva (OR = 2,72; 1,32-5,61).</p>
      <p>El hallazgo más interesante es el otro: los adolescentes que
      simplemente <em>tenían acceso</em> al dispositivo por la noche, sin
      declarar usarlo, presentaban también más sueño insuficiente (OR = 1,79;
      1,39-2,31) y más somnolencia diurna (OR = 2,27; 1,54-3,35). La presencia
      del dispositivo en la habitación es en sí misma un factor de riesgo.</p>
      <p>Pero repárese en lo que el móvil no puede explicar. No explica por qué
      la misma cohorte duerme ocho horas o más el fin de semana y no entre
      semana, ni por qué el retraso de fase aparece asociado al estadio puberal
      y no a los factores psicosociales, ni por qué mover la campana 55 minutos
      produce 34 minutos más de sueño medidos con actímetro. Son dos causas que
      se suman, y solo una de ellas está en manos del centro educativo.</p>
    </div>
    <div class="aside">
      <h3>Qué se deduce de todo esto</h3>
      <p>Primero, que el sueño insuficiente adolescente es un problema
      estructural de horarios, no un problema de carácter, y que responde a una
      intervención barata y reversible.</p>
      <p>Segundo, que en España el efecto está agravado por un desfase de una
      hora y veinticuatro minutos entre el reloj oficial y el Sol, de modo que
      cualquier discusión sobre la entrada a las 8:00 debería partir de que son
      las 6:36 solares.</p>
      <p>Y tercero, que el margen práctico existe: retirar los dispositivos de
      la habitación, proteger la exposición a luz matinal y, sobre todo,
      discutir en serio la hora de inicio de la jornada en secundaria.</p>
    </div>
  </div>
  {figure(f6, "6",
          "Gráfico de bosque con seis razones de probabilidad y sus intervalos "
          "de confianza al 95 %, agrupadas según uso o mero acceso al "
          "dispositivo.",
          "Las seis estimaciones son mayores que 1 y sus intervalos de "
          "confianza no cruzan la unidad. El uso al acostarse duplica la "
          "probabilidad de sueño insuficiente; el mero acceso la multiplica por "
          "1,79.",
          "Las pantallas son un factor real y modificable, pero de magnitud "
          "comparable, no superior, al efecto del propio horario escolar.")}
</section>

<section id="fuentes">
  <h2><span class="n">08</span>Fuentes</h2>
  <hr class="rule">
  <p>Todas las cifras citadas provienen de las publicaciones que siguen. Los
  metadatos bibliográficos de cada referencia (autores, año, título, revista,
  volumen, número y páginas) se han descargado de Crossref y de PubMed y se
  comparan mecánicamente con el texto de esta página mediante el script de
  validación que se indica más abajo.</p>
  <ol class="refs">
  {refs}
  </ol>
  <div class="method">
    <h3>Nota metodológica y de reproducibilidad</h3>
    <p>Los porcentajes del Estudio HBSC-2022 se toman literalmente de las tablas
    19 y 20 del informe divulgativo del Ministerio de Sanidad. Los agregados «7
    horas o menos» y «8 horas o más» son sumas aritméticas de esas categorías
    publicadas, calculadas en el propio generador de esta página; las dos que el
    informe también publica como texto ({es(d17_wd)} % y {es(d1112_wd)} %) se
    reproducen exactamente, lo que sirve de comprobación.</p>
    <p>Los datos astronómicos de Madrid se obtienen de la API del Observatorio
    Naval de los Estados Unidos para las coordenadas 40,4168 N y −3,7038, y se
    expresan en la hora del reloj oficial español (UTC+1 en enero y diciembre,
    UTC+2 en abril y junio). La hora solar equivalente se calcula como la hora
    oficial menos el desfase entre el paso del Sol por el meridiano y las
    12:00.</p>
    <p>Esta página es un único fichero HTML sin dependencias externas: todas las
    figuras son SVG generado programáticamente a partir de los datos declarados
    en <code>build.py</code>. La verificación es mecánica y reproducible en tres
    niveles: <code>data/validate_refs.py</code> coteja cada campo de cada
    referencia contra Crossref y PubMed, <code>data/validate_claims.py</code>
    comprueba que cada cifra atribuida a un trabajo aparece literalmente en su
    texto, y <code>data/validate_astro.py</code> vuelve a consultar al
    Observatorio Naval. Los metadatos y textos descargados quedan cacheados en
    <code>data/refs_cache/</code> para que la comparación sea auditable.</p>
  </div>
</section>

</main>

<footer>
  <p class="name">Eduardo C. Garrido-Merchán</p>
  <hr class="rule2">
  <p>Universidad Pontificia Comillas ·
  <a href="mailto:ecgarrido@comillas.edu">ecgarrido@comillas.edu</a></p>
  <p>Madrid, 2026</p>
</footer>

<script>
(function(){{
  var links = Array.prototype.slice.call(document.querySelectorAll('nav a'));
  var secs  = links.map(function(a){{ return document.getElementById(a.dataset.sec); }});
  function mark(id){{
    links.forEach(function(a){{ a.classList.toggle('on', a.dataset.sec === id); }});
  }}
  if ('IntersectionObserver' in window) {{
    var io = new IntersectionObserver(function(entries){{
      entries.forEach(function(e){{ if (e.isIntersecting) mark(e.target.id); }});
    }}, {{ rootMargin: '-45% 0px -50% 0px' }});
    secs.forEach(function(s){{ if (s) io.observe(s); }});
  }} else {{
    window.addEventListener('scroll', function(){{
      var best = null, bd = Infinity;
      secs.forEach(function(s){{
        if (!s) return;
        var d = Math.abs(s.getBoundingClientRect().top - 120);
        if (d < bd) {{ bd = d; best = s.id; }}
      }});
      if (best) mark(best);
    }}, {{ passive: true }});
  }}
  mark('reloj');
}})();
</script>
</body>
</html>
"""


def main() -> None:
    html = build_html()
    out = os.path.join(HERE, "index.html")
    with open(out, "w", encoding="utf-8") as fh:
        fh.write(html)

    with open(os.path.join(HERE, "data", "astro_madrid.json"), "w",
              encoding="utf-8") as fh:
        json.dump({"source": "US Naval Observatory, AA API rstt/oneday",
                   "coords": "40.4168,-3.7038",
                   "note": ("consultado con tz=1 y dst=false; a las fechas en "
                            "horario de verano se les suma 60 min para "
                            "expresarlas en hora oficial"),
                   "dst_offset_applied_min": ASTRO_DST_ADJUSTED,
                   "data": ASTRO}, fh, indent=1, ensure_ascii=False)

    problems = []
    for name, tbl in (("Tabla 19", HBSC_WEEKDAY), ("Tabla 20", HBSC_WEEKEND)):
        for age, row in tbl.items():
            if abs(sum(row) - 100.0) > 0.6:
                problems.append(f"{name} {age}: suma {sum(row):.1f} %")
    if abs(sum(HBSC_TOTAL_WEEKDAY) - 100.0) > 0.6:
        problems.append(f"Tabla 19 Total: suma {sum(HBSC_TOTAL_WEEKDAY):.1f} %")
    # cifras que el informe publica en texto y que deben salir por suma
    for label, got, want in (("17-18 >=8h", pct_at_least_8h(HBSC_WEEKDAY["17-18"]), 23.4),
                             ("11-12 >=8h", pct_at_least_8h(HBSC_WEEKDAY["11-12"]), 78.3)):
        if abs(got - want) > 0.05:
            problems.append(f"{label}: calculado {got} != publicado {want}")
    # ningun texto de la pagina debe llevar punto decimal en una cifra.
    # El separador de millares espanol siempre agrupa de tres en tres, de modo
    # que un punto seguido de una o dos cifras solo puede ser un decimal ingles.
    import re
    for m in re.finditer(r">[^<>]*?\b\d+\.\d{1,2}(?!\d)[^<>]*?<", html):
        frag = m.group(0)
        if "doi" in frag or "10." in frag:
            continue
        problems.append(f"separador decimal ingles: {frag[:70]}")

    print(f"[build] escrito {out} ({len(html)/1024:.1f} kB)")
    for age in HBSC_WEEKDAY:
        print(f"        {age}: >=8h entre semana {pct_at_least_8h(HBSC_WEEKDAY[age]):5.1f} % | "
              f">=8h fin de semana {pct_at_least_8h(HBSC_WEEKEND[age]):5.1f} % | "
              f"<=7h entre semana {pct_at_most_7h(HBSC_WEEKDAY[age]):5.1f} %")
    if problems:
        print("[build] INCONSISTENCIAS:")
        for p in problems:
            print("   -", p)
        raise SystemExit(1)
    print("[build] comprobaciones de consistencia: OK")


if __name__ == "__main__":
    main()
