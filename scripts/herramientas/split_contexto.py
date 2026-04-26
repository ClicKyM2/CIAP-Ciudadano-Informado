# -*- coding: utf-8 -*-
"""
split_contexto.py — Divide CONTEXTO.md en sub-notas Obsidian.
Crea archivos en contexto/sub/ y reemplaza CONTEXTO.md con un hub de enlaces.

Uso:
  python scripts/herramientas/split_contexto.py
"""
from pathlib import Path
import re

VAULT = Path(__file__).parent.parent.parent
SRC = VAULT / "contexto" / "CONTEXTO.md"
DEST = VAULT / "contexto" / "sub"

# Mapeo: titulo de seccion (## ...) -> nombre de archivo destino
SPLIT_MAP = {
    "Estado actual de la base de datos": "Estado_DB",
    "Esquema real de la tabla": "Esquema_Candidato",
    "La IA Fiscalizadora": "IA_Fiscalizadora",
    "API Node.js": "API_Endpoints",
    "Frontend HTML": "Frontend_HTML",
    "Fuentes de datos": "Fuentes_Datos",
    "Archivos clave del proyecto": "Archivos_Clave",
    "Scripts del pipeline": "Pipeline_Scripts",
    "Orden de ejecución del pipeline": "Pipeline_Scripts",  # se une a anterior
    "Notas técnicas importantes": "Notas_Tecnicas",
    "Próximos pasos": "Proximos_Pasos",
}

# Secciones que se QUEDAN en CONTEXTO.md (hub)
KEEP_IN_HUB = {
    "REGLAS OBLIGATORIAS",
    "INSTRUCCIONES PARA CLAUDE",
    "es este proyecto",
    "Arquitectura",
    "Archivos de seguimiento",
    "Variables de entorno",
    "ÍNDICE DE SECCIONES",
}

TAGS = {
    "Estado_DB": ["contexto", "estado", "base-de-datos"],
    "Esquema_Candidato": ["contexto", "base-de-datos", "esquema"],
    "IA_Fiscalizadora": ["contexto", "pipeline", "ia"],
    "API_Endpoints": ["contexto", "api"],
    "Frontend_HTML": ["contexto", "api", "frontend"],
    "Fuentes_Datos": ["contexto", "fuentes-datos"],
    "Archivos_Clave": ["contexto", "indice"],
    "Pipeline_Scripts": ["contexto", "pipeline"],
    "Notas_Tecnicas": ["contexto", "configuracion"],
    "Proximos_Pasos": ["contexto", "planificacion"],
}


def get_dest_for(title: str) -> str | None:
    for key, dest in SPLIT_MAP.items():
        if key.lower() in title.lower():
            return dest
    return None


def should_keep(title: str) -> bool:
    for k in KEEP_IN_HUB:
        if k.lower() in title.lower():
            return True
    return False


def frontmatter(file_stem: str) -> str:
    tags = TAGS.get(file_stem, ["contexto"])
    tag_str = "[" + ", ".join(tags) + "]"
    return f"---\ntags: {tag_str}\n---\n\n"


def backlink(file_stem: str) -> str:
    return f"\n\n---\n*Sub-nota de [[CONTEXTO]] · [[Indice_Arquitectura]]*\n"


def run():
    DEST.mkdir(exist_ok=True)
    text = SRC.read_text(encoding="utf-8")

    # Eliminar frontmatter existente si lo hay
    text = re.sub(r"^---\n.*?\n---\n\n?", "", text, flags=re.DOTALL)

    # Partir en secciones por "## "
    parts = re.split(r"(?=^## )", text, flags=re.MULTILINE)

    buckets: dict[str, list[str]] = {}  # file_stem -> [section_text, ...]
    hub_parts: list[str] = []

    for part in parts:
        if not part.strip():
            continue
        # Extraer titulo
        first_line = part.split("\n", 1)[0]
        title = first_line.lstrip("#").strip()

        dest = get_dest_for(title)

        if dest is None or should_keep(title):
            hub_parts.append(part)
        else:
            buckets.setdefault(dest, []).append(part)

    # Escribir sub-notas
    written = []
    for stem, sections in buckets.items():
        out_path = DEST / f"{stem}.md"
        content = frontmatter(stem) + "\n".join(sections).strip() + backlink(stem)
        out_path.write_text(content, encoding="utf-8")
        written.append(stem)
        print(f"  -> contexto/sub/{stem}.md")

    # Construir hub actualizado
    hub_links = "\n".join(
        f"- [[sub/{stem}]]" for stem in sorted(set(SPLIT_MAP.values()))
    )
    hub_header = (
        "---\ntags: [contexto, fuente-de-verdad, planificacion]\n---\n\n"
        "# CONTEXTO DEL PROYECTO — CIUDADANO INFORMADO (CIAP)\n\n"
        "> Archivo hub. Las secciones extensas viven en sub-notas enlazadas abajo.\n\n"
        "## Sub-notas\n\n"
        + hub_links
        + "\n\n---\n\n"
    )

    hub_body = "\n".join(hub_parts)
    # Quitar el primer encabezado H1 si existe (ya lo ponemos en hub_header)
    hub_body = re.sub(r"^# .+\n\n?", "", hub_body)

    SRC.write_text(hub_header + hub_body, encoding="utf-8")
    print(f"\n[OK] {len(written)} sub-notas creadas. CONTEXTO.md actualizado como hub.")


if __name__ == "__main__":
    run()
