# Snapshot signing trust roots

Los ficheros `*.allowed_signers` son trust roots públicos revisables. Las claves
privadas nunca viven aquí ni en Git.

Verificación canónica:

```bash
just etl-scale-origin-hf-verify-attestation
```

No aceptar un `allowed_signers` descargado del mismo dataset que se intenta verificar.
La clave pública publicada dentro del snapshot sirve para descubrimiento y diagnóstico,
no para decidir confianza.
