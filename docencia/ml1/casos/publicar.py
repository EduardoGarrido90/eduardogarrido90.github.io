#!/usr/bin/env python3
"""Publica los casos de practica de Machine Learning I, en dos zonas cifradas.

GitHub Pages sirve ficheros estaticos y no valida nada, de modo que un
formulario de JavaScript delante de la pagina no protege: las URL de los PDF
y los CSV seguirian siendo publicas y indexables. La unica proteccion real es
cifrar el contenido, y eso es lo que se hace aqui con las dos zonas.

  * Zona de alumnos, contrasena de clase. Los 56 dossieres en PDF y los 56
    ficheros de datos en CSV, cifrados. Sin la contrasena no se abre nada
    aunque se adivine la ruta.

  * Zona docente, contrasena propia del equipo. La clave del profesor con el
    proceso generador de cada caso, las revisiones preliminares con la salida
    completa de los ajustes, el informe comparado y las metricas.

Cada zona tiene su sal y su token de control, de forma que la contrasena de
una no abre la otra. El formato es el que espera `docencia/assets/vault.js`:

    fichero .enc = iv(12 bytes) || AES-GCM(ciphertext || tag)
    clave        = PBKDF2-SHA256(password, salt, iters) -> AES-256-GCM

Las contrasenas se piden por getpass, nunca por argv, y se verifican contra
su token antes de escribir un solo fichero.

Uso:
    python3 publicar.py --iniciar    # primera vez: crea sales y tokens
    python3 publicar.py              # recifra con las contrasenas vigentes
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
V_ALUMNO = AQUI / "material"
V_DOCENTE = AQUI / "vault"
PUBLICO_VIEJO = AQUI / "archivos"      # zona en claro de la version anterior
ORIGEN = Path("/home/eduardo/docencia/machine_learning/dossiers/casos_nuevos")

ITERS = 200_000
ORDEN_FAMILIAS = ["Empresa", "Educación", "Salud", "Medio ambiente",
                  "Gestión urbana", "Social"]


# =====================================================================
#  Criptografia
# =====================================================================
def derivar_clave(password: str, salt: bytes, iters: int) -> bytes:
    kdf = PBKDF2HMAC(algorithm=hashes.SHA256(), length=32, salt=salt, iterations=iters)
    return kdf.derive(password.encode("utf-8"))


def cifrar(datos: bytes, clave: bytes) -> bytes:
    iv = os.urandom(12)
    blob = iv + AESGCM(clave).encrypt(iv, datos, None)
    assert AESGCM(clave).decrypt(blob[:12], blob[12:], None) == datos, "round-trip falló"
    return blob


def b64(x: bytes) -> str:
    return base64.b64encode(x).decode()


def leer_cfgs() -> dict:
    """Extrae CFG_ALUMNO y CFG_DOCENTE del index.html ya publicado."""
    texto = INDEX.read_text(encoding="utf-8")
    out = {}
    for nombre in ("CFG_ALUMNO", "CFG_DOCENTE"):
        m = re.search(rf"const\s+{nombre}\s*=\s*(\{{.*?\}})\s*;", texto, re.S)
        if not m:
            raise SystemExit(f"No encuentro {nombre} en index.html. ¿Falta --iniciar?")
        cfg = json.loads(re.sub(r"(\w+)\s*:", r'"\1":', m.group(1)))
        out[nombre] = (base64.b64decode(cfg["salt"]),
                       base64.b64decode(cfg["check"]), int(cfg["iters"]))
    return out


def verificar(clave: bytes, check: bytes, quien: str) -> None:
    try:
        token = AESGCM(clave).decrypt(check[:12], check[12:], None)
    except Exception:
        raise SystemExit(f"Contraseña {quien} incorrecta: no se ha tocado ningún fichero.")
    if token != b"unlock-ok":
        raise SystemExit(f"El token de control de {quien} no es 'unlock-ok'.")


def pedir_nueva(quien: str) -> str:
    pw = getpass.getpass(f"Contraseña NUEVA {quien}: ")
    if pw != getpass.getpass("Repítela: "):
        raise SystemExit("Las contraseñas no coinciden.")
    if len(pw) < 8:
        print(f"  aviso: contraseña {quien} corta; el cifrado es público y se puede "
              "atacar por diccionario sin conexión")
    return pw


# =====================================================================
#  Conversion del material docente a fragmentos HTML
# =====================================================================
def md_a_html(texto: str) -> str:
    """Conversion minima del Markdown que usan estos informes."""
    out, tabla = [], []

    def en_linea(s: str) -> str:
        s = html.escape(s)
        s = re.sub(r"`([^`]+)`", r"<code>\1</code>", s)
        s = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", s)
        return s

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

    en_lista = False
    for linea in texto.splitlines():
        if linea.startswith("|"):
            tabla.append(linea)
            continue
        cerrar_tabla()
        if en_lista and not linea.startswith("- "):
            out.append("</ul>")
            en_lista = False
        if linea.startswith("### "):
            out.append(f"<h4>{en_linea(linea[4:])}</h4>")
        elif linea.startswith("## "):
            out.append(f"<h3>{en_linea(linea[3:])}</h3>")
        elif linea.startswith("# "):
            out.append(f"<h2>{en_linea(linea[2:])}</h2>")
        elif linea.startswith("- "):
            if not en_lista:
                out.append("<ul>")
                en_lista = True
            out.append(f"<li>{en_linea(linea[2:])}</li>")
        elif linea.strip():
            out.append(f"<p>{en_linea(linea)}</p>")
    if en_lista:
        out.append("</ul>")
    cerrar_tabla()
    return "\n".join(out)


def txt_a_html(texto: str, titulo: str) -> str:
    return f"<h2>{html.escape(titulo)}</h2><pre>{html.escape(texto)}</pre>"


# =====================================================================
#  Pagina
# =====================================================================
def construir_index(casos: list[dict], cfg_alumno: str, cfg_docente: str) -> str:
    por_familia: dict[str, list[str]] = {}
    for c in casos:
        tipo = "Regresión" if c["tipo"] == "regresion" else "Clasificación"
        n = f"{c['n']:,}".replace(",", ".")
        fila = (
            f'<div class="row"><div class="rd">{tipo[:3]}.</div>'
            f'<div class="rt"><div class="rtt">{html.escape(c["titulo"])}</div>'
            f'<div class="rte">{n} registros · {c["columnas"]} campos · {tipo.lower()}</div></div>'
            f'<div class="ra">'
            f'<button class="btn alu-pdf" disabled '
            f'data-file="material/{c["tema"]}/dossier.enc" '
            f'data-title="Dossier · {html.escape(c["titulo"])}" '
            f'data-dl="dossier_{c["tema"]}">Dossier</button>'
            f'<button class="btn ghost alu-csv" disabled '
            f'data-file="material/{c["tema"]}/datos.enc" '
            f'data-dl="datos_{c["tema"]}.csv">Datos</button>'
            f'<button class="btn doc-btn" disabled '
            f'data-file="vault/rev_{c["tema"]}.enc" '
            f'data-title="Revisión preliminar · {html.escape(c["tema"])}">Docente</button>'
            f'</div></div>')
        por_familia.setdefault(c["familia"], []).append(fila)

    bloques = []
    for fam in ORDEN_FAMILIAS:
        if fam not in por_familia:
            continue
        bloques.append(f'<div class="tema-head">{html.escape(fam)} · '
                       f'{len(por_familia[fam])} casos</div>')
        bloques.append('<div class="rows">' + "".join(por_familia[fam]) + "</div>")

    globales = [
        ("vault/informe_preliminar.enc", "Informe preliminar comparado",
         f"Tabla de los {len(casos)} casos con métricas y dificultad"),
        ("vault/clave_profesor.enc", "Clave del profesor",
         "Proceso generador, variables de relleno y suciedad de cada caso"),
        ("vault/metricas.enc", "Métricas en JSON",
         "Las mismas cifras, en bruto, para procesarlas"),
    ]
    filas_glob = "".join(
        f'<div class="row"><div class="rd">Doc.</div>'
        f'<div class="rt"><div class="rtt">{html.escape(t)}</div>'
        f'<div class="rte">{html.escape(d)}</div></div>'
        f'<div class="ra"><button class="btn doc-btn" disabled '
        f'data-file="{f}" data-title="{html.escape(t)}">Abrir</button></div></div>'
        for f, t, d in globales)

    return f"""<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="robots" content="noindex, nofollow">
