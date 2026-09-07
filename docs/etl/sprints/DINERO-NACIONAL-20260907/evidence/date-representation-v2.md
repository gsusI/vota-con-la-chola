# Fechas y API candidata — 2026-09-08

Ahora: 47.397 resultados siguen publicados en Hetzner. La candidata local de
128.837 resultados supera la comprobación funcional de API y exportación; no se
ha promocionado ni se afirma cobertura nacional completa.

- Release fuente: `82e44fce99c656795d622ac60fd3a76fe2f236e1b2e1186de529c08082373dc3`.
- Versión derivada: `71eaf94d5622dfca46fd0c30094f3ea5f7948d23448ecbe600cce7ca163ad848`.
- SQLite: 392.028.160 bytes; 128.837 resultados; 8.908.050.904.021 céntimos.
- 15 fechas corregidas mediante las reglas existentes; cuatro fechas no resueltas conservan literal y se representan como null.
- GALASA: 11 resultados, 572.335.676 céntimos; enero de 2025 conserva un resultado de 754.648 céntimos.
- Primera fecha válida sintácticamente: literal `1925-04-02`, expediente `14013/2025`, registro oficial `17457633`. No se cambia a 2025 sin corroboración ni se interpreta como prueba de cobertura desde 1925.

Destino: todos los registros accesibles, fechas inciertas explícitas y mismo
conjunto en filtros, paginación y CSV. `date_scope=all` incluye el rango fechado
y los no resueltos; `dated` restringe al rango; `unresolved` selecciona solo
los no resueltos, sin restricción del calendario. Órgano, proveedor y texto
se mantienen en todos los modos. `undated_count` informa el número seleccionado.

Verificado: clasificación idempotente, preservación del literal, fechas
bisiestas y orden; API sobre la base pública de 47.397 y la candidata de
128.837; recorrido completo sin claves duplicadas y suma exacta; partición
fechados/no resueltos con conservación de cantidades; filtro por órgano y CSV
de los cuatro registros dudosos; invalidación de parámetros incorrectos.
Servidor local candidato: tres consultas iniciales simultáneas responden 200;
ráfaga de veinte devuelve nueve 200 y once 503 con JSON válido, readiness intacto.
No es un ensayo de capacidad o latencia de producción.

Comandos reproducibles:

```sh
node tests/test_spending_date_quality.mjs
node scripts/build_spending_backend.mjs OUTPUT --plan-only --public-root=SEALED_RELEASE_ROOT
node tests/test_spending_backend.mjs OUTPUT/verify.db --national-candidate
node scripts/build_hetzner_spending_bundle.mjs OUTPUT/verify.db NEW_BUNDLE
node tests/test_hetzner_spending_server.mjs NEW_BUNDLE
```

Siguiente: integrar selección y explicación de fechas en la interfaz; publicar
las capturas inmutables y preparar el frontend con esa misma release; repetir
los controles de privacidad y paridad, desplegar candidato en slot inactivo y
promocionar con comprobación pública. Sin esa integración, no promover esta API.

## Corrección del paquete durante el gate de publicación

El gate de reproducción detectó que la candidata anterior excedía el límite
de extracción de 2 GB y conservaba una descripción limitada al código 8. Se
corrigieron los archivos fuente de documentación y reproducción, manteniendo
límites explícitos de 600 MB descargados, 4 GB extraídos y 150.000 miembros.
Medición de la candidata previa: 3.079.747.128 bytes extraídos y 86.947 archivos.
Se regeneró el paquete sin alterar filas ni XML: nueva release
`ab964ef550781b61e62bef96fa000e251a9ae133d4e1894d6f6bbda1ad733147`.
La versión de API ahora incorpora también la identidad del paquete, evitando
que dos paquetes distintos compartan versión de caché. Nueva versión derivada:
`ee3e6c8b2e02997ebfaa389f2f6b621209cf54cc7cbecc130deb30f78bf3281c`.
La interfaz fija esa versión en cada consulta y rechaza cruces entre API y
capturas. Publicación remota todavía pendiente de los gates finales.
