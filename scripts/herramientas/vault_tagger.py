# -*- coding: utf-8 -*-
"""
Vault Tagger — detecta el tipo de cada nota Markdown y agrega/actualiza
YAML frontmatter con tags para Obsidian Graph View.

Uso:
  python scripts/herramientas/vault_tagger.py          # etiqueta todo el vault
  python scripts/herramientas/vault_tagger.py --dry    # solo muestra cambios sin escribir
"""
import sys
import re
from pathlib import Path

VAULT = Path(__file__).parent.parent.parent

EXCLUDE = {
    "node_modules", ".venv", "__pycache__", ".git", ".claude",
    ".obsidian", "data", ".idea",
}

# Reglas de deteccion: (funcion_match, lista_de_tags)
def detect_tags(path: Path, content: str) -> list:
    rel = path.relative_to(VAULT)
    parts = rel.parts
    tags = []

    # Por ubicacion
    if parts[0] == "diario":
        if "_prompt" in path.stem:
            tags += ["sesion", "prompt"]
        elif "_cambios" in path.stem:
            tags += ["sesion", "cambios"]
        else:
            tags.append("sesion")

    elif parts[0] == "contexto":
        tags.append("contexto")
        if "CONTEXTO" in path.stem.upper():
            tags.append("fuente-de-verdad")
        if "estado_proyecto" in path.stem:
            tags.append("estado")
        if "fuentes" in path.stem:
            tags.append("fuentes-datos")

    elif parts[0] in ("scripts", "src"):
        tags.append("codigo")
        if "pipeline" in str(rel):
            tags.append("pipeline")
        if "extractores" in str(rel):
            tags.append("extractor")
        if "herramientas" in str(rel):
            tags.append("herramienta")

    # Por nombre de archivo
    stem_lower = path.stem.lower()
    if "arquitectura" in stem_lower or "adr" in stem_lower or "separation" in stem_lower:
        tags.append("arquitectura")
    if "claude" in stem_lower:
        tags.append("configuracion")
    if "indice" in stem_lower or "index" in stem_lower:
        tags.append("indice")

    # Por contenido
    if "GET /api/" in content or "POST /api/" in content:
        tags.append("api")
    if "pipeline_maestro" in content or "scripts/pipeline" in content:
        tags.append("pipeline")
    if "[[" in content:
        tags.append("enlazada")
    if "## Proximos pasos" in content or "## Próximos pasos" in content:
        tags.append("planificacion")

    return sorted(set(tags))


FRONTMATTER_RE = re.compile(r"^---\n(.*?)\n---\n", re.DOTALL)
TAGS_RE = re.compile(r"^tags:.*$", re.MULTILINE)


def update_file(path: Path, dry: bool = False) -> bool:
    try:
        text = path.read_text(encoding="utf-8")
    except Exception:
        return False

    tags = detect_tags(path, text)
    if not tags:
        return False

    tags_line = "tags: [" + ", ".join(tags) + "]"

    match = FRONTMATTER_RE.match(text)
    if match:
        fm = match.group(1)
        if TAGS_RE.search(fm):
            new_fm = TAGS_RE.sub(tags_line, fm)
        else:
            new_fm = fm + "\n" + tags_line
        new_text = f"---\n{new_fm}\n---\n" + text[match.end():]
    else:
        new_text = f"---\n{tags_line}\n---\n\n" + text

    if new_text == text:
        return False

    print(f"  {path.relative_to(VAULT)}  ->  {tags}")
    if not dry:
        path.write_text(new_text, encoding="utf-8")
    return True


def should_skip(path: Path) -> bool:
    for part in path.relative_to(VAULT).parts:
        if part in EXCLUDE or part.startswith("."):
            return True
    return False


def run(dry: bool = False):
    changed = 0
    for md in VAULT.rglob("*.md"):
        if should_skip(md):
            continue
        if update_file(md, dry):
            changed += 1
    print(f"\n{'[DRY]' if dry else '[OK]'} {changed} archivos {'modificados' if not dry else 'que cambiarian'}.")


if __name__ == "__main__":
    dry = "--dry" in sys.argv
    if dry:
        print("Modo DRY — no se escribe nada.\n")
    run(dry)