<title>Casos de práctica · Machine Learning I</title>
<link rel="stylesheet" href="../../assets/style.css">
<script defer src="../../assets/vault.js"></script>
</head>
<body>
<div class="crumbs"><a href="../../index.html">Asignaturas</a><span class="sep">/</span><a href="../index.html">Machine Learning I</a><span class="sep">/</span><span>Casos de práctica</span></div>
<h1>Casos de práctica</h1>
<p class="sub">{len(casos)} conjuntos de datos con su dossier. Cada dossier es un informe descriptivo de una organización, en apariencia real: presenta el diccionario de campos, los estadísticos y las gráficas, sin decir qué tipo tiene cada variable ni qué habría que predecir. Esa propuesta es vuestra.</p>

<div class="gate">
  <label for="pw1">Contraseña de clase</label>
  <input id="pw1" type="password" autocomplete="off" spellcheck="false">
  <button class="go" onclick="abrirAlumno()">Entrar</button>
  <div class="msg" id="msg1"></div>
</div>

<div class="nota"><b>Cómo se trabaja un caso.</b> Leed primero el dossier y decidid qué variable tiene sentido predecir con las demás, y si el problema es de regresión o de clasificación. Descargad después el fichero de datos. Viene deliberadamente sucio: hay importes y fechas guardados como texto, categorías escritas de forma inconsistente, ausencias codificadas con centinelas y alguna columna redundante. Varias columnas no aportan nada y debéis detectarlo por vosotros mismos.</div>
<hr class="rule">
{"".join(bloques)}

