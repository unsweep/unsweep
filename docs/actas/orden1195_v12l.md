# Acta #1195 v12l (#1193 / #1011 PASO F v12l), 2026-11-22

RESULTADO: **COMPLETADA**. Se ejecutó en una sola pasada, sin reintentos ni fallos.

- SHA: f9275dd5e125cbbdafe6fa4d57030af2c0ab844a (CI success: https://github.com/unsweep/unsweep/actions/runs/44994827743, rama feat-arbitrum-42161-v12f).
- Log: /opt/aire/workspace/logs/pasoF_arb_v12l.log.
- Scripts: /opt/aire/workspace/artifacts/pasoF_v12l/{paso0.sh, paso1_import.py, paso2_sim.sh, paso3_deploy.sh, paso4_arb.sh}.

## PASO 0: precheck (07:06:55Z, solo lectura)

- Base por IP 172.18.0.7:8787: HTTP 200, ok=true, chainId 8453 (lectura 1). Por Caddy: HTTP 200, ok=true, 8453 (lectura 1).
- index.html: 2d5ec0c46b632ca63948db1ffbb1763f909ae3f24179b4eef30fc82443a5d5d7.
- app.js: c29807e0332ca8a0becca6bf3b89e1b291d24666b9826dbb318b54b2d8fb76c1.
- Nonce de OPS en Base: 3/3. Nonce de OPS en Arbitrum: 2/2. Saldo en Arbitrum: 0.005244 ETH.
- Contenedor unsweep-relayer-arb antes del despliegue: imagen 5a1e4c3a…, UNSWEEP_CHAIN_ID=42161, running, restarts=0. Se inspeccionaron solo los nombres de las variables de entorno.

## PASO 1: firmante con keystore de Foundry

- `cast wallet import ops-arb --interactive`, alimentado por un pty desde Python. La clave se leyó de /opt/aire/product.env y no apareció en argv, ps ni en los logs.
- Contraseña aleatoria en /home/tecnoclic/.aire/ops-arb.pass (600; directorio 700), fuera del repo.
- Keystore en ~/.foundry/keystores/ops-arb. Se creó con permisos 644 y se endurecieron a 600.
- `cast wallet address` = **0xF48c54ab4D91C2328111082331ABb4eBA8c2c031**: SIGNER_MATCH=OK.
- Causa de la parada en v12k: `cast send` ignoraba ETH_PRIVATE_KEY. Queda resuelta con `--keystore` y `--password-file`.

## PASO 2: única transacción en Arbitrum

Simulación (07:08:29Z):

- chainId 42161, nonce 2/2, saldo 5243749858744270 wei.
- eth_call=0x (sin revert). estimateGas=21554. gasPrice=0.02 gwei.
- El destino tiene código 0xef0100+63c0c19a282a1b52b07dd5a65b58948a07dae32b, es decir, una delegación EIP-7702. El humano confirmó que la dirección es suya (#131) y fijó el destino y el importe (#132).
- `cast mktx` sin broadcast: from=OPS, to=destino, value=5e14 wei, nonce 2.

Envío (07:08:43Z):

- tx: **0x278230d2f173435ef190d289bfdf97754c0e1bd4fd7f455e8cfe798aa14d534a**
- https://arbiscan.io/tx/0x278230d2f173435ef190d289bfdf97754c0e1bd4fd7f455e8cfe798aa14d534a
- status 0x1, bloque 526450250, gasUsed 21292. 0.0005 ETH de 0xF48c…c031 a 0x7E26916f1FF93FcF6CCd7eAaa0561007783FDA1B.
- Después: nonce de OPS en Arbitrum 3 (latest y pending). Saldo 0.004743324018722978 ETH, menor que 0.005.
- Total: 1 transacción. No se envió ninguna transacción en Base.

## PASO 3: despliegue de relayer-arb

- `deploy_relayer.sh --commit f9275dd… --service relayer-arb`, con `UNSWEEP_ARB_REPO=/opt/aire/workspace/unsweep-arb-v12e`.
  - Desviación anotada: el repo por defecto, unsweep-arb-deploy, no existe.
  - La orden fija el origen en unsweep-arb-v12e, que ya era el config_file de compose del contenedor de Arbitrum.
  - El guard del script impide usar el repo de Base.
- Pasos previos: `--plan` y `--dry-run` OK.
- Imagen nueva: sha256:55cf28df849a… Rollback disponible: unsweep-relayer-arb:rollback-f9275dd5.
- Health del script: 3/3 consecutivos con True 42161 True. Secretos prohibidos en el contenedor: ninguno. deploy_rc=0.
- Contenedor de Base después del despliegue, idéntico a la línea base: Id c0bbe7ab…, imagen 7c209387…, StartedAt 05:34:43Z, restarts=0.

## PASO 4: verificación (07:10:30Z a 07:10:49Z)

- Health de Arbitrum (172.18.0.8:8787): HTTP 200, ok=true, chainId 42161, mainnet=true (lectura 1).
- POST /api/scan en Arbitrum con la dirección pública 0x38bc…A8c8: HTTP 200 en 5 s, chainId 42161, approvalsError=null, sin 429.
- Base por IP y por Caddy: HTTP 200, ok, 8453 (lectura 1 en cada vía).
- Hashes sin cambios: index 2d5ec0c4…, app.js c29807e0….
- Nonce de OPS en Base: 3/3 (saldo 0.004936 ETH). Nonce de OPS en Arbitrum: 3/3.

## Criterios

| Criterio | Resultado |
|---|---|
| (a) Firmante del keystore = 0xF48c…c031, sin exponer secretos | OK |
| (b) 1 tx confirmada, saldo < 0.005 ETH, nonce 3 | OK |
| (c) relayer-arb desde f9275dd, health 42161 y /api/scan 200 sin 429 | OK |
| (d) Base intacta: contenedor, imagen, hashes y nonce 3 | OK |
| (e) Acta y memory_save | OK |

## Notas

- El aviso "Bad substitution" del dry-run venía del envoltorio en /bin/sh, no del script de despliegue.
- Un intento de respuesta que no era JSON válido no ejecutó nada.
- Al principio cité una delegación EIP-7702 del destino sin haberla verificado. Quedó verificada en cadena en el PASO 2.
