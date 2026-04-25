# Tesis de Proyecto

## Qué es

Vota Con La Chola es una infraestructura cívica de evidencia pública, no un asistente de opinión.

- Parte de una hipótesis simple: la decisión política necesita métodos de verificación similares a una auditoría pública.
- Mantiene una cadena reproducible de datos (origen público -> normalización -> inferencia de postura -> señal de cobertura/incertidumbre -> publicación por snapshot).
- Prioriza transparencia operativa sobre “magia analítica”: cada métrica debe poder reconducirse a evidencia y a consultas reproducibles.

La visión y misión de esta base se define en `docs/roadmap.md` como comparar lo prometido, lo hecho y el impacto observable por ámbito territorial.

## A quién sirve primero

Primera audiencia objetivo:

- **Ciudadanía de decisión rápida**: quiere una lectura accionable sobre 1-3 preocupaciones concretas en pocos minutos, con trazabilidad desde la primera fila de resultado.
- **Ciudadanía escéptica (modo auditoría)**: necesita abrir la evidencia fuente y aceptar explícitamente la incertidumbre cuando faltan señales.
- **Usuarios de verificación (citizen/tema/SQL)**: analistas, periodistas o investigadores que usan el contexto de temas y explorer para revisar una afirmación específica.

Esto está alineado con los flujos ideales en `docs/personas-y-flujos-ideales.md` y con la interfaz de inicio de `ui/citizen/index.html` y `ui/placeholder-site/index.html`.

## Qué podemos reclamar hoy

- El stack base es operativo:
  - un flujo UL `ETL -> SQLite -> snapshots` documentado y reproducible;
  - identificadores estables y upserts idempotentes en ingesta;
  - trazabilidad técnica (`source_id`, `source_record`, `source_url`, raw/hash cuando aplica).
- Se está construyendo una capa de acción parlamentaria robusta:
  - representantes/mandatos;
  - votaciones de Congreso/Senado;
  - iniciativa y tema como ejes de evidencia en curso de cierre.
- La capa pública visible refleja el contrato de evidencia primero:
  - **match/mismatch/unknown** en lugar de “recomendación cerrada”;
  - avisos explícitos de cobertura/frescura y límites de comparabilidad.
- Hay un punto de partida fuerte para el uso público:
  - snapshots de `citizen` y de votaciones;
  - publicación periódica en repositorio y en Hugging Face.

## Qué no debe reclamar todavía

- No promete una verdad absoluta ni una recomendación de voto única.
- No asume causalidad de impacto salvo cuando exista diseño metodológico defendible.
- No cubre todavía “todo lo político” en territorio español:
  - la implementación prioriza ejes y dominios concretos en vez de cobertura total;
  - hay huecos de fuentes y cobertura por jurisdicción.
- No puede garantizar “número real de tiempo” del día de la decisión por diseño actual (la señal depende de refrescos por snapshot).
- No reemplaza revisión jurídica, auditoría judicial o análisis financiero técnico; aporta evidencia navegable para facilitar esos análisis.

## Qué marco queremos construir de largo plazo

El marco de accountability del proyecto debe madurar en tres planos conectados:

1. **Decir (dicen)**
   - claims y programas con trazabilidad textual y reglas de revisión humana para ambigüedad.
2. **Hacer (hacen)**
   - acción parlamentaria e institucional (votos, iniciativas, normativa y ejecución) normalizada como eventos auditables.
3. **Impacto (cuando sea defensible)**
   - estimaciones públicas con supuestos explícitos, incertidumbre y límites de identificación.

La operación se mantiene “KISS” siempre que sea posible:
- esquemas aditivos en SQLite;
- PK/FK navegables en Explorer;
- evidencia como contrato central de calidad;
- controles de privacidad y reproducibilidad como parte del flujo, no como añadido de fase final.

El objetivo no es cerrar el ciclo de una vez; es abrirlo con fiabilidad para que cada mejora futura sea medible y verificable.
