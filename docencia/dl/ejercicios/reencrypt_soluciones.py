#!/usr/bin/env python3
"""Regenera los .enc de soluciones a partir de los PDFs de materiales/.

Formato exigido por docencia/assets/vault.js:
    fichero .enc = iv(12 bytes) || AES-GCM(ciphertext || tag)
    clave        = PBKDF2-SHA256(password, salt, iters) -> AES-256-GCM

El salt y el número de iteraciones se leen del CFG incrustado en index.html,
de modo que este script no puede desincronizarse de la página.

Hay dos secciones con soluciones cifradas y este script cubre las dos:

    ejercicios/sol/            dia_NN.enc           ejercicio del día de la sesión
    ejercicios_ampliacion/sol/ dia_NN_del_dia.enc   ejercicios del día de los
                               días 07, 09 y 10, que pasaron a ampliación

Ambas usan la misma contraseña de clase, pero cada una lee su propio CFG: si
alguna vez se separan las contraseñas, el script sigue siendo correcto sin
tocar nada. El número de día se extrae del nombre con una expresión regular,
no cortando el prefijo, precisamente para que el sufijo `_del_dia` no rompa la
búsqueda del PDF de origen.

La contraseña se pide por getpass: no se pasa por argv (quedaría en el
historial del shell), no se imprime y no se escribe en disco. Antes de cifrar
nada se verifica contra el token `check` de cada index.html, así que una
contraseña equivocada aborta sin tocar un solo fichero.

Uso:
    python3 reencrypt_soluciones.py            # regenera los que estén obsoletos
    python3 reencrypt_soluciones.py --todos    # regenera todos
"""
from __future__ import annotations

import argparse
import getpass
import json
import os
import re
import sys
from pathlib import Path

try:
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
except ImportError:
    sys.exit("Falta el paquete 'cryptography'. Instala con: pip install cryptography")

import base64

AQUI = Path(__file__).resolve().parent
AMPLIACION = AQUI.parent / "ejercicios_ampliacion"
MATERIALES = Path("/home/eduardo/docencia/DL_26_27/materiales")

# (nombre para los mensajes, index.html del que sale el CFG, carpeta de .enc)
SECCIONES = [
    ("ejercicios", AQUI / "index.html", AQUI / "sol"),
    ("ampliación", AMPLIACION / "index.html", AMPLIACION / "sol"),
]


def leer_cfg(index: Path) -> tuple[bytes, bytes, int]:
    """Extrae (salt, check, iters) del CFG de index.html.

    Devuelve salt y check ya decodificados de base64.
    """
    texto = index.read_text(encoding="utf-8")
    m = re.search(r"const\s+CFG\s*=\s*(\{.*?\})\s*;", texto, re.S)
    if not m:
        raise SystemExit(f"No encuentro el objeto CFG en {index}")
    # el literal JS usa claves sin comillas: las añadimos para poder leerlo como JSON
    crudo = re.sub(r"(\w+)\s*:", r'"\1":', m.group(1))
    cfg = json.loads(crudo)
    return (base64.b64decode(cfg["salt"]),
            base64.b64decode(cfg["check"]),
            int(cfg["iters"]))


def derivar_clave(password: str, salt: bytes, iters: int) -> bytes:
    kdf = PBKDF2HMAC(algorithm=hashes.SHA256(), length=32, salt=salt,
                     iterations=iters)
    return kdf.derive(password.encode("utf-8"))


def verificar(clave: bytes, check: bytes) -> None:
    """Descifra el token de control. Lanza si la contraseña no es la buena."""
    iv, ct = check[:12], check[12:]
    try:
        token = AESGCM(clave).decrypt(iv, ct, None)
    except Exception:
        raise SystemExit("Contraseña incorrecta: no se ha tocado ningún fichero.")
    if token != b"unlock-ok":
        raise SystemExit("El token de control no es 'unlock-ok'; revisa el CFG.")


def cifrar(datos: bytes, clave: bytes) -> bytes:
    """iv(12) || AES-GCM(ciphertext||tag), exactamente como espera vault.js."""
    iv = os.urandom(12)
    return iv + AESGCM(clave).encrypt(iv, datos, None)


def origen_soluciones(num: str) -> Path | None:
    """PDF de soluciones de ese día dentro de materiales/."""
    for d in MATERIALES.glob(f"dia_{num}_*"):
        p = d / "ejercicios" / "ejercicios_soluciones.pdf"
        if p.exists():
            return p
    return None


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--todos", action="store_true",
                    help="regenera todos, no solo los obsoletos")
    args = ap.parse_args()

    # Se recorre todo y se decide qué hay que hacer antes de pedir la
    # contraseña: así un error de rutas se ve de inmediato y no después de
    # teclearla.
    trabajo = []  # (seccion, num, src, dst, salt, check, iters)
    for nombre, index, sol_dir in SECCIONES:
        if not sol_dir.is_dir():
            raise SystemExit(f"No existe la carpeta de soluciones {sol_dir}")
        salt, check, iters = leer_cfg(index)
        print(f"CFG de {nombre}: iters={iters}, salt={len(salt)} bytes")

        destinos = sorted(sol_dir.glob("dia_*.enc"))
        if not destinos:
            raise SystemExit(f"No hay ficheros .enc en {sol_dir}")

        for dst in destinos:
            m = re.match(r"dia_(\d{2})", dst.stem)
            if m is None:
                raise SystemExit(
                    f"No sé de qué día es {dst}: el nombre tiene que empezar "
                    f"por dia_NN")
            num = m.group(1)
            src = origen_soluciones(num)
            if src is None:
                print(f"  aviso: sin PDF fuente para el día {num} "
                      f"({nombre}), se deja como está")
                continue
            if args.todos or src.stat().st_mtime > dst.stat().st_mtime:
                trabajo.append((nombre, num, src, dst, salt, check, iters))

    if not trabajo:
        print("Todo al día: no hay nada que recifrar.")
        return 0

    print(f"\nSe recifrarán {len(trabajo)} ficheros: "
          f"{', '.join(f'{n} ({s})' for s, n, _, _, _, _, _ in trabajo)}")
    password = getpass.getpass("Contraseña de clase: ")

    # Una clave por sección, verificada contra el token de esa sección antes de
    # escribir nada.
    claves: dict[bytes, bytes] = {}
    for _, _, _, _, salt, check, iters in trabajo:
        if salt not in claves:
            clave = derivar_clave(password, salt, iters)
            verificar(clave, check)
            claves[salt] = clave
    print(f"Contraseña verificada contra {len(claves)} token(s) de control.\n")

    for nombre, num, src, dst, salt, _, _ in trabajo:
        clave = claves[salt]
        datos = src.read_bytes()
        blob = cifrar(datos, clave)
        # comprobación de ida y vuelta antes de escribir: nunca dejamos un .enc
        # que el navegador no pueda abrir
        iv, ct = blob[:12], blob[12:]
        assert AESGCM(clave).decrypt(iv, ct, None) == datos, f"round-trip falló en {num}"
        dst.write_bytes(blob)
        print(f"  día {num} ({nombre}): {src.name} -> {dst.name} "
              f"({len(datos)} -> {len(blob)} bytes, round-trip OK)")

    print(f"\nListo: {len(trabajo)} ficheros recifrados y verificados.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
