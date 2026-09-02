# ¿Por qué tus alumnos están dormidos a las 8 de la mañana?

Página divulgativa autocontenida sobre el desajuste entre el reloj circadiano
adolescente y la hora de entrada al instituto, con datos españoles del Estudio
HBSC-2022, evidencia experimental sobre el retraso de la hora de entrada y los
datos solares de Madrid.

Publicada en <https://eduardogarrido90.github.io/sueno/>.

## Estructura

    index.html                  página final, un solo fichero, sin dependencias
    build.py                    generador: datos + figuras SVG + HTML
    data/astro_madrid.json      datos solares usados, con su procedencia
    data/validate_refs.py       cotejo de la bibliografía (Crossref + PubMed)
    data/validate_claims.py     cotejo de cada cifra contra el texto fuente
    data/validate_astro.py      cotejo de los datos solares contra el USNO
    data/refs_cache/            metadatos y textos descargados (auditable)

`index.html` es generado: no se edita a mano. Todo el contenido, incluidos los
porcentajes y las figuras, se declara en `build.py`.

## Regenerar

    python3 build.py

El generador falla si las tablas del HBSC no suman 100 %, si los agregados
calculados por suma no reproducen las cifras que el informe publica como texto,
o si alguna cifra del HTML queda escrita con punto decimal en lugar de coma.

## Validar

    python3 data/validate_refs.py    --verbose   # metadatos bibliográficos
    python3 data/validate_claims.py              # cifras en su fuente
    python3 data/validate_astro.py               # amanecer y mediodía solar

Los tres terminan con código distinto de cero ante cualquier discrepancia.
Añadir `--refresh` fuerza a volver a descargar las fuentes en lugar de usar la
caché.

## Fuentes de datos

- Estudio HBSC-2022 en España (Ministerio de Sanidad, 2025), tablas 19 y 20,
  n = 33.630 adolescentes de 11 a 18 años.
- US Naval Observatory, Astronomical Applications API, para Madrid
  (40,4168 N; −3,7038).
- 15 artículos con DOI, cotejados campo a campo contra Crossref y PubMed.
