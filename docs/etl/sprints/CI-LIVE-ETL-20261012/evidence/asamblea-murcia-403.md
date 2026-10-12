# Asamblea Regional de Murcia — HTTP 403 (2026-10-12T08:47:27Z)

$ python3 scripts/ingestar_politicos_es.py ingest --db <tmp>/probe.db --source asamblea_murcia_diputados --snapshot-date 2026-10-12 --timeout 60 --strict-network
urllib.error.HTTPError: HTTP Error 403: Forbidden

$ curl -sk -D - -o /dev/null -A "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0 Safari/537.36" https://www.asambleamurcia.es/diputados
HTTP/2 403 
server: volt-adc
x-volterra-location: ny8-nyc
date: Mon, 12 Oct 2026 08:47:27 GMT

GitHub Actions run 38222268315 (2026-10-12, ubuntu-latest):
asamblea_murcia_diputados: ERROR RuntimeError: Implicit sample fallback is disabled by the real-data-only policy for asamblea_murcia_diputados. (Batch log prints only the outer error; the same-day local strict-network run above shows the underlying HTTP 403.)
