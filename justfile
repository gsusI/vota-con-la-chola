db_path := env_var_or_default("DB_PATH", "etl/data/staging/politicos-es.db")
snapshot_date := env_var_or_default("SNAPSHOT_DATE", "2026-02-12")
tracker_path := env_var_or_default("TRACKER_PATH", "docs/etl/e2e-scrape-load-tracker.md")
municipal_timeout := env_var_or_default("MUNICIPAL_TIMEOUT", "240")
galicia_manual_dir := env_var_or_default("GALICIA_MANUAL_DIR", "etl/data/raw/manual/galicia_deputado_profiles_20260212T141929Z/pages")
navarra_manual_dir := env_var_or_default("NAVARRA_MANUAL_DIR", "etl/data/raw/manual/navarra_persona_profiles_20260212T144911Z/pages")
infoelectoral_timeout := env_var_or_default("INFOELECTORAL_TIMEOUT", "30")

default:
  @just --list

etl-cli cmd:
  docker compose run --rm --build etl "python3 scripts/ingestar_politicos_es.py {{cmd}}"

py cmd:
  docker compose run --rm --build etl "python3 {{cmd}}"

parl-cli cmd:
  docker compose run --rm --build etl "python3 scripts/ingestar_parlamentario_es.py {{cmd}}"

etl-build:
  docker compose build etl

etl-init:
  docker compose run --rm --build etl "python3 scripts/ingestar_politicos_es.py init-db --db {{db_path}}"

