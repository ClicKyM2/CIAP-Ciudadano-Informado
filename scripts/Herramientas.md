---
tags: [codigo, enlazada]
---

# Herramientas — scripts/herramientas/

Ver [[Mapa_Proyecto]] · [[scripts/Pipeline_Pasos]] · [[scripts/Extractores]]

---

## Scripts de herramientas

| Script | Propósito |
|--------|-----------|
| `vault_tagger.py` | Escanea todos los `.md` del vault, detecta tipo por path/contenido, añade/actualiza YAML frontmatter con `tags:` |
| `obsidian_logger.py` | Crea notas de diario en `diario/YYYY-MM-DD/` al recibir un prompt o al usar herramientas |
| `split_contexto.py` | Divide CONTEXTO.md por `## ` headers en sub-notas en `contexto/sub/` |
| `consolidador_maestro.py` | Consolida archivos `funcionarios_rescatados*.csv` en `MAESTRO_RUTS_CONSOLIDADOS.csv` |
| `cruce_infoprobidad.py` | Match nombres normalizado entre csvdeclaraciones.csv y tabla candidato. Asigna `uri_declarante`. |
| `arreglar_columnas.py` | Ajusta estructura del CSV de asistencias pasivas a 10 columnas |
| `revisar_columnas.py` | Diagnóstico: inspecciona columnas de cualquier CSV |

---

## vault_tagger.py

Detecta tipo de nota según ruta:
- `contexto/sub/` → tags: `[contexto, enlazada]`
- `db/` → tags: `[db, enlazada]`
- `fuentes/` → tags: `[fuentes-datos, extractor]`
- `arquitectura/` → tags: `[arquitectura, enlazada]`
- `scripts/` → tags: `[scripts, enlazada]`
- `diario/` → tags: `[diario]`

```bash
.venv/Scripts/python.exe scripts/herramientas/vault_tagger.py
```

## obsidian_logger.py

Llamado por hooks de Claude Code:
- `UserPromptSubmit` → crea `diario/YYYY-MM-DD/HH-MM_prompt.md`
- `PostToolUse` (Write|Edit|Bash) → crea `diario/YYYY-MM-DD/HH-MM_cambios.md`

Configurado en `.claude/settings.json`. Usa Python del sistema (no del venv).

---

*Sub-nota de [[Mapa_Proyecto]] · [[scripts/Pipeline_Pasos]]*
