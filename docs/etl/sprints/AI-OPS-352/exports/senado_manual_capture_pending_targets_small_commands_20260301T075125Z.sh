#!/usr/bin/env bash
set -euo pipefail

python3 scripts/manual_capture_playwright.py --url https://www.senado.es/ --label senado_cookie_refresh_ai_ops_299_01_seed --out-dir etl/data/raw/manual --wait-seconds 15 --channel ""
python3 scripts/manual_capture_playwright.py --url 'https://www.senado.es/web/actividadparlamentaria/iniciativas/enmiendas/index.html?id1=610&id2=000005&legis=10' --label senado_cookie_refresh_ai_ops_299_02_leg10_tipo610 --out-dir etl/data/raw/manual --wait-seconds 15 --channel ""