etl-samples:
  docker compose run --rm --build etl "python3 scripts/ingestar_politicos_es.py ingest --db {{db_path}} --source congreso_diputados --from-file etl/data/raw/samples/congreso_diputados_sample.json --snapshot-date {{snapshot_date}}"
  docker compose run --rm --build etl "python3 scripts/ingestar_politicos_es.py ingest --db {{db_path}} --source cortes_aragon_diputados --from-file etl/data/raw/samples/cortes_aragon_diputados_sample.json --snapshot-date {{snapshot_date}}"
  docker compose run --rm --build etl "python3 scripts/ingestar_politicos_es.py ingest --db {{db_path}} --source senado_senadores --from-file etl/data/raw/samples/senado_senadores_sample.csv --snapshot-date {{snapshot_date}}"
  docker compose run --rm --build etl "python3 scripts/ingestar_politicos_es.py ingest --db {{db_path}} --source europarl_meps --from-file etl/data/raw/samples/europarl_meps_sample.xml --snapshot-date {{snapshot_date}}"
  docker compose run --rm --build etl "python3 scripts/ingestar_politicos_es.py ingest --db {{db_path}} --source municipal_concejales --from-file etl/data/raw/samples/municipal_concejales_sample.csv --snapshot-date {{snapshot_date}}"
  docker compose run --rm --build etl "python3 scripts/ingestar_politicos_es.py ingest --db {{db_path}} --source asamblea_madrid_ocupaciones --from-file etl/data/raw/samples/asamblea_madrid_ocupaciones_sample.csv --snapshot-date {{snapshot_date}}"
  docker compose run --rm --build etl "python3 scripts/ingestar_politicos_es.py ingest --db {{db_path}} --source asamblea_ceuta_diputados --from-file etl/data/raw/samples/asamblea_ceuta_diputados_sample.json --snapshot-date {{snapshot_date}}"
  docker compose run --rm --build etl "python3 scripts/ingestar_politicos_es.py ingest --db {{db_path}} --source asamblea_extremadura_diputados --from-file etl/data/raw/samples/asamblea_extremadura_diputados_sample.json --snapshot-date {{snapshot_date}}"
  docker compose run --rm --build etl "python3 scripts/ingestar_politicos_es.py ingest --db {{db_path}} --source asamblea_murcia_diputados --from-file etl/data/raw/samples/asamblea_murcia_diputados_sample.json --snapshot-date {{snapshot_date}}"
  docker compose run --rm --build etl "python3 scripts/ingestar_politicos_es.py ingest --db {{db_path}} --source jgpa_diputados --from-file etl/data/raw/samples/jgpa_diputados_sample.json --snapshot-date {{snapshot_date}}"
  docker compose run --rm --build etl "python3 scripts/ingestar_politicos_es.py ingest --db {{db_path}} --source parlamento_canarias_diputados --from-file etl/data/raw/samples/parlamento_canarias_diputados_sample.json --snapshot-date {{snapshot_date}}"
  docker compose run --rm --build etl "python3 scripts/ingestar_politicos_es.py ingest --db {{db_path}} --source parlamento_cantabria_diputados --from-file etl/data/raw/samples/parlamento_cantabria_diputados_sample.json --snapshot-date {{snapshot_date}}"
  docker compose run --rm --build etl "python3 scripts/ingestar_politicos_es.py ingest --db {{db_path}} --source parlament_balears_diputats --from-file etl/data/raw/samples/parlament_balears_diputats_sample.json --snapshot-date {{snapshot_date}}"
  docker compose run --rm --build etl "python3 scripts/ingestar_politicos_es.py ingest --db {{db_path}} --source parlamento_larioja_diputados --from-file etl/data/raw/samples/parlamento_larioja_diputados_sample.json --snapshot-date {{snapshot_date}}"
  docker compose run --rm --build etl "python3 scripts/ingestar_politicos_es.py ingest --db {{db_path}} --source parlament_catalunya_diputats --from-file etl/data/raw/samples/parlament_catalunya_diputats_sample.json --snapshot-date {{snapshot_date}}"
  docker compose run --rm --build etl "python3 scripts/ingestar_politicos_es.py ingest --db {{db_path}} --source corts_valencianes_diputats --from-file etl/data/raw/samples/corts_valencianes_diputats_sample.json --snapshot-date {{snapshot_date}}"
  docker compose run --rm --build etl "python3 scripts/ingestar_politicos_es.py ingest --db {{db_path}} --source cortes_clm_diputados --from-file etl/data/raw/samples/cortes_clm_diputados_sample.json --snapshot-date {{snapshot_date}}"
  docker compose run --rm --build etl "python3 scripts/ingestar_politicos_es.py ingest --db {{db_path}} --source cortes_cyl_procuradores --from-file etl/data/raw/samples/cortes_cyl_procuradores_sample.json --snapshot-date {{snapshot_date}}"
  docker compose run --rm --build etl "python3 scripts/ingestar_politicos_es.py ingest --db {{db_path}} --source parlamento_andalucia_diputados --from-file etl/data/raw/samples/parlamento_andalucia_diputados_sample.json --snapshot-date {{snapshot_date}}"
  docker compose run --rm --build etl "python3 scripts/ingestar_politicos_es.py ingest --db {{db_path}} --source parlamento_vasco_parlamentarios --from-file etl/data/raw/samples/parlamento_vasco_parlamentarios_sample.json --snapshot-date {{snapshot_date}}"

parl-init:
  docker compose run --rm --build etl "python3 scripts/ingestar_parlamentario_es.py init-db --db {{db_path}}"

parl-samples:
  docker compose run --rm --build etl "python3 scripts/ingestar_parlamentario_es.py ingest --db {{db_path}} --source congreso_votaciones --from-file etl/data/raw/samples/congreso_votaciones_sample.json --snapshot-date {{snapshot_date}} --strict-network"
  docker compose run --rm --build etl "python3 scripts/ingestar_parlamentario_es.py ingest --db {{db_path}} --source congreso_iniciativas --from-file etl/data/raw/samples/congreso_iniciativas_sample.json --snapshot-date {{snapshot_date}} --strict-network"
  docker compose run --rm --build etl "python3 scripts/ingestar_parlamentario_es.py ingest --db {{db_path}} --source senado_votaciones --from-file etl/data/raw/samples/senado_votaciones_sample.xml --snapshot-date {{snapshot_date}} --strict-network"

etl-stats:
  docker compose run --rm --build etl "python3 scripts/ingestar_politicos_es.py stats --db {{db_path}}"

etl-backfill-normalized:
  docker compose run --rm --build etl "python3 scripts/ingestar_politicos_es.py backfill-normalized --db {{db_path}}"

etl-test:
  docker compose run --rm --build etl "python3 -m unittest discover -s tests -v"

