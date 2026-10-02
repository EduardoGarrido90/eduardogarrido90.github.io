#!/usr/bin/env python3
"""Publica los casos de practica de Machine Learning I en la web del curso.

Deja dos zonas claramente separadas:

  * Zona abierta. Para cada caso, el dossier en PDF y el fichero de datos en
    CSV. Es lo unico que ve el alumnado, y no revela ni el tipo de las
    columnas ni cual es la variable a predecir, porque proponerla es el
    ejercicio.

  * Zona docente, cifrada. La clave del profesor con el proceso generador de
    cada caso, la revision preliminar con la salida completa de los ajustes,
    el informe comparado y el fichero de metricas. La contrasena NO es la de
    clase: este material resuelve el ejercicio entero y solo lo abre el
    equipo docente.

El cifrado es el mismo que usa `docencia/assets/vault.js`:
    fichero .enc = iv(12 bytes) || AES-GCM(ciphertext || tag)
    clave        = PBKDF2-SHA256(password, salt, iters) -> AES-256-GCM

La contrasena se pide por getpass, nunca por argv, y se verifica contra el
token de control de index.html antes de escribir un solo fichero. En la
primera ejecucion no hay token todavia: se usa --iniciar para crear el salt y
el token, y el CFG se inyecta en index.html.

Uso:
    python3 publicar.py --iniciar    # primera vez: crea salt, token y CFG
    python3 publicar.py              # republica lo que haya cambiado
    python3 publicar.py --todos      # rehace la publicacion entera
"""
from __future__ import annotations

import argparse
import base64
import getpass
import html
import json
import os
import re
import shutil
import sys
from pathlib import Path

try:
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
except ImportError:
    sys.exit("Falta el paquete 'cryptography'. Instala con: pip install cryptography")

AQUI = Path(__file__).resolve().parent
INDEX = AQUI / "index.html"
PUBLICO = AQUI / "archivos"
VAULT = AQUI / "vault"
ORIGEN = Path("/home/eduardo/docencia/machine_learning/dossiers/casos_nuevos")

ITERS = 200_000
ORDEN_FAMILIAS = ["Empresa", "Educación", "Salud", "Medio ambiente",
                  "Gestión urbana", "Social"]


# =====================================================================
#  Criptografia (identica a la que espera vault.js)
# =====================================================================
def derivar_clave(password: str, salt: bytes, iters: int) -> bytes:
    kdf = PBKDF2HMAC(algorithm=hashes.SHA256(), length=32, salt=salt, iterations=iters)
    return kdf.derive(password.encode("utf-8"))


def cifrar(datos: bytes, clave: bytes) -> bytes:
    iv = os.urandom(12)
    blob = iv + AESGCM(clave).encrypt(iv, datos, None)
    # round-trip antes de devolver: nunca se escribe un .enc que el navegador
    # no pueda abrir
    assert AESGCM(clave).decrypt(blob[:12], blob[12:], None) == datos, "round-trip falló"
    return blob


def leer_cfg() -> tuple[bytes, bytes, int]:
    texto = INDEX.read_text(encoding="utf-8")
    m = re.search(r"const\s+CFG\s*=\s*(\{.*?\})\s*;", texto, re.S)
    if not m:
        raise SystemExit("No encuentro el CFG en index.html. ¿Falta lanzar --iniciar?")
    cfg = json.loads(re.sub(r"(\w+)\s*:", r'"\1":', m.group(1)))
    return (base64.b64decode(cfg["salt"]), base64.b64decode(cfg["check"]), int(cfg["iters"]))


def verificar(clave: bytes, check: bytes) -> None:
    try:
        token = AESGCM(clave).decrypt(check[:12], check[12:], None)
    except Exception:
        raise SystemExit("Contraseña incorrecta: no se ha tocado ningún fichero.")
    if token != b"unlock-ok":
        raise SystemExit("El token de control no es 'unlock-ok'; revisa el CFG.")


