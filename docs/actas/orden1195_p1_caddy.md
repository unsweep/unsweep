# Orden #1195 P1 (#1011 PASO F): exposición pública del relayer de Arbitrum 42161

Fecha: 2026-11-22, 07:32-07:37Z. Log: /opt/aire/workspace/logs/orden1195_p1_caddy.log

## PASO 0 (solo lectura)
- HECHO: Base https://unsweep.com/api/health devuelve HTTP 200, ok=true, chainId 8453, ofac_entries 123.
- HECHO: los hashes servidos coinciden con fccdd7b (sha256/16): index.html 3a74a1baecce00d8, assets/app.js f980e8433949eef3, assets/style.css 811d3eba7b1e8693. Las rutas reales son /assets/*; la primera comparación de /app.js era inválida porque comparaba dos sha vacíos.
- HECHO: unsweep-relayer-arb en estado running. Id 8c941c5aba82…, StartedAt 2026-11-22T07:10:12Z, puerto interno 8787, health /api/health, alias de red relayer-arb.
- HECHO: Base unsweep-relayer, Id c0bbe7ab70ab…, StartedAt 2026-11-22T05:34:43.224921307Z.
- HECHO: nonces OPS: Arbitrum 3/3 y Base 3/3 (latest/pending).

## PASO 1
- app.js siempre llama a '/api/' + path y no tiene ruta para Arbitrum, así que se usa una ruta aditiva handle /arb/api/* con uri strip_prefix /arb hacia unsweep-relayer-arb:8787. web/* no se ha tocado.
- Backup: logs/Caddyfile.pre_orden1195_p1.20261122T073415Z (sha d141533a76fe069f). Edición en el mismo inodo (bind mount). caddy validate OK; caddy reload OK, sin reiniciar contenedores.

## PASO 2 (curl externo, DNS real 40.75.139.128)
- (a) https://unsweep.com/arb/api/health devuelve HTTP 200, ok=true, chainId 42161.
- (b) https://unsweep.com/api/health devuelve HTTP 200 y chainId 8453; Id y StartedAt de unsweep-relayer sin cambios.
- (c) Hashes de los estáticos sin cambios (EQ con fccdd7b).
- (d) POST https://unsweep.com/arb/api/scan con la dirección pública 0xd8dA6BF26964aF9D7eEd9e03E53415D37aA96045 devuelve HTTP 200 y chainId 42161 (t=50 s, cerca del límite).
- (e) Arbiscan https://arbiscan.io/address/0x38bcF425bC4d13624734e09376F2fafc799fA8c8#code: NO_DISPONIBLE por fetch automático (HTTP 403 Cloudflare). Alternativa, Sourcify v2: delegate 0x38bcF425…A8c8 con exact_match (creation y runtime) en 42161 (verifiedAt 2026-11-21T07:02:51Z, https://sourcify.dev/server/v2/contract/42161/0x38bcF425bC4d13624734e09376F2fafc799fA8c8) y en 8453. eth_getCode en Arbitrum: 6059 bytes. HIPOTESIS: Arbiscan muestra la verificación de Sourcify; queda pendiente comprobarlo a mano en un navegador.
- (f) 0 transacciones firmadas en esta orden.

## Hallazgos que bloquean el E2E
- HECHO: el contenedor arb no tiene relayer/data/ofac_eth.json; Base sí lo tiene (montaje projects/unsweep/relayer/data). ofac_set() falla cerrado, de modo que todo /api/rescue en Arbitrum se rechaza con 'lista OFAC no disponible'. No hay riesgo de evadir sanciones, pero el rescate en Arbitrum NO funciona.
- HECHO: /api/health devuelve ok=true aunque ofac_entries sea 0. Es un indicador engañoso; debería devolver ok=false.
- HECHO: goplus_flag usa chain_id=8453 fijo en el código, también en Arbitrum (deuda pendiente).
- No se abre la solicitud de USDC en HUMANO.md: el E2E fallaría por OFAC antes de usar los fondos. Primero hay que generar ofac_eth.json en el directorio data de arb, con ofac_update.py o copiándolo; es tarea interna y no necesita al humano.

## Rollback
cat logs/Caddyfile.pre_orden1195_p1.20261122T073415Z > projects/x402-netcheck/Caddyfile && docker exec x402-netcheck-caddy-1 caddy reload --config /etc/caddy/Caddyfile --adapter caddyfile