etl-live:
  docker compose run --rm --build etl "python3 scripts/ingestar_politicos_es.py ingest --db {{db_path}} --source all --snapshot-date {{snapshot_date}} --timeout {{municipal_timeout}}"

etl-elecciones:
  docker compose run --rm --build etl "python3 scripts/generar_proximas_elecciones_espana.py --today {{snapshot_date}}"

etl-publish-representantes:
  docker compose run --rm --build etl "python3 scripts/publicar_representantes_es.py --db {{db_path}} --snapshot-date {{snapshot_date}}"

parl-extract-congreso-votaciones:
  docker compose run --rm --build etl "python3 scripts/ingestar_parlamentario_es.py ingest --db {{db_path}} --source congreso_votaciones --snapshot-date {{snapshot_date}} --strict-network"

parl-extract-congreso-iniciativas:
  docker compose run --rm --build etl "python3 scripts/ingestar_parlamentario_es.py ingest --db {{db_path}} --source congreso_iniciativas --snapshot-date {{snapshot_date}} --strict-network"

parl-extract-senado-votaciones:
  docker compose run --rm --build etl "python3 scripts/ingestar_parlamentario_es.py ingest --db {{db_path}} --source senado_votaciones --snapshot-date {{snapshot_date}} --strict-network"

etl-extract-congreso:
  docker compose run --rm --build etl "python3 scripts/ingestar_politicos_es.py ingest --db {{db_path}} --source congreso_diputados --snapshot-date {{snapshot_date}} --strict-network"

etl-extract-cortes-aragon:
  docker compose run --rm --build etl "python3 scripts/ingestar_politicos_es.py ingest --db {{db_path}} --source cortes_aragon_diputados --snapshot-date {{snapshot_date}} --strict-network"

etl-extract-senado:
  docker compose run --rm --build etl "python3 scripts/ingestar_politicos_es.py ingest --db {{db_path}} --source senado_senadores --snapshot-date {{snapshot_date}} --strict-network"

etl-extract-europarl:
  docker compose run --rm --build etl "python3 scripts/ingestar_politicos_es.py ingest --db {{db_path}} --source europarl_meps --snapshot-date {{snapshot_date}} --strict-network"

etl-extract-municipal:
  docker compose run --rm --build etl "python3 scripts/ingestar_politicos_es.py ingest --db {{db_path}} --source municipal_concejales --snapshot-date {{snapshot_date}} --strict-network --timeout {{municipal_timeout}}"

etl-extract-asamblea-madrid:
  docker compose run --rm --build etl "python3 scripts/ingestar_politicos_es.py ingest --db {{db_path}} --source asamblea_madrid_ocupaciones --snapshot-date {{snapshot_date}} --strict-network"

etl-extract-asamblea-ceuta:
  docker compose run --rm --build etl "python3 scripts/ingestar_politicos_es.py ingest --db {{db_path}} --source asamblea_ceuta_diputados --snapshot-date {{snapshot_date}} --strict-network"

etl-extract-asamblea-extremadura:
  docker compose run --rm --build etl "python3 scripts/ingestar_politicos_es.py ingest --db {{db_path}} --source asamblea_extremadura_diputados --snapshot-date {{snapshot_date}} --strict-network"

etl-extract-asamblea-murcia:
  docker compose run --rm --build etl "python3 scripts/ingestar_politicos_es.py ingest --db {{db_path}} --source asamblea_murcia_diputados --snapshot-date {{snapshot_date}} --strict-network"

etl-extract-jgpa:
  docker compose run --rm --build etl "python3 scripts/ingestar_politicos_es.py ingest --db {{db_path}} --source jgpa_diputados --snapshot-date {{snapshot_date}} --strict-network"

etl-extract-parlamento-canarias:
  docker compose run --rm --build etl "python3 scripts/ingestar_politicos_es.py ingest --db {{db_path}} --source parlamento_canarias_diputados --snapshot-date {{snapshot_date}} --strict-network"

etl-extract-parlamento-cantabria:
  docker compose run --rm --build etl "python3 scripts/ingestar_politicos_es.py ingest --db {{db_path}} --source parlamento_cantabria_diputados --snapshot-date {{snapshot_date}} --strict-network"

