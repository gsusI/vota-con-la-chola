# Killer use case

Estado: `v1`
Fecha de decision: `2026-04-04`

## Decision

Para los proximos `3-6` meses, el wedge publico principal debe ser:

- **Vote explainer audit-able para una votacion concreta**

El wedge de apoyo debe ser:

- **Source obstruction tracker**

No debemos liderar todavia con:

- **said-vs-did analysis**

## Frase corta

Cuando una votacion importante haga ruido, cualquier persona debe poder abrir una sola pagina y entender:

- que se voto,
- que paso,
- quien voto como,
- de donde sale la evidencia oficial,
- y que partes siguen siendo inciertas.

## Usuario objetivo

Usuario objetivo principal:

- **ciudadania esceptica con mentalidad de verificacion**

Perfil operativo:

- llega por una votacion o controversia concreta, no por una exploracion abstracta del sistema;
- quiere una respuesta en `2-5` minutos;
- no acepta una conclusion sin fuente primaria y caveats;
- puede ser ciudadano, periodista, analista o creador que luego comparte el caso.

Este usuario encaja mejor con `F-03`, `F-11` y parcialmente `F-01` en `docs/personas-y-flujos-ideales.md`.

## Por que esta es la mejor apuesta ahora

### 1. Ya existe una base de evidencia util

La superficie de votaciones es la mas cercana a una historia publica completa hoy:

- `docs/gh-pages/explorer-votaciones/data/votes-preview.json` publica `502` eventos totales y devuelve `200` en preview.
- En esa preview, `199/200` eventos ya tienen `source_url`.
- `198/200` ya tienen `initiative`.
- `200/200` incluyen `group_breakdown`.
- La preview mezcla `congreso_votaciones` y `senado_votaciones`, o sea, ya hay una base nacional reconocible.

Eso es suficiente para convertir una votacion concreta en una pagina compartible y verificable.

### 2. La promesa es facil de entender

Un vote explainer no requiere que el usuario entienda antes:

- ontologias complejas,
- scores agregados,
- pesos metodologicos,
- o coverage matrices grandes.

Solo exige una pregunta publica muy natural:

- "¿Que se voto realmente y quien voto como?"

### 3. Encaja con la tesis del proyecto sin sobre-prometer

`docs/strategy/project-thesis.md` deja claro que el proyecto hoy puede reclamar:

- cadena reproducible,
- accion parlamentaria robusta en construccion,
- trazabilidad y advertencias explicitas de incertidumbre.

El vote explainer cabe dentro de ese contrato.

No obliga a prometer:

- recomendacion de voto final,
- causalidad,
- cobertura total de todo lo politico,
- ni "truth score" sintetico.

### 4. Tiene mejor potencial de distribucion que el resto del producto actual

Una pagina de voto concreto es:

- enlazable,
- citable,
- facil de compartir,
- y facil de contrastar contra la fuente oficial.

Es mas probable que circule por un caso real que por una home generica o por una tabla agregada.

## Comparativa de wedges

| Opcion | Fortaleza principal | Debilidad principal ahora | Veredicto |
|---|---|---|---|
| Vote explainer | Ya existe base de datos y preview muy util para eventos concretos; promesa simple y compartible | Falta cerrar la pagina canonica y el contrato de caveats | **Primary wedge** |
| Source obstruction tracker | Muy diferencial y muy alineado con accountability institucional; convierte blockers en historia publica verificable | Es mas meta que tarea principal del usuario final; explica por que faltan datos, pero no resuelve primero un caso ciudadano concreto | **Supporting wedge** |
| Said-vs-did analysis | Es la promesa mas ambiciosa y memorable a largo plazo; conecta directamente con la tesis de "dicen vs hacen" | Todavia no esta listo para liderar: `docs/gh-pages/explorer-sources/data/status.json` reporta `topic_evidence_declared_total = 0`, y `docs/gh-pages/legacy/citizen/data/citizen.json` muestra solo `4.8986%` de celdas con alguna senal en `combined` y `99.3806%` `unknown` | **No liderar aun** |

