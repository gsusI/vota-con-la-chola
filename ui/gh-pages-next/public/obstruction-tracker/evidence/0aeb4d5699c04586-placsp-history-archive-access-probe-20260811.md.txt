# PLACSP history archive access probe — 2026-08-11

Observed window: `2026-08-11T17:16:00Z`–`2026-08-11T17:18:00Z`

Target:

`https://contrataciondelsectorpublico.gob.es/sindicacion/sindicacion_643/licitacionesPerfilesContratanteCompleto3_2024.zip`

Verified Python `HEAD` probe (three bounded attempts):

```bash
python3 - <<'PY'
import urllib.request
url = "https://contrataciondelsectorpublico.gob.es/sindicacion/sindicacion_643/licitacionesPerfilesContratanteCompleto3_2024.zip"
for index in range(3):
    try:
        response = urllib.request.urlopen(
            urllib.request.Request(url, method="HEAD"), timeout=30
        )
        print(index, response.status, response.headers.get("Content-Length"))
    except Exception as exc:
        print(index, type(exc).__name__, exc)
PY
```

Machine-verifiable result:

```text
0 ConnectionResetError [Errno 54] Connection reset by peer
1 ConnectionResetError [Errno 54] Connection reset by peer
2 ConnectionResetError [Errno 54] Connection reset by peer
```

A one-byte `Range` diagnostic with certificate verification disabled only to classify the upstream response did not return ZIP metadata or bytes:

```bash
curl -kfsS -D - -o /dev/null -r 0-0 'https://contrataciondelsectorpublico.gob.es/sindicacion/sindicacion_643/licitacionesPerfilesContratanteCompleto3_2024.zip'
```

Machine-verifiable result:

```text
HTTP/1.1 200 Error
Content-Type: text/html; charset=UTF-8
Connection: close
Transfer-Encoding: chunked
```

Interpretation: archive access is intermittent, not a permanent total outage. The same environment successfully downloaded six 2025 monthly archives earlier on `2026-08-11`; the official Hacienda catalog also remained reachable with verified TLS and exposed all expected history links. The history worker was therefore not started blindly. Its 22 archive items remain pending until a fresh access signal and a disk/origin budget exist.

No motive is inferred. No unverified payload was ingested.