etl-extract-parlament-balears:
  docker compose run --rm --build etl "python3 scripts/ingestar_politicos_es.py ingest --db {{db_path}} --source parlament_balears_diputats --snapshot-date {{snapshot_date}} --strict-network"

etl-extract-parlamento-larioja:
  docker compose run --rm --build etl "python3 scripts/ingestar_politicos_es.py ingest --db {{db_path}} --source parlamento_larioja_diputados --snapshot-date {{snapshot_date}} --strict-network"

etl-extract-parlament-catalunya:
  docker compose run --rm --build etl "python3 scripts/ingestar_politicos_es.py ingest --db {{db_path}} --source parlament_catalunya_diputats --snapshot-date {{snapshot_date}} --strict-network"

etl-extract-corts-valencianes:
  docker compose run --rm --build etl "python3 scripts/ingestar_politicos_es.py ingest --db {{db_path}} --source corts_valencianes_diputats --snapshot-date {{snapshot_date}} --strict-network"

etl-extract-cortes-clm:
  docker compose run --rm --build etl "python3 scripts/ingestar_politicos_es.py ingest --db {{db_path}} --source cortes_clm_diputados --snapshot-date {{snapshot_date}} --strict-network"

etl-extract-cortes-cyl:
  docker compose run --rm --build etl "python3 scripts/ingestar_politicos_es.py ingest --db {{db_path}} --source cortes_cyl_procuradores --snapshot-date {{snapshot_date}} --strict-network"

etl-extract-parlamento-andalucia:
  docker compose run --rm --build etl "python3 scripts/ingestar_politicos_es.py ingest --db {{db_path}} --source parlamento_andalucia_diputados --snapshot-date {{snapshot_date}} --strict-network"

etl-extract-parlamento-vasco:
  docker compose run --rm --build etl "python3 scripts/ingestar_politicos_es.py ingest --db {{db_path}} --source parlamento_vasco_parlamentarios --snapshot-date {{snapshot_date}} --strict-network"

etl-extract-parlamento-galicia-manual:
  test -d {{galicia_manual_dir}} || (echo "GALICIA_MANUAL_DIR no existe: {{galicia_manual_dir}}. Captura perfiles (Playwright) y exporta la ruta." && exit 2)
  docker compose run --rm --build etl "python3 scripts/ingestar_politicos_es.py ingest --db {{db_path}} --source parlamento_galicia_deputados --from-file {{galicia_manual_dir}} --snapshot-date {{snapshot_date}}"

etl-extract-parlamento-navarra-manual:
  test -d {{navarra_manual_dir}} || (echo "NAVARRA_MANUAL_DIR no existe: {{navarra_manual_dir}}. Captura perfiles (Playwright) y exporta la ruta." && exit 2)
  docker compose run --rm --build etl "python3 scripts/ingestar_politicos_es.py ingest --db {{db_path}} --source parlamento_navarra_parlamentarios_forales --from-file {{navarra_manual_dir}} --snapshot-date {{snapshot_date}}"

etl-extract-infoelectoral-descargas:
  docker compose run --rm --build etl "python3 scripts/ingestar_infoelectoral_es.py ingest --db {{db_path}} --source infoelectoral_descargas --snapshot-date {{snapshot_date}} --timeout {{infoelectoral_timeout}} --strict-network"

