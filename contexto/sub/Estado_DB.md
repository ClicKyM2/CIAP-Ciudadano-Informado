---
tags: [contexto, enlazada]
---

## Estado actual de la base de datos (PostgreSQL 18)

### Resumen numérico — verificado 2026-04-25 (sesión 12)

**Funcionarios**
| Métrica | Valor |
|---------|-------|
| Total candidatos en DB | 6.801 (+116 Gobierno Kast) |
| Con RUT real | 5.601 |
| Con uri_declarante (vinculados a CPLT) | 6.513 |
| Sin RUT visible en CPLT (privacidad) | ~1.002 — incluye nuevos Kast sin RUT aún |
| Con score_transparencia calculado | 6.801 |
| Score promedio | 46.5 / 100 |

**Empresas**
| Métrica | Valor |
|---------|-------|
| Participaciones societarias declaradas | 6.903 |
| Candidatos con al menos 1 empresa declarada | 2.556 |
| Empresas únicas en participacion_societaria | 2.782 |
| Empresas enriquecidas con datos SII (100%) | 2.782 / 2.782 |
| Registros directorio CMF | 5.766 |

**Alertas de probidad**
| Tipo | Total | Gravedad |
|------|-------|---------|
| AUTOLOBBY_DETECTADO | 30 | ALTA |
| DIRECTOR_NO_DECLARADO | 5 | ALTA |
| CONFLICTO_FAMILIAR_POSIBLE | ~563 | MEDIA/BAJA |
| **TOTAL** | **~598** | 35 ALTA · ~563 MEDIA/BAJA |

**Lobby**
| Métrica | Valor |
|---------|-------|
| Matches candidato-lobby | 503.007 |
| Audiencias de lobby | 894.157 |
| Representaciones (entidades privadas) | 1.548.503 |

**Declaraciones CPLT**
| Métrica | Valor |
|---------|-------|
| Declaraciones importadas (declaracion_cplt) | 118.760 |
| CSV actual (csvdeclaraciones.csv) | 118.458 filas (incluye Gobierno Kast parcial) |

**Congreso**
| Métrica | Valor |
|---------|-------|
| Diputados registrados (leg 50-58) | 335 (335/335 vinculados a candidato) |
| Sesiones | 1.125 (leg 50-58 completa) |
| Votaciones | 7.180 |
| Votos individuales | 947.256 |
| Registros de asistencia | 376.875 |

---

### Tablas principales

| Tabla | Registros | Estado |
|-------|-----------|--------|
| candidato | 6.801 (5.601 RUT real). 6.513 con uri_declarante. +116 Gobierno Kast sesión 11. | Activo |
| financiamiento_electoral | 15.739 (2.402 vinculados a candidato) | SERVEL 2024 definitivo |
| donante_electoral | 338.911 transacciones. 12.255 donantes únicos | SERVEL 2024 definitivo |
| cargo | 30+ | MINISTRO, SEREMI, JEFE DE GABINETE, INTENDENTE, etc. |
| partido | variable | partido_id=NULL para todos los candidatos reales |
| participacion_societaria | 6.903 | Desde csvacciones.csv (bulk CPLT) + scraping sesiones 6-8 |
| empresa_enriquecida | 2.782 | 100% enriquecidas con SII via csvacciones.csv |
| directorio_cmf | 5.766 | Actualizado sesión 8 |
| declaracion_cplt | 118.760 | Vinculadas via uri_declarante. CSV Kast parcial cargado sesión 11. |
| alerta_probidad | ~598 | 35 ALTA · ~563 MEDIA/BAJA |
| reunion_lobby | 4.805.778 | empresa_rut=NULL en TODAS — NO usar para cruce |
| licitacion | En ingesta (sesión 9) | Licitaciones adjudicadas a empresas de candidatos. Fuente: OCDS bulk ZIP + API OCDS |
| proyecto_ley | 7.933 | Mociones de diputados. Columnas: boletin (UNIQUE), titulo, fecha_ingreso, tipo_iniciativa, camara_origen, legislatura, link |
| autoria_proyecto | variable | Relación candidato↔proyecto. Columnas: proyecto_id, candidato_id, autor_nombre. UNIQUE(proyecto_id, candidato_id) |
| diputado_camara | 335 | 335/335 con candidato_id |
| sesion_camara | 1.125 | Leg 50-58 completa |
| votacion_camara | 7.180 | VIDs leg 57/58 en rango 80K-85K |
| voto_diputado | 947.256 | Votos individuales por diputado |
| asistencia_sesion | 376.875 | 112K presencias + 264K inasistencias |

### Tablas temporales (para cruces lobby)

| Tabla | Registros | Descripción |
|-------|-----------|-------------|
| temp_audiencia | 894.157 | Audiencias de lobby completas |
| temp_asistencia_pasivo | 894.251 | Relación audiencia-pasivo |
| match_candidato_lobby | 503.007 | Matches candidatos vs lobby (rut, codigo_pasivo) |
| temp_representaciones | 1.548.503 | Entidades privadas que hicieron lobby (UTF-16) |

---

---
*Sub-nota de [[CONTEXTO]] · [[Indice_Arquitectura]]*
