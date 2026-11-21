# Acta UNSWEEP M2c-2b (Base Sepolia, chainId 84532), 2026-11-21

Resultado: **BLOQUEADA en el paso 3 (Turnstile)**. Único intento, sin reintento (anti-bucle).

## Corrección de la causa de la #72
La víctima nueva tiene 150 tUSDC + 50 tGOV = 200 USD (testnet), por debajo del límite de beta de 500 USD. La cotización fue **ELEGIBLE**: tUSDC 150 → fee 22.5 / neto 127.5; tGOV 50 → fee 7.5 / neto 42.5; total $200, fee $30 (15 %).

## Preparación (paso 1)
- Víctima: 0x13EF4fA2078A25bDbB79832Ecd38DA3D6c7cFB66
- Wallet segura nueva: 0x259A23db05D3123e189C7d318fD534888f245211
- Comisión: 0x7E26916f1FF93FcF6CCd7eAaa0561007783FDA1B
- Atacante (sweeper): 0x7Dd4071C33D40CDb50Dfa3096610F72aa409E0A7
- Mint tUSDC: 0xf9a68e7d30bc4b0fd8fbd94277a98de70ae786380eb8544db3c64d6a32c9b353
- Mint tGOV: 0xe437fa5cb9f33ecf2f034318a8f83255dbb9d2436afe364d241b8dd801d674fa
- Cebo barrido por el sweeper v2: 0x358e29a6e7abbada905211af0e64ad0e0ca0632df863c9b30847cfc875e6a31f
- El sweeper anterior se mató por PGID; el sweeper v2 corre en el PGID 85765.

## Intento web (pasos 1-3)
- Paso 1, escaneo: OK (tUSDC 150, tGOV 50, nonce 1, sin delegación 7702).
- Paso 2, cotización: OK, elegible.
- Paso 3: **ABORTADO**. `RESULT {stage: quote, turnstile_token: false, abort: turnstile_not_solved_headless}`; 90 s sin token. /api/health informa `turnstile: prod` (en la #72 era `test`). En la consola, el CSP `connect-src` rechaza `data:,` durante el reto de Cloudflare.
- No hubo llamada a /api/rescue (rescue_events: 0 `rescue` y 0 `simulate`) ni transacción de rescate.

## Saldos (bloques 61519079 → 61519958): idénticos
| wallet | tUSDC | tGOV |
|---|---|---|
| víctima | 150000000 → 150000000 | 50e18 → 50e18 |
| segura | 0 → 0 | 0 → 0 |
| comisión | 0 → 0 | 0 → 0 |
| atacante | 0 → 0 | 0 → 0 |

El sweeper no capturó ningún token.

## Incidencias sin efecto en cadena
1. Primera preparación: `cast wallet new --json` (cast 1.10) devuelve un sobre `{schema_version,success,data}` y el parseo falló; no se envió ninguna tx (nonce OPS = 13). Se rehízo con openssl + `cast wallet address`.
2. Primer lanzamiento E2E con el python3 del sistema: ImportError de playwright, sin contacto con la web. Hay que usar `.venv/bin/python`.

## Registro
PostgreSQL `dbname=unsweep`, tabla `e2e_actas` id=1 (sql/002_e2e_actas.sql). Log: .e2e/e2e_run_m2c2b.log (no versionado).

## Opciones para cerrar M2c-2 (decide el humano)
(a) Clave de test de Turnstile solo en el relayer de testnet para el E2E.
(b) Que el humano complete el paso 3 en un navegador real.
(c) Revisar el CSP o el entorno headless frente al reto de Turnstile.