# =====================================================================
#  Conversion del material docente a fragmentos HTML
# =====================================================================
def md_a_html(texto: str) -> str:
    """Conversion minima de los informes en Markdown a fragmento HTML.

    Solo se cubre lo que estos documentos usan: encabezados, tablas, listas,
    codigo entre comillas invertidas, negrita y parrafos. No se pretende un
    conversor general.
    """
    out, tabla = [], []

    def cerrar_tabla():
        if not tabla:
            return
        filas = [f for f in tabla if not re.match(r"^\|[\s:|-]+\|$", f)]
        out.append("<table>")
        for i, fila in enumerate(filas):
            celdas = [c.strip() for c in fila.strip().strip("|").split("|")]
            et = "th" if i == 0 else "td"
            out.append("<tr>" + "".join(f"<{et}>{en_linea(c)}</{et}>" for c in celdas) + "</tr>")
        out.append("</table>")
        tabla.clear()

    def en_linea(s: str) -> str:
        s = html.escape(s)
        s = re.sub(r"`([^`]+)`", r"<code>\1</code>", s)
        s = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", s)
        return s

    en_lista = False
    for linea in texto.splitlines():
        if linea.startswith("|"):
            tabla.append(linea)
            continue
        cerrar_tabla()
        if linea.startswith("### "):
            if en_lista:
                out.append("</ul>"); en_lista = False
            out.append(f"<h4>{en_linea(linea[4:])}</h4>")
        elif linea.startswith("## "):
            if en_lista:
                out.append("</ul>"); en_lista = False
            out.append(f"<h3>{en_linea(linea[3:])}</h3>")
        elif linea.startswith("# "):
            if en_lista:
                out.append("</ul>"); en_lista = False
            out.append(f"<h2>{en_linea(linea[2:])}</h2>")
        elif linea.startswith("- "):
            if not en_lista:
                out.append("<ul>"); en_lista = True
            out.append(f"<li>{en_linea(linea[2:])}</li>")
        elif not linea.strip():
            if en_lista:
                out.append("</ul>"); en_lista = False
        else:
            if en_lista:
                out.append("</ul>"); en_lista = False
            out.append(f"<p>{en_linea(linea)}</p>")
    if en_lista:
        out.append("</ul>")
    cerrar_tabla()
    return "\n".join(out)


def txt_a_html(texto: str, titulo: str) -> str:
    """La revision preliminar es salida de statsmodels: va en monoespaciado."""
    return f"<h2>{html.escape(titulo)}</h2><pre>{html.escape(texto)}</pre>"


