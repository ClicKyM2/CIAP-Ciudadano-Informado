"""
Obsidian Logger — registra prompts y acciones de Claude Code como notas Markdown.
Llamado desde hooks en .claude/settings.json.

Uso:
  echo '<json>' | python obsidian_logger.py prompt
  echo '<json>' | python obsidian_logger.py tool
  echo '<json>' | python obsidian_logger.py session_end
"""
import sys
import json
from datetime import datetime
from pathlib import Path

VAULT = Path(__file__).parent.parent.parent  # raiz de CIAP
DIARIO = VAULT / "diario"

_session_key = None  # se fija al primer prompt del turno


def _get_key():
    return datetime.now().strftime("%H-%M")


def _today():
    return datetime.now().strftime("%Y-%m-%d")


def _date_dir():
    d = DIARIO / _today()
    d.mkdir(parents=True, exist_ok=True)
    return d


def _latest_key():
    """Devuelve la clave del ultimo prompt del dia (para asociar cambios)."""
    d = DIARIO / _today()
    if not d.exists():
        return _get_key()
    prompts = sorted(d.glob("*_prompt.md"), reverse=True)
    if prompts:
        return prompts[0].stem.replace("_prompt", "")
    return _get_key()


def handle_prompt(data):
    prompt = data.get("prompt", "").strip()
    key = _get_key()
    d = _date_dir()
    date = _today()

    prompt_path = d / f"{key}_prompt.md"
    cambios_path = d / f"{key}_cambios.md"

    prompt_path.write_text(
        f"---\n"
        f"tipo: prompt\n"
        f"fecha: {date}\n"
        f"hora: {key.replace('-', ':')}\n"
        f"---\n\n"
        f"# Prompt {key} — {date}\n\n"
        f"{prompt}\n\n"
        f"## Vínculos\n"
        f"[[diario/{date}/{key}_cambios]] · [[Indice_Arquitectura]]\n",
        encoding="utf-8",
    )

    if not cambios_path.exists():
        cambios_path.write_text(
            f"---\n"
            f"tipo: cambios\n"
            f"fecha: {date}\n"
            f"hora: {key.replace('-', ':')}\n"
            f"---\n\n"
            f"# Cambios {key} — {date}\n\n"
            f"> Origen: [[diario/{date}/{key}_prompt]]\n\n"
            f"## Acciones\n\n",
            encoding="utf-8",
        )


def handle_tool(data):
    tool_name = data.get("tool_name", "")
    if tool_name not in ("Write", "Edit", "Bash"):
        return

    tool_input = data.get("tool_input", {})
    key = _latest_key()
    cambios_path = _date_dir() / f"{key}_cambios.md"

    if not cambios_path.exists():
        return

    now = datetime.now().strftime("%H:%M:%S")

    if tool_name in ("Write", "Edit"):
        file_path = tool_input.get("file_path", "")
        try:
            rel = Path(file_path).relative_to(VAULT)
            rel_str = str(rel).replace("\\", "/")
            link = rel_str[:-3] if rel_str.endswith(".md") else None
            entry = (
                f"- `{now}` [edit] {tool_name} -> [[{link}]]\n"
                if link
                else f"- `{now}` [edit] {tool_name} -> `{rel_str}`\n"
            )
        except ValueError:
            entry = f"- `{now}` [edit] {tool_name} -> `{file_path}`\n"
    else:
        cmd = tool_input.get("command", "").replace("\n", " ")[:120]
        entry = f"- `{now}` [bash] -> `{cmd}`\n"

    with open(cambios_path, "a", encoding="utf-8") as f:
        f.write(entry)


def handle_session_end(data):
    """Crea o actualiza resumen_sesion.md con todos los prompts y cambios del dia."""
    date = _today()
    d = DIARIO / date
    if not d.exists():
        sys.exit(0)

    prompts = sorted(d.glob("*_prompt.md"))
    cambios = sorted(d.glob("*_cambios.md"))

    resumen_path = d / "resumen_sesion.md"

    lineas_prompts = []
    for p in prompts:
        try:
            texto = p.read_text(encoding="utf-8")
            # Extrae el contenido real (despues del frontmatter y el titulo)
            partes = texto.split("\n\n", 2)
            cuerpo_raw = partes[2] if len(partes) > 2 else ""
            # Cortar antes de la seccion de vinculos (con o sin tilde)
            for sep in ("## Vínculos", "## Vinculos"):
                if sep in cuerpo_raw:
                    cuerpo_raw = cuerpo_raw.split(sep)[0]
            cuerpo = cuerpo_raw.strip()
            hora = p.stem.replace("_prompt", "").replace("-", ":")
            lineas_prompts.append(f"### {hora}\n{cuerpo[:300]}{'...' if len(cuerpo) > 300 else ''}")
        except Exception:
            lineas_prompts.append(f"- {p.stem}")

    lineas_cambios = []
    for c in cambios:
        try:
            texto = c.read_text(encoding="utf-8")
            acciones = [l for l in texto.splitlines() if l.startswith("- `")]
            if acciones:
                lineas_cambios.extend(acciones[:20])
        except Exception:
            pass

    contenido = (
        f"---\n"
        f"tipo: resumen-sesion\n"
        f"fecha: {date}\n"
        f"---\n\n"
        f"# Resumen de Sesion — {date}\n\n"
        f"**Prompts:** {len(prompts)} | **Archivos con cambios:** {len(cambios)}\n\n"
    )

    if lineas_prompts:
        contenido += "## Prompts de la sesion\n\n" + "\n\n".join(lineas_prompts) + "\n\n"

    if lineas_cambios:
        contenido += "## Cambios registrados\n\n" + "\n".join(lineas_cambios[:30]) + "\n\n"

    contenido += "## Vinculos\n[[Indice_Arquitectura]] · [[contexto/CONTEXTO]]\n"

    resumen_path.write_text(contenido, encoding="utf-8")


if __name__ == "__main__":
    event = sys.argv[1] if len(sys.argv) > 1 else ""
    try:
        data = json.loads(sys.stdin.read())
    except Exception:
        data = {}

    if event == "prompt":
        handle_prompt(data)
    elif event == "tool":
        handle_tool(data)
    elif event == "session_end":
        handle_session_end(data)
