# Migración de API a Hetzner — 2026-09-07

Solicitud del mantenedor: nuevo servicio blue/green Ansible en el repositorio first_hetzner, sin comprometer otros servicios. Sustituye D1 para servir consultas; no cambia la ambición de cobertura ni autoriza ETL ilimitado en producción.

## Estado verificado

- Rol `ansible/roles/vclc_spending` y playbooks `apps/vclc-spending`, `apps/vclc-spending-promote` en first_hetzner.
- Identidad física del target comprobada por target_guard. Inventario de un solo host; wrapper canónico, syntax/check/apply ejecutados.
- API HTTPS directa: https://api.votaconlachola.org/v1/status. DNS A exclusivo en modo DNS-only; registro del sitio principal preservado.
- Slot blue activo. Readiness, TLS y versión comprobados desde el servidor y cliente externo. Total 47.397 y 4.865.774.429.683 céntimos: misma release pública, no nueva cobertura.
- SQLite de solo lectura; proceso no root, capabilities vacías, límite 0,5 CPU/512 MiB, sin swap adicional, 64 PIDs y logs acotados. Únicamente localhost 18085/18086.
- Antes: 30 GiB libres (80% ocupado), 10.331 MiB disponibles, carga 0,28/0,84/0,99. Presión de memoria cero; presión IO baja.
- Después: 35 GiB libres (76% ocupado); variación de disco ajena a este despliegue, no se ejecutó limpieza. API en reposo 31,27 MiB. Los 24 contenedores anteriores mantienen exactamente sus tiempos de arranque y cero reinicios/OOM. Sin unidades systemd fallidas.
- No reinicio de Traefik ni cambios en Postgres, Redis, SSH, firewall o despliegues ajenos.

## Estado intermedio antes del cierre

Publicar la URL nueva en el frontend y verificar navegador. Segundo slot y rollback comprobados: blue → green → blue, HTTPS válido en cada conmutación y 15/15 consultas de estado HTTP 200 durante la observación (182–282 ms). Ambos slots saludables; blue activo. La candidata de 128.837 resultados sigue siendo una operación separada de calidad/publicación; los cambios parciales de fecha desconocida aún no se usan en esta migración. No se afirma North Star alcanzada.

## Cierre de la migración

Frontend publicado desde checkout aislado: main `008e517767`, gh-pages `0fd0971d8a`, assets activos `740eda54-fa99-456c-b54e-faf7f3838c4f`. Los controles de datos reales, privacidad, siete pruebas de corpus, fechas, API, build Next y paridad de archivos pasan. Se preservaron exactamente 17.328 archivos ajenos al corte publicado.

El navegador detectó un defecto de concurrencia inicial: tres peticiones simultáneas podían producir 503 vacío. Se corrigió con cola máxima de ocho solicitudes, espera/ejecución acotadas y errores JSON. Regresión local: arranque 3/3 correcto; ráfaga de 20 produce nueve 200 y once 503 válidos, sin perder readiness. Código corregido `eb96367ed6`; bundle `efca9a409f04f6e841d82d4dcece596c309f22fd9fe3f4933bfc183081833ff6`.

La receta `just spending-api-deploy BUNDLE green` se ejecutó de extremo a extremo: syntax/check/apply, candidato y promoción HTTPS. Green queda activo; blue actualizado al mismo bundle como reserva, sin conmutar tráfico durante esa actualización. Ambos healthchecks pasan y conservan límites efectivos 0,5 CPU/512 MiB.

Verificación final en navegador público: carga inicial 47.397 resultados y 48.657.744.296,83 euros; selección GALASA y calendario 1999–2027 muestran ocho resultados y 5.505.965,94 euros. CSV paginado comprobado contra API externa con paridad de importe. La consulta Python al HTML del sitio recibió 403 de su capa de acceso; la navegación normal sí funciona. No se atribuye ese 403 al backend Hetzner ni se omite del registro.

Las consultas de la web pasan directamente a api.votaconlachola.org, sin Workers/D1 en ese camino. Cloudflare sigue alojando el frontend y gestionando DNS. No se borraron D1 ni el Worker anterior. La ampliación del corpus y el tratamiento de fechas dudosas siguen pendientes y separados de esta migración.

Revalidación 2026-09-07 22:14 UTC: HTTPS devuelve la misma versión y 47.397 resultados; green activo y ambos slots saludables, cero reinicios y OOM. Disco disponible 30 GiB (80% ocupado), RAM disponible 9.017 MiB, carga 2,52/1,16/0,79 y ninguna unidad systemd fallida. Presión de memoria cero; presión IO avg10 0,07%. Los límites efectivos siguen en 512 MiB y 0,5 CPU por slot, con raíz de solo lectura. Hay despliegues concurrentes de otros servicios: el espacio y la carga fluctúan; estas cifras sustituyen a las anteriores como última observación, no representan capacidad garantizada.

Comprobación final tras la corrección: green activo, blue y green saludables, sin OOM ni reinicios automáticos; 10.020 MiB de RAM disponible, 35 GiB libres (77% de disco), presión de memoria cero e IO prácticamente cero, sin unidades systemd fallidas. Se observan dos despliegues concurrentes de aplicaciones ajenas respecto al inventario inicial; este rol y sus comandos no los gestionaron. Los demás 22 contenedores conservan sus tiempos de arranque, incluido Traefik, PostgreSQL y Redis. La afirmación previa de 24 tiempos iguales correspondía al control intermedio, no se extiende falsamente al cierre.