# =====================================================================
#  Pagina
# =====================================================================
def construir_index(casos: list[dict], cfg_js: str) -> str:
    filas_por_familia: dict[str, list[str]] = {}
    for c in casos:
        tipo = "Regresión" if c["tipo"] == "regresion" else "Clasificación"
        fila = (
            f'<div class="row"><div class="rd">{tipo[:3]}.</div>'
            f'<div class="rt"><div class="rtt">{html.escape(c["titulo"])}</div>'
            f'<div class="rte">{c["n"]:,} registros · {c["columnas"]} campos · '
            f'{tipo.lower()}</div></div>'
            f'<div class="ra">'
            f'<a class="btn" href="archivos/{c["tema"]}/dossier_{c["tema"]}.pdf" '
            f'target="_blank" rel="noopener">Dossier</a>'
            f'<a class="btn ghost" href="archivos/{c["tema"]}/datos_{c["tema"]}.csv" '
            f'download>Datos</a>'
            f'<button class="btn sol-btn" disabled '
            f'data-file="vault/rev_{c["tema"]}.enc" '
            f'data-title="Revisión preliminar · {html.escape(c["tema"])}">Docente</button>'
            f'</div></div>'
        ).replace(",", ".")
        filas_por_familia.setdefault(c["familia"], []).append(fila)

    bloques = []
    for fam in ORDEN_FAMILIAS:
        if fam not in filas_por_familia:
            continue
        bloques.append(f'<div class="tema-head">{html.escape(fam)} · '
                       f'{len(filas_por_familia[fam])} casos</div>')
        bloques.append('<div class="rows">' + "".join(filas_por_familia[fam]) + "</div>")

    globales = [
        ("vault/informe_preliminar.enc", "Informe preliminar comparado",
         "Tabla de los 56 casos con métricas y dificultad"),
        ("vault/clave_profesor.enc", "Clave del profesor",
         "Proceso generador, variables irrelevantes y suciedad de cada caso"),
        ("vault/metricas.enc", "Métricas en JSON",
         "Las mismas cifras, en bruto, para procesarlas"),
    ]
    filas_glob = "".join(
        f'<div class="row"><div class="rd">Doc.</div>'
        f'<div class="rt"><div class="rtt">{html.escape(t)}</div>'
        f'<div class="rte">{html.escape(d)}</div></div>'
        f'<div class="ra"><button class="btn sol-btn" disabled '
        f'data-file="{f}" data-title="{html.escape(t)}">Abrir</button></div></div>'
        for f, t, d in globales)

    return f"""<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Casos de práctica · Machine Learning I</title>
<link rel="stylesheet" href="../../assets/style.css">
<script defer src="../../assets/vault.js"></script>
</head>
<body>
<div class="crumbs"><a href="../../index.html">Asignaturas</a><span class="sep">/</span><a href="../index.html">Machine Learning I</a><span class="sep">/</span><span>Casos de práctica</span></div>
<h1>Casos de práctica</h1>
<p class="sub">{len(casos)} conjuntos de datos con su dossier. Cada dossier es un informe descriptivo de una organización real en apariencia: presenta el diccionario de campos, los estadísticos y las gráficas, sin decir qué tipo tiene cada variable ni qué habría que predecir. Esa propuesta es vuestra.</p>
<div class="nota"><b>Cómo se trabaja un caso.</b> Leed primero el dossier y decidid qué variable tiene sentido predecir con las demás, y si el problema es de regresión o de clasificación. Descargad después el fichero de datos. Viene deliberadamente sucio: hay importes y fechas guardados como texto, categorías escritas de forma inconsistente, ausencias codificadas con centinelas y alguna columna redundante. Varias columnas no aportan nada y debéis detectarlo por vosotros mismos.</p>
<hr class="rule">
{"".join(bloques)}

<div class="tema-head">Material del equipo docente</div>
<p class="sub">Esta zona está cifrada y no se abre con la contraseña de clase. Contiene la solución completa de todos los casos.</p>
<div class="gate">
  <label for="pw">Contraseña del equipo docente</label>
  <input id="pw" type="password" autocomplete="off" spellcheck="false">
  <button class="go" onclick="unlock()">Desbloquear</button>
  <div class="msg" id="msg"></div>
</div>
<div class="rows" style="margin-top:16px">{filas_glob}</div>
<p class="sub" style="margin-top:10px">Al desbloquear, el botón <b>Docente</b> de cada caso abre su revisión preliminar con la salida completa de los ajustes.</p>

<p class="pie">Eduardo C. Garrido-Merchán · ecgarrido@comillas.edu · Universidad Pontificia Comillas (ICADE) · Machine Learning para Business Analytics 2026–2027</p>
<script>
{cfg_js}
let KEY=null;
const msg=document.getElementById('msg');
async function unlock(){{
  const pw=document.getElementById('pw').value;
  msg.className='msg'; msg.textContent='Comprobando…';
  try{{
    KEY=await DLVault.verify(pw,CFG);
    msg.className='msg ok'; msg.textContent='Material docente desbloqueado.';
    document.querySelectorAll('.sol-btn').forEach(btn=>{{
      btn.disabled=false;
      btn.addEventListener('click',async()=>{{
        try{{ await DLVault.open({{file:btn.dataset.file,title:btn.dataset.title,type:'html'}},KEY);}}
        catch(e){{ alert('No se ha podido abrir: '+e.message); }}
      }});
    }});
  }}catch(e){{
    msg.className='msg err'; msg.textContent='Contraseña incorrecta.';
  }}
}}
document.getElementById('pw').addEventListener('keydown',e=>{{if(e.key==='Enter')unlock();}});
</script>
</body>
</html>
"""


