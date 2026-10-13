#!/usr/bin/env python3
"""Upload the site's static assets as a new Worker version and route all traffic to it."""
import argparse, re, shutil, subprocess, sys
p=argparse.ArgumentParser();p.add_argument('--site',required=True);a=p.parse_args()
worker_dir='infra/cloudflare/votaconlachola-worker'  # run wrangler here so the repo-root .env token is not loaded
wrangler=['wrangler'] if shutil.which('wrangler') else ['npx','--yes','wrangler@4.149.0']
subprocess.run([sys.executable,'scripts/prepare_site_static_assets.py','--site',a.site],check=True)
subprocess.run([sys.executable,'scripts/check_public_privacy_leaks.py','--path','infra/cloudflare/votaconlachola-worker/public'],check=True)
subprocess.run(['node','tests/test_spending_static_router.mjs'],check=True)
result=subprocess.run(wrangler+['versions','upload','--keep-vars','--message','Publish site static assets'],capture_output=True,text=True,cwd=worker_dir)
print(result.stdout);print(result.stderr,file=sys.stderr)
result.check_returncode()
version=re.search(r'Worker Version ID:\s*([0-9a-f-]{36})',result.stdout)
if not version:raise SystemExit('Upload completed but version ID missing; inspect upload before activating traffic')
subprocess.run(wrangler+['versions','deploy',version.group(1)+'@100','--yes','--message','Serve site static assets and R2 origin'],check=True,cwd=worker_dir)
