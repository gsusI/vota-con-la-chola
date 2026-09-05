# Seis primeras aportaciones al corte PLACSP

Demo: https://votaconlachola.org/spending/. Reproducción: [guía](../examples/placsp-launch/README.md). Estado: tareas abiertas, sin atribuir revisiones ni responsables personales inexistentes. Responsable de integración de las seis: rol mantenedor del repositorio; ejecución disponible para quien se asigne en un PR. Validación comunitaria aún pendiente.

Tres rutas: mejorar una consulta, verificar/corregir evidencia o proponer una fuente oficial con el [plantilla existente de fuente](../../.github/ISSUE_TEMPLATE/data_source_request.yml). En este lanzamiento se priorizan las seis tareas siguientes. No requieren credenciales privadas ni lanzar ETL.

| Tarea | Archivo | Entrada | Salida esperada | Validación | Responsable |
| --- | --- | --- | --- | --- | --- |
| 1. Probar inicio desde cero | `docs/examples/placsp-launch/README.md` | ZIP de la demo y Python 3.10+ | PR con comando usado, versión Python, tiempo y aclaración de cualquier paso confuso | Las tres consultas verifican; no publicar paths locales o sesiones | Contribuidor que se asigne; integra mantenedor |
| 2. Revisar teclado y móvil | `ui/gh-pages-next/app/spending/launch-explorer.js` | Demo pública, móvil o teclado | PR con defecto concreto o informe de recorrido sin incidencias | Elegir filtro, copiar enlace, recargar y abrir fuente; mismo recuento e importe | Contribuidor que se asigne; integra mantenedor |
| 3. Añadir ejemplo de periodo | `docs/examples/placsp-launch/README.md` | Comando con `--start` y `--end` | Ejemplo breve con resultado exacto comprobado | Reproducción anónima y suma en céntimos; especificar corte parcial | Contribuidor que se asigne; integra mantenedor |
| 4. Proponer consulta por lote | `docs/examples/placsp-launch/records.sql` | CSV y consulta de detalle | Nueva consulta propuesta en PR, conservando lotes ausentes explícitos | No sumar versiones ni tratar lotes ausentes como un lote real; comparar con detalle | Contribuidor que se asigne; integra mantenedor |
| 5. Revisar una adjudicación | `docs/etl/sprints/PUBLIC-LAUNCH-20260905/evidence/community-review.md` | Una fila, XML capturado y expediente oficial | Registrar campo, cita XML, hash y resultado de revisión | Distinguir fuente capturada de versión actual; sin acusaciones ni datos privados | Revisor que se asigne; integra mantenedor |
| 6. Mejorar diccionario y derechos | `docs/examples/placsp-launch/README.md` | Diccionario y política de datos por fuente | PR corrigiendo una ambigüedad con referencia oficial | Mantener adjudicado/pagado, fechas y ausencia de cobertura completa; no relicenciar documentos como MIT | Contribuidor que se asigne; integra mantenedor |

Las tareas 1 y 2 requieren conocimientos generales de uso de ordenador, no de contratación pública. Antes de contribuir: [CONTRIBUTING](../../CONTRIBUTING.md). Proponer cambios mediante PR; el envío de convocatorias a terceros requiere autorización específica del mantenedor.

## Crédito

Fuente del dataset: Plataforma de Contratación del Sector Público. Preparación del corte, consultas iniciales y demo: proyecto Vota Con La Chola. Revisión independiente: pendiente. Cada aportación aceptada añadirá enlace al PR y el nombre o alias que su autor quiera hacer público, distinguiendo datos, consulta, diseño, documentación y revisión. No hay aportaciones externas aceptadas registradas para esta alfa.