<div class="tema-head">Material del equipo docente</div>
<p class="sub">Zona aparte, con su propia contraseña. No se abre con la de clase. Contiene la solución completa de todos los casos.</p>
<div class="gate">
  <label for="pw2">Contraseña del equipo docente</label>
  <input id="pw2" type="password" autocomplete="off" spellcheck="false">
  <button class="go" onclick="abrirDocente()">Desbloquear</button>
  <div class="msg" id="msg2"></div>
</div>
<div class="rows" style="margin-top:16px">{filas_glob}</div>
<p class="sub" style="margin-top:10px">Al desbloquear, el botón <b>Docente</b> de cada caso abre su revisión preliminar con la salida completa de los ajustes.</p>

<p class="pie">Eduardo C. Garrido-Merchán · ecgarrido@comillas.edu · Universidad Pontificia Comillas (ICADE) · Machine Learning para Business Analytics 2026–2027</p>
<script>
{cfg_alumno}
{cfg_docente}
let K_ALU=null, K_DOC=null;
const m1=document.getElementById('msg1'), m2=document.getElementById('msg2');

async function abrirAlumno(){{
  m1.className='msg'; m1.textContent='Comprobando…';
  try{{
    K_ALU=await DLVault.verify(document.getElementById('pw1').value, CFG_ALUMNO);
    m1.className='msg ok'; m1.textContent='Material desbloqueado. Ya puedes descargar.';
    document.querySelectorAll('.alu-pdf').forEach(b=>{{
      b.disabled=false;
      b.addEventListener('click',async()=>{{
        try{{ await DLVault.open({{file:b.dataset.file,title:b.dataset.title,
              type:'pdf',download:b.dataset.dl}},K_ALU); }}
        catch(e){{ alert('No se ha podido abrir: '+e.message); }}
      }});
    }});
    document.querySelectorAll('.alu-csv').forEach(b=>{{
      b.disabled=false;
      b.addEventListener('click',async()=>{{
        const t=b.textContent; b.textContent='…';
        try{{ await DLVault.descargar({{file:b.dataset.file,
              download:b.dataset.dl,mime:'text/csv'}},K_ALU); }}
        catch(e){{ alert('No se ha podido descargar: '+e.message); }}
        b.textContent=t;
      }});
    }});
  }}catch(e){{ m1.className='msg err'; m1.textContent='Contraseña incorrecta.'; }}
}}