etl-extract-all:
  docker compose run --rm --build etl "python3 scripts/ingestar_politicos_es.py ingest --db {{db_path}} --source congreso_diputados --snapshot-date {{snapshot_date}} --strict-network"
  docker compose run --rm --build etl "python3 scripts/ingestar_politicos_es.py ingest --db {{db_path}} --source cortes_aragon_diputados --snapshot-date {{snapshot_date}} --strict-network"
  docker compose run --rm --build etl "python3 scripts/ingestar_politicos_es.py ingest --db {{db_path}} --source senado_senadores --snapshot-date {{snapshot_date}} --strict-network"
  docker compose run --rm --build etl "python3 scripts/ingestar_politicos_es.py ingest --db {{db_path}} --source europarl_meps --snapshot-date {{snapshot_date}} --strict-network"
  docker compose run --rm --build etl "python3 scripts/ingestar_politicos_es.py ingest --db {{db_path}} --source municipal_concejales --snapshot-date {{snapshot_date}} --strict-network --timeout {{municipal_timeout}}"
  docker compose run --rm --build etl "python3 scripts/ingestar_politicos_es.py ingest --db {{db_path}} --source asamblea_madrid_ocupaciones --snapshot-date {{snapshot_date}} --strict-network"
  docker compose run --rm --build etl "python3 scripts/ingestar_politicos_es.py ingest --db {{db_path}} --source asamblea_ceuta_diputados --snapshot-date {{snapshot_date}} --strict-network"
  docker compose run --rm --build etl "python3 scripts/ingestar_politicos_es.py ingest --db {{db_path}} --source asamblea_extremadura_diputados --snapshot-date {{snapshot_date}} --strict-network"
  docker compose run --rm --build etl "python3 scripts/ingestar_politicos_es.py ingest --db {{db_path}} --source asamblea_murcia_diputados --snapshot-date {{snapshot_date}} --strict-network"
  docker compose run --rm --build etl "python3 scripts/ingestar_politicos_es.py ingest --db {{db_path}} --source jgpa_diputados --snapshot-date {{snapshot_date}} --strict-network"
  docker compose run --rm --build etl "python3 scripts/ingestar_politicos_es.py ingest --db {{db_path}} --source parlamento_canarias_diputados --snapshot-date {{snapshot_date}} --strict-network"
  docker compose run --rm --build etl "python3 scripts/ingestar_politicos_es.py ingest --db {{db_path}} --source parlamento_cantabria_diputados --snapshot-date {{snapshot_date}} --strict-network"
  docker compose run --rm --build etl "python3 scripts/ingestar_politicos_es.py ingest --db {{db_path}} --source parlament_balears_diputats --snapshot-date {{snapshot_date}} --strict-network"
  docker compose run --rm --build etl "python3 scripts/ingestar_politicos_es.py ingest --db {{db_path}} --source parlamento_larioja_diputados --snapshot-date {{snapshot_date}} --strict-network"
  docker compose run --rm --build etl "python3 scripts/ingestar_politicos_es.py ingest --db {{db_path}} --source parlament_catalunya_diputats --snapshot-date {{snapshot_date}} --strict-network"
  docker compose run --rm --build etl "python3 scripts/ingestar_politicos_es.py ingest --db {{db_path}} --source corts_valencianes_diputats --snapshot-date {{snapshot_date}} --strict-network"
  docker compose run --rm --build etl "python3 scripts/ingestar_politicos_es.py ingest --db {{db_path}} --source cortes_clm_diputados --snapshot-date {{snapshot_date}} --strict-network"
  docker compose run --rm --build etl "python3 scripts/ingestar_politicos_es.py ingest --db {{db_path}} --source cortes_cyl_procuradores --snapshot-date {{snapshot_date}} --strict-network"
  docker compose run --rm --build etl "python3 scripts/ingestar_politicos_es.py ingest --db {{db_path}} --source parlamento_andalucia_diputados --snapshot-date {{snapshot_date}} --strict-network"
  docker compose run --rm --build etl "python3 scripts/ingestar_politicos_es.py ingest --db {{db_path}} --source parlamento_vasco_parlamentarios --snapshot-date {{snapshot_date}} --strict-network"

