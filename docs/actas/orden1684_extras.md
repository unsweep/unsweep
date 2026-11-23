# Acta ORDEN #1684: fix de descubrimiento de extras en /api/scan (UNSWEEP)
Fecha: 2026-11-23 (UTC). Ejecutor: AIRE (Claude). No se ha contactado a terceros. No contiene secretos: las URLs de RPC están enmascaradas.

## 1. Causa raíz (HECHO)
Medido con una sola llamada alchemy_getTokenBalances desde el contenedor `unsweep-relayer`.
- `svc_core.py`: `RPC = UNSWEEP_RPC` y `w3 = Web3(HTTPProvider(RPC))`.
- En producción, `UNSWEEP_RPC` = `https://main***base.org`, que es el RPC público de Base y no Alchemy.
- `alchemy_getTokenBalances` contra UNSWEEP_RPC devuelve **HTTP 401** con `{"error":{"code":-32611,"message":"rejected due to request filter settings"}}`. La librería lo eleva como HTTPError y el fail-soft lo registraba como `WARNING extras no disponibles: HTTPError`.
- La misma llamada contra `BASE_RPC_URL` (`base***alchemy.com`) devuelve **HTTP 200** con tokenBalances.
- **Clasificación: (a) método no soportado, porque w3 no apunta a Alchemy.** No es un problema de clave (b) ni de cuota (c).

## 2. Corrección (commit a09d323541f48715c921c05ef206387456a22067, rama main, ya en origin)
Cambia `relayer/svc_scan.py` (+68 líneas) y añade `relayer/test_extras_1684.py`.
- Cliente dedicado `_extras_rpc`. El endpoint sale de `UNSWEEP_EXTRAS_RPC` si existe; si no, del host Alchemy por CHAIN_ID (8453 → base-mainnet, 42161 → arb-mainnet) con la ruta de clave de `BASE_RPC_URL`, que ya existía. Nunca usa el w3 público.
- Cualquier error JSON-RPC, aunque llegue con HTTP 200, lanza `ExtrasError` con un motivo concreto (código HTTP, código RPC y mensaje), sin URL.
- Ante un 429 reintenta 3 veces con backoff de 0,5·2^i s.
- Se mantienen: `value_usd=0`, `unverified=True`, la fee en especie con el mismo bps (no se ha tocado `extras.py` ni `select_extras`) y el fail-soft, que devuelve `[]` y ahora registra el motivo concreto.
- No cambian los estáticos, así que no hace falta recalcular el SRI.

## 3. Tests
- 7 tests nuevos en `test_extras_1684.py`: 401 con motivo, error con HTTP 200 (caso Arbitrum), backoff 429, 429 agotado y éxito con `value_usd=0`, entre otros.
- `relayer/`: **150 passed** (143 previos + 7). `deploy/tests` + `tools`: 15 passed.

## 4. Despliegue y verificación en Base
- `deploy/deploy_relayer.sh --commit a09d323…` a las 23:34:01Z: health OK 3/3. `https://unsweep.com/api/health` da 200 con `chainId 8453, mainnet true`.
- El contenedor contiene `_extras_rpc`.
- Nota: `https://40-75-139-128.sslip.io/api/health` devuelve 410. Es el Caddy de x402-netcheck y no afecta a UNSWEEP.
- Holders obtenidos de logs Transfer de BRETT (0x532f27101965dd16442E59d40670FaF5eBB142E4, que no está en assets_8453.json) en ventanas de 10 bloques, porque el plan Free de Alchemy limita eth_getLogs.
- Scan 1: holder `0x81db196456ad53fa2c8131a9d276c8c1e661cf4d`. HTTP 200 en 32,2 s, con 50 extras, todos `value_usd=0`. **BRETT no aparece por el recorte `exs[:50]`**: la cartera tiene más de 50 tokens spam con direcciones ordenadas antes que BRETT. Es un fallo previo a este cambio, no corregido aquí.
- Scan 2 (tras 20 s de espera): holder `0x7d4fcf1c7e7e63d07fe79a2232f2f2e682fbd356` (tx 0x6c89b061…db65, bloque 61432167). **HTTP 200 en 7,6 s. Extras: BASED y BRETT, ambos `unverified=true` y `value_usd=0`.**
- Limitación: esa dirección no tiene tokens listados (`rescuable=false`), así que no se genera quote. La fee en especie al mismo bps está respaldada por el diff (código de fee intacto) y por los tests, **no por un scan en vivo**.
- Logs: antes había `2026-11-23 23:21:27,770 WARNING extras no disponibles: HTTPError`. Después del despliegue, `docker logs --since 2026-11-23T23:34:01Z unsweep-relayer | grep -c 'extras no disponibles'` da **0**.

## 5. Arbitrum: AFECTADO y NO desplegado
- `w3 = UNSWEEP_RPC = arb1***arbitrum.io` (público).
- Devuelve HTTP 200 con `{"error":{"code":-32601,"message":"the method alchemy_getTokenBalances does not exist/is not available"}}`. Como el código viejo hace `.get('result')`, obtiene None y extras=[] **sin ningún log**. Por eso había 0 warnings en arb: es un fallo silencioso.
- La misma clave de Alchemy contra arb-mainnet devuelve HTTP 200.
- Fix preparado en la rama `fix-extras-1684-arb` (92bdd0aac7bbe0dea3da87a05a4e5e7f9f702f4b = deb3bcd + cherry-pick de a09d323, aplicado limpio). Rama publicada en origin.
- Sus tests no se ejecutaron: en el worktree nuevo hay un FileNotFoundError en la colección, probablemente porque `relayer/data` (o el symlink de OFAC) no está versionado. **No está verificado.**
- No se despliega por riesgo. El contenedor monta en vivo `/opt/aire/workspace/unsweep-arb-v12e` (uvicorn sin `--reload`):
  - `deploy_relayer.sh` apunta a `ARB_REPO=/opt/aire/workspace/unsweep-arb-deploy`, que no existe.
  - El árbol v12e tiene un cambio de tipo en `relayer/data/ofac_eth.json`. En HEAD es un symlink hacia `/ofac`, pero `/opt/aire/unsweep-ofac` no contiene `ofac_eth.json`.
  - El archivo actual tiene 5 entradas, modificado el 23-11 a las 03:31 por `unsweep-ofac-update.timer`. El proceso en marcha reporta 123 entradas.
  - Recrear o reiniciar el contenedor cambiaría la lista OFAC cargada, o la rompería. Esa decisión corresponde al humano.
- El árbol vivo v12e y el contenedor arb no se han tocado: deb3bcd, Up 40 h, `/arb/api/health` da 200.

## 6. Métricas
- El worktree `tmp/metrics` [metrics-orden1646] sigue en 7bfa82d, con 1 línea en status igual que antes. No se ha ejecutado `prune`.
- Timers presentes: unsweep-f5bot, unsweep-funnel (próximo a las 23:55) y unsweep-ofac-update. No se ha modificado ningún timer.

## Pendientes
- Decisión humana sobre el despliegue de Arbitrum y la lista OFAC.
- Priorizar tokens no spam o subir el tope `exs[:50]`.
- Verificar en vivo la fee en especie con una dirección que tenga un token listado más un extra.
