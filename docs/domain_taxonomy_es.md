# Taxonomía de dominios (España)

Version: `v1`

Objetivo: definir **ámbitos políticos (dominios)** para España con una lista priorizada (Tier 1/2/3) que sirva como:
- base del `codebook` (ejes por dominio),
- capa de agregación para “acción revelada” (vector por dominio),
- y contrato estable para evolucionar el esquema (`domains`, `policy_axes`) sin inventar “índices morales”.

Nota: esto no es lo mismo que `topics` (temas concretos y trazables a evidencia). Los `topics` son granularidad “de expediente/medida”; los **dominios** son la capa “de ámbito” para agregación y navegación.

## Tier 1 (prioridad máxima)

| canonical_key | label |
|---|---|
| `economia_empleo` | Economía y empleo |
| `coste_vida` | Coste de vida (inflación, energía, cesta básica) |
| `sanidad_salud_publica` | Sanidad y salud pública |
| `educacion_capital_humano` | Educación y capital humano |
| `vivienda_urbanismo` | Vivienda y urbanismo |
| `impuestos_gasto_fiscalidad` | Impuestos, gasto público y sostenibilidad fiscal |
| `justicia_seguridad` | Justicia, seguridad y orden público |
| `energia_medio_ambiente` | Energía y medio ambiente |
| `infraestructura_transporte` | Infraestructura y transporte |
| `proteccion_social_pensiones` | Protección social y pensiones |

## Tier 2 (alto impacto, algo más mediado)

| canonical_key | label |
|---|---|
| `ciencia_innovacion_digitalizacion` | Ciencia, innovación y digitalización |
| `regulacion_empresarial_competencia` | Regulación empresarial y competencia |
| `migracion_integracion` | Migración e integración |
| `calidad_administrativa` | Calidad administrativa, burocracia y servicios públicos |
| `agricultura_alimentacion_rural` | Agricultura, alimentación y mundo rural |
| `industria_comercio_exterior_economico` | Industria, comercio y política exterior económica |
| `adaptacion_climatica_riesgos` | Adaptación climática y gestión de riesgos |
| `proteccion_consumidor` | Protección del consumidor |

## Tier 3 (útil, normalmente fuera del núcleo)

| canonical_key | label |
|---|---|
| `cultura_medios_deporte` | Cultura, medios y deporte |
| `politica_exterior_defensa` | Política exterior y defensa |
| `turismo` | Turismo |
| `igualdad_juventud_cohesion_territorial` | Igualdad, juventud y cohesión territorial |
| `medidas_simbolicas_protocolo` | Medidas simbólicas y protocolo |

## Reglas (KISS)

- Los `canonical_key` deben ser **estables** (no se renombran; si cambia el significado, se crea uno nuevo y se depreca el anterior).
- Un evento puede mapear a 1 dominio “principal” y, opcionalmente, a dominios secundarios (si los añadimos, deben ser explícitos y auditables).
- Esta taxonomía debe mapear 1:1 con la tabla SQLite `domains(canonical_key, label, tier)` cuando se empiece a poblar.