etl-e2e:
  docker compose run --rm --build etl "python3 scripts/ingestar_politicos_es.py init-db --db {{db_path}}"
  docker compose run --rm --build etl "python3 scripts/ingestar_politicos_es.py ingest --db {{db_path}} --source congreso_diputados --snapshot-date {{snapshot_date}} --strict-network"
  docker compose run --rm --build etl "python3 scripts/ingestar_politicos_es.py ingest --db {{db_path}} --source cortes_aragon_diputados --snapshot-date {{snapshot_date}} --strict-network"
  docker compose run --rm --build etl "python3 scripts/ingestar_politicos_es.py ingest --db {{db_path}} --source senado_senadores --snapshot-date {{snapshot_date}} --strict-network"
  docker compose run --rm --build etl "python3 scripts/ingestar_politicos_es.py ingest --db {{db_path}} --source europarl_meps --snapshot-date {{snapshot_date}} --strict-network"
  docker compose run --rm --build etl "python3 scripts/ingestar_politicos_es.py ingest --db {{db_path}} --source municipal_concejales --snapshot-date {{snapshot_date}} --strict-network --timeout {{municipal_timeout}}"
  docker compose run --rm --build etl "python3 scripts/ingestar_politicos_es.py ingest --db {{db_path}} --source asamblea_madrid_ocupaciones --snapshot-date {{snapshot_date}} --strict-network"
  docker compose run --rm --build etl "python3 scripts/ingestar_politicos_es.py ingest --db {{db_path}} --source asamblea_ceuta_diputados --snapshot-date {{snapshot_date}} --strict-network"
  docker compose run --rm --build etl "python3 scripts/ingestar_politicos_es.py ingest --db {{db_path}} --source asamblea_extremadura_diputados --snapshot-date {{snapshot_date}} --strict-network"
  docker compose run --rm --build etl "python3 scripts/ingestar_politicos_es.py ingest --db {{db_path}} --source asamblea_murcia_diputados --snapshot-date {{snapshot_date}} --strict-network"
  docker compose run --rm --build etl "python3 scripts/ingestar_politicos_es.py ingest --db {{db_path}} --source jgpa_diputados --snapshot-date {{snapshot_date}} --strict-network"
  docker compose run --rm --build etl "python3 scripts/ingestar_politicos_es.py ingest --db {{db_path}} --source parlamento_canarias_diputados --snapshot-date {{snapshot_date}} --strict-network"
  docker compose run --rm --build etl "python3 scripts/ingestar_politicos_es.py ingest --db {{db_path}} --source parlamento_cantabria_diputados --snapshot-date {{snapshot_date}} --strict-network"
  docker compose run --rm --build etl "python3 scripts/ingestar_politicos_es.py ingest --db {{db_path}} --source parlament_balears_diputats --snapshot-date {{snapshot_date}} --strict-network"
  docker compose run --rm --build etl "python3 scripts/ingestar_politicos_es.py ingest --db {{db_path}} --source parlamento_larioja_diputados --snapshot-date {{snapshot_date}} --strict-network"
  docker compose run --rm --build etl "python3 scripts/ingestar_politicos_es.py ingest --db {{db_path}} --source parlament_catalunya_diputats --snapshot-date {{snapshot_date}} --strict-network"
  docker compose run --rm --build etl "python3 scripts/ingestar_politicos_es.py ingest --db {{db_path}} --source corts_valencianes_diputats --snapshot-date {{snapshot_date}} --strict-network"
  docker compose run --rm --build etl "python3 scripts/ingestar_politicos_es.py ingest --db {{db_path}} --source cortes_clm_diputados --snapshot-date {{snapshot_date}} --strict-network"
  docker compose run --rm --build etl "python3 scripts/ingestar_politicos_es.py ingest --db {{db_path}} --source cortes_cyl_procuradores --snapshot-date {{snapshot_date}} --strict-network"
  docker compose run --rm --build etl "python3 scripts/ingestar_politicos_es.py ingest --db {{db_path}} --source parlamento_andalucia_diputados --snapshot-date {{snapshot_date}} --strict-network"
  docker compose run --rm --build etl "python3 scripts/ingestar_politicos_es.py ingest --db {{db_path}} --source parlamento_vasco_parlamentarios --snapshot-date {{snapshot_date}} --strict-network"
  docker compose run --rm --build etl "python3 scripts/ingestar_politicos_es.py stats --db {{db_path}}"

# UI: explorador de grafo (web)
graph-ui:
  DB_PATH={{db_path}} docker compose up --build graph-ui

graph-ui-bg:
  DB_PATH={{db_path}} docker compose up --build -d graph-ui

graph-ui-stop:
  docker compose stop graph-ui
  docker compose rm -f graph-ui

# Tracker: estado SQL vs checklist
etl-tracker-status:
  docker compose run --rm --build etl "python3 scripts/e2e_tracker_status.py --db {{db_path}} --tracker {{tracker_path}}"

etl-tracker-gate:
  docker compose run --rm --build etl "python3 scripts/e2e_tracker_status.py --db {{db_path}} --tracker {{tracker_path}} --fail-on-done-zero-real"