async function abrirDocente(){{
  m2.className='msg'; m2.textContent='Comprobando…';
  try{{
    K_DOC=await DLVault.verify(document.getElementById('pw2').value, CFG_DOCENTE);
    m2.className='msg ok'; m2.textContent='Material docente desbloqueado.';
    document.querySelectorAll('.doc-btn').forEach(b=>{{
      b.disabled=false;
      b.addEventListener('click',async()=>{{
        try{{ await DLVault.open({{file:b.dataset.file,title:b.dataset.title,
              type:'html'}},K_DOC); }}
        catch(e){{ alert('No se ha podido abrir: '+e.message); }}
      }});
    }});
  }}catch(e){{ m2.className='msg err'; m2.textContent='Contraseña incorrecta.'; }}
}}
document.getElementById('pw1').addEventListener('keydown',e=>{{if(e.key==='Enter')abrirAlumno();}});
document.getElementById('pw2').addEventListener('keydown',e=>{{if(e.key==='Enter')abrirDocente();}});
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
    ap.add_argument("--iniciar", action="store_true")
    args = ap.parse_args(argv)

    casos = cargar_casos()
    print(f"casos encontrados: {len(casos)}")

    if args.iniciar:
        salt_a, salt_d = os.urandom(16), os.urandom(16)
        pw_a = pedir_nueva("de clase (alumnos)")
        pw_d = pedir_nueva("del equipo docente")
        if pw_a == pw_d:
            raise SystemExit("Las dos contraseñas no pueden ser la misma.")
        k_a, k_d = derivar_clave(pw_a, salt_a, ITERS), derivar_clave(pw_d, salt_d, ITERS)
        chk_a, chk_d = cifrar(b"unlock-ok", k_a), cifrar(b"unlock-ok", k_d)
        iters_a = iters_d = ITERS
    else:
        cfgs = leer_cfgs()
        salt_a, chk_a, iters_a = cfgs["CFG_ALUMNO"]
        salt_d, chk_d, iters_d = cfgs["CFG_DOCENTE"]
        k_a = derivar_clave(getpass.getpass("Contraseña de clase: "), salt_a, iters_a)
        verificar(k_a, chk_a, "de clase")
        k_d = derivar_clave(getpass.getpass("Contraseña docente: "), salt_d, iters_d)
        verificar(k_d, chk_d, "docente")
        print("Las dos contraseñas verifican contra su token.")

    cfg_alumno = (f'const CFG_ALUMNO={{salt:"{b64(salt_a)}",'
                  f'check:"{b64(chk_a)}",iters:{iters_a}}};')
    cfg_docente = (f'const CFG_DOCENTE={{salt:"{b64(salt_d)}",'
                   f'check:"{b64(chk_d)}",iters:{iters_d}}};')

    # ---- zona de alumnos, cifrada ----
    V_ALUMNO.mkdir(parents=True, exist_ok=True)
    n = 0
    for c in casos:
        d = V_ALUMNO / c["tema"]
        d.mkdir(exist_ok=True)
        for src, dst in [(ORIGEN / c["tema"] / "data" / "datos.csv", d / "datos.enc"),
                         (ORIGEN / c["tema"] / f"dossier_{c['tema']}.pdf", d / "dossier.enc")]:
            if not src.exists():
                raise SystemExit(f"falta el fichero de origen {src}")
            dst.write_bytes(cifrar(src.read_bytes(), k_a))
            n += 1
    print(f"zona de alumnos: {n} ficheros cifrados en {V_ALUMNO.name}/")

    # ---- zona docente, cifrada ----
    V_DOCENTE.mkdir(parents=True, exist_ok=True)
    n = 0
    for c in casos:
        src = ORIGEN / c["tema"] / "revision_preliminar.txt"
        if not src.exists():
            print(f"  aviso: sin revisión preliminar para {c['tema']}")
            continue
        frag = txt_a_html(src.read_text(encoding="utf-8"),
                          f"Revisión preliminar · {c['tema']}")
        (V_DOCENTE / f"rev_{c['tema']}.enc").write_bytes(cifrar(frag.encode(), k_d))
        n += 1
    for nombre, fuente, conv in [
            ("informe_preliminar", ORIGEN / "INFORME_PRELIMINAR.md", md_a_html),
            ("clave_profesor", ORIGEN / "CLAVE_PROFESOR.md", md_a_html),
            ("metricas", ORIGEN / "metricas.json",
             lambda t: f"<h2>metricas.json</h2><pre>{html.escape(t)}</pre>")]:
        if not fuente.exists():
            raise SystemExit(f"falta {fuente}")
        (V_DOCENTE / f"{nombre}.enc").write_bytes(
            cifrar(conv(fuente.read_text(encoding="utf-8")).encode(), k_d))
        n += 1
    print(f"zona docente: {n} ficheros cifrados en {V_DOCENTE.name}/")

    # ---- retirada de la zona en claro de la version anterior ----
    if PUBLICO_VIEJO.exists():
        shutil.rmtree(PUBLICO_VIEJO)
        print(f"retirada la zona en claro {PUBLICO_VIEJO.name}/ de la versión anterior")

    INDEX.write_text(construir_index(casos, cfg_alumno, cfg_docente), encoding="utf-8")
    print(f"escrito {INDEX.name}")

    for z in (V_ALUMNO, V_DOCENTE):
        mb = sum(f.stat().st_size for f in z.rglob("*") if f.is_file()) / 1048576
        print(f"  {z.name}: {mb:.1f} MB")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