# =====================================================================
#  Programa principal
# =====================================================================
def cargar_casos() -> list[dict]:
    sys.path.insert(0, str(ORIGEN / "common"))
    from casos_def import CASOS  # noqa: E402
    metricas = {r["tema"]: r for r in json.loads((ORIGEN / "metricas.json").read_text())}
    casos = []
    for c in CASOS:
        m = metricas.get(c["tema"])
        if m is None:
            print(f"  aviso: {c['tema']} no está en metricas.json, se omite")
            continue
        casos.append(dict(tema=c["tema"], familia=c["familia"], tipo=c["tipo"],
                          n=m["n"], columnas=m["n_columnas"],
                          titulo=c["cabecera"].replace(
                              "Ficha del conjunto de datos de ", "").capitalize()))
    return casos


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--iniciar", action="store_true",
                    help="primera ejecución: crea salt y token de control")
    ap.add_argument("--todos", action="store_true", help="rehace todo, no solo lo cambiado")
    args = ap.parse_args(argv)

    casos = cargar_casos()
    print(f"casos encontrados: {len(casos)}")

    if args.iniciar:
        salt = os.urandom(16)
        password = getpass.getpass("Contraseña NUEVA del equipo docente: ")
        if password != getpass.getpass("Repítela: "):
            raise SystemExit("Las contraseñas no coinciden.")
        if len(password) < 8:
            print("  aviso: contraseña corta; el cifrado es público y se puede "
                  "atacar por diccionario sin conexión")
        clave = derivar_clave(password, salt, ITERS)
        check = cifrar(b"unlock-ok", clave)
        cfg_js = (f'const CFG={{salt:"{base64.b64encode(salt).decode()}",'
                  f'check:"{base64.b64encode(check).decode()}",iters:{ITERS}}};')
    else:
        salt, check, iters = leer_cfg()
        password = getpass.getpass("Contraseña del equipo docente: ")
        clave = derivar_clave(password, salt, iters)
        verificar(clave, check)
        print("Contraseña verificada contra el token de control.")
        cfg_js = (f'const CFG={{salt:"{base64.b64encode(salt).decode()}",'
                  f'check:"{base64.b64encode(check).decode()}",iters:{iters}}};')

    # ---- zona abierta ----
    PUBLICO.mkdir(parents=True, exist_ok=True)
    copiados = 0
    for c in casos:
        destino = PUBLICO / c["tema"]
        destino.mkdir(exist_ok=True)
        pares = [(ORIGEN / c["tema"] / "data" / "datos.csv", destino / f"datos_{c['tema']}.csv"),
                 (ORIGEN / c["tema"] / f"dossier_{c['tema']}.pdf",
                  destino / f"dossier_{c['tema']}.pdf")]
        for src, dst in pares:
            if not src.exists():
                raise SystemExit(f"falta el fichero de origen {src}")
            if args.todos or not dst.exists() or src.stat().st_mtime > dst.stat().st_mtime:
                shutil.copy2(src, dst)
                copiados += 1
    print(f"zona abierta: {copiados} ficheros copiados en {PUBLICO.name}/")

    # ---- zona docente cifrada ----
    VAULT.mkdir(parents=True, exist_ok=True)
    cifrados = 0
    for c in casos:
        src = ORIGEN / c["tema"] / "revision_preliminar.txt"
        if not src.exists():
            print(f"  aviso: sin revisión preliminar para {c['tema']}")
            continue
        frag = txt_a_html(src.read_text(encoding="utf-8"),
                          f"Revisión preliminar · {c['tema']}")
        (VAULT / f"rev_{c['tema']}.enc").write_bytes(cifrar(frag.encode("utf-8"), clave))
        cifrados += 1

    for nombre, fuente, conv in [
            ("informe_preliminar", ORIGEN / "INFORME_PRELIMINAR.md", md_a_html),
            ("clave_profesor", ORIGEN / "CLAVE_PROFESOR.md", md_a_html),
            ("metricas", ORIGEN / "metricas.json",
             lambda t: f"<h2>metricas.json</h2><pre>{html.escape(t)}</pre>")]:
        if not fuente.exists():
            raise SystemExit(f"falta {fuente}")
        frag = conv(fuente.read_text(encoding="utf-8"))
        (VAULT / f"{nombre}.enc").write_bytes(cifrar(frag.encode("utf-8"), clave))
        cifrados += 1
    print(f"zona docente: {cifrados} ficheros cifrados en {VAULT.name}/")

    INDEX.write_text(construir_index(casos, cfg_js), encoding="utf-8")
    print(f"escrito {INDEX.name}")

    mb_pub = sum(f.stat().st_size for f in PUBLICO.rglob("*") if f.is_file()) / 1048576
    mb_vault = sum(f.stat().st_size for f in VAULT.rglob("*") if f.is_file()) / 1048576
    print(f"\npeso: zona abierta {mb_pub:.1f} MB · zona docente {mb_vault:.1f} MB")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