## Por que el obstruction tracker va segundo

El obstruction tracker debe ser el wedge de apoyo porque aporta dos cosas que el vote explainer necesita:

- **credibilidad metodologica**: explica por que faltan piezas, por que hay huecos y por que el proyecto no finge cobertura total;
- **diferenciacion publica**: convierte la obstruccion del acceso a datos en una historia de accountability institucional.

Pero no debe ser el mensaje principal de entrada porque, por si solo, responde peor a la primera pregunta del usuario general:

- no dice que paso en un caso concreto;
- dice por que el sistema aun no puede ver todo.

Eso lo vuelve un excelente "second click", no el mejor "first click".

## Por que said-vs-did debe esperar

No es un problema de ambicion; es un problema de honestidad de producto.

La evidencia publicada hoy sugiere:

- `citizen_votes.json` si tiene senal fuerte: `94.2005%` de celdas con alguna senal y `82.4324%` clear.
- pero `citizen.json` (`combined`) y `citizen_declared.json` solo muestran `4.8986%` con alguna senal y `99.3806%` `unknown`.
- ademas, `status.json` reporta `topic_evidence_declared_total = 0` frente a `topic_evidence_revealed_total = 24837`.

Conclusion:

- hoy podemos explicar bastante bien **lo que hicieron en votos**;
- todavia no podemos liderar honestamente con **lo que dijeron vs lo que hicieron**.

Said-vs-did debe seguir como promesa de roadmap y como criterio de diseno de la ontologia, no como la portada principal del proximo trimestre.

## Propuesta de producto para el proximo tramo

### Wedge principal

- **Vote explainer**

Job to be done:

- "Necesito entender rapidamente una votacion relevante y tener una fuente verificable para compartirla."

Capacidades minimas que debe incluir:

- titulo entendible del voto;
- explicacion de que se votaba;
- resultado y reparto por grupos;
- enlace a fuente oficial;
- contexto de iniciativa cuando exista;
- caveats de comparabilidad/cobertura/freshness;
- salida compartible por URL canonica.

### Wedge de apoyo

- **Source obstruction tracker**

Job to be done:

- "Necesito saber que partes del mapa de datos estan bloqueadas, degradadas o incompletas, y que impacto tiene eso."

Capacidades minimas que debe incluir:

- estado por fuente;
- evidencia reproducible del bloqueo;
- impacto en cobertura;
- ultima actualizacion;
- enlace al incidente o evidencia.

## Metricas de exito

Metrica principal del wedge para el siguiente tramo:

- **al menos un vote explainer canonico, compartible y auditable por URL, apoyado por datos oficiales y caveats visibles, para cada voto destacado que se publique en la superficie publica**

Indicador operativo inicial:

- cada vote explainer publicado debe mostrar `source_url` oficial y resultado por grupos;
- el usuario debe poder llegar desde la tarjeta resumen a evidencia primaria en `<= 2 clicks`;
- los caveats de freshness y cobertura deben estar visibles en la misma pagina, no escondidos en metodologia.

Metrica secundaria:

- **cada vote explainer debe enlazar o convivir con el obstruction tracker cuando falte una pieza critica**, para que la ausencia de datos no se lea como silencio metodologico.

## Implicaciones para prioridades siguientes

Si este documento se acepta, las tareas siguientes deben leerse asi:

- `TODO 8`: formaliza el contrato de verdad necesario para que el vote explainer no sobre-prometa;
- `TODO 9`: define la spec de la pagina que realmente debe circular;
- `TODO 10`: implementa el wedge principal;
- `TODO 11`: implementa el wedge de apoyo que explica blockers y huecos.

## Lo que no debemos hacer en portada

- No abrir la home con un ranking general.
- No abrir la home con "said-vs-did" mientras la capa `declared` siga vacia o casi vacia.
- No convertir el obstruction tracker en la promesa unica del producto.
- No esconder `unknown` para que la interfaz parezca mas completa de lo que es.
