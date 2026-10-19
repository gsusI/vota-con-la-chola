# oecd.org: Cloudflare challenge on scripted access (2026-10-19)

Used by: `/visualizaciones/educacion/` (`scripts/ingest_education_es.py`), PISA tables and country notes.

Command (repo User-Agent, no cookies):

```bash
curl -s -o /dev/null -D - -A "Mozilla/5.0 (compatible; vota-con-la-chola-etl/1.0; +https://votaconlachola.org)" \
  "https://www.oecd.org/en/publications/pisa-2022-results-volume-i-and-ii-country-notes_ed6fbcc5-en/spain_f1a3afc1-en.html"
```

Result at `2026-10-19T09:00:41Z` and `09:00:42Z` (same for the PISA 2022 Volume I page):

```text
HTTP/2 403
content-type: text/html; charset=UTF-8
cf-mitigated: challenge
server: cloudflare
```

The PDF country note link (`/publication/pisa-2022-results/webbooks/dynamic/pisa-country-notes/f1a3afc1/pdf/spain.pdf`)
returns an HTML page instead of a PDF. `sdmx.oecd.org` gives the same answer at `2026-10-19T09:01:01Z`
(`GET https://sdmx.oecd.org/public/rest/dataflow/OECD.EDU.IMEP/DSD_EAG_UOE_FIN@DF_UOE_INDIC_FIN_PERSTUD/latest` →
`HTTP/2 403`, `cf-mitigated: challenge`).

Workaround used (no challenge bypass):
- OECD Education at a Glance finance: DBnomics mirror `api.db.nomics.world/v22/series/OECD/DSD_EAG_UOE_FIN@DF_UOE_INDIC_FIN_PERSTUD`.
- PISA 2022 country note for Spain: official copy hosted by the Ministerio de Educación (INEE), sha256 `5077fa4b…dd85a`.

Data lost: OECD average PISA scores 2000-2015, PISA grade repetition before 2022 and 2022 reading/science scores of
Germany, France, Italy and Portugal (only in figures of the INEE report).
