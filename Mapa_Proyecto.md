---
tags: [enlazada]
---

# Mapa del Proyecto — CIAP

Hub principal. Representa la estructura completa del proyecto Ciudadano Informado.

---

## Documentacion y arquitectura

- [[CLAUDE]] — Reglas del sistema para Claude Code
- [[Indice_Arquitectura]] — Indice de decisiones arquitectonicas
- [[contexto/CONTEXTO]] — Estado, pipeline, API, frontend (hub doc)

## Base de datos

- [[db/PostgreSQL]] — Hub PostgreSQL: 18 tablas, 5 fuentes, anomalias criticas
  - [[db/Tabla_Candidato]] — Tabla central del proyecto
  - [[db/Tabla_Lobby]] — Cruces lobby (atencion: empresa_rut=NULL)
  - [[db/Tabla_Empresas]] — Participacion societaria + enriquecimiento SII/CMF
  - [[db/Tabla_Congreso]] — Diputados, votaciones, proyectos de ley
  - [[db/Tabla_Alertas]] — alerta_probidad generada por la IA

## Fuentes de datos

- [[fuentes/CPLT]] — InfoProbidad: declaraciones y empresas
- [[fuentes/Lobby]] — InfoLobby: audiencias y representaciones
- [[fuentes/Servel]] — Financiamiento electoral 2024
- [[fuentes/Congreso]] — Camara + BCN: votaciones y proyectos
- [[fuentes/Mercado_Publico]] — Licitaciones y ordenes de compra OCDS

## Codigo

- [[scripts/Extractores]] — Scripts de descarga por fuente
- [[scripts/Pipeline_Pasos]] — Los 18 pasos del pipeline de datos
- [[scripts/Herramientas]] — Utilidades del vault y del pipeline
- [[src/API_Node]] — API REST Node.js/Express

## Arquitectura tecnica

- [[arquitectura/Stack_Tecnologico]] — Rol de cada tecnologia
- [[arquitectura/Flujo_Pipeline]] — Diagrama de los 18 pasos
- [[arquitectura/Modelo_Datos]] — Relaciones entre tablas nucleares
- [[Separation_of_Concerns]] — ADR-001: separacion de capas

## Sesiones de trabajo

- [[diario/INDEX]] — Diario automatico de sesiones

---

## Lineaje de datos

```
Fuentes → Extractores → Pipeline → DB → API → Frontend
```

[[fuentes/CPLT]] + [[fuentes/Lobby]] + [[fuentes/Servel]] + [[fuentes/Congreso]] + [[fuentes/Mercado_Publico]]
  → [[scripts/Extractores]]
  → [[scripts/Pipeline_Pasos]]
  → [[db/PostgreSQL]]
  → [[src/API_Node]]
  → [[contexto/sub/Frontend_HTML]]
