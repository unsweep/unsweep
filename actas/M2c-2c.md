# Acta UNSWEEP M2c-2c (Base Sepolia, chainId 84532), 2026-11-21

Resultado: **BLOQUEADA en el paso 1 (escaneo)**. Único intento, sin reintento (anti-bucle). Sin firma, sin llamada a /api/rescue, sin transacción de rescate.

## Correcciones de la #72 y la #74 (aplicadas y verificadas)
- Turnstile: claves de TEST oficiales de Cloudflare (https://developers.cloudflare.com/turnstile/troubleshooting/testing/) en `environment:` de deploy/docker-compose.yml, solo en el contenedor unsweep-relayer (84532). `/api/health` -> `turnstile:"test"`. product.env no se ha tocado; cabeceras y CSP de la #552 intactas; escaneo mainnet de M2d sin cambios (200).
- Víctima nueva con 400 USD (< límite de beta de 500): 300 tUSDC + 100 tGOV.

## Preparación
- Víctima: 0xbAD61DA6AcfB81639591802762679976C25DedCB
- Segura: 0x259A23db05D3123e189C7d318fD534888f245211
- Comisión: 0x7E26916f1FF93FcF6CCd7eAaa0561007783FDA1B
- Atacante (sweeper): 0x7Dd4071C33D40CDb50Dfa3096610F72aa409E0A7
- Mint 300 tUSDC: 0xf29bca04dce8bd68c9dbb2f44c8458c9399b5bbb1e2876f01a87d5b9717d4da6 (bloque 61527115)
- Mint 100 tGOV: 0x12d0153f898c6ce6f2fd33517b812a7c987611c37c8b1504c6f356db5b7b089e (bloque 61527134)
- Cebo de 0.00002 ETH desde OPS: 0xa5a7448650995ffc039dbdafd69324f09ab8a2b394194748c9e4c4f383b78786 (bloque 61527256)
- Barrido del sweeper v2 (tarifa L1 restada, sin SEND_FAIL): 0xc7b75d6bd7ca0dcc5c467066782ab00c49a072c0acdc3636b353394c1054726f
- Sweeper pid 119048: activo antes y después del intento; parado a las 2026-11-21T02:16:55Z.

## Intento web
Error exacto: `RESULT {stage: scan, abort: "TimeoutError: Page.wait_for_selector: Timeout 10000ms exceeded. waiting for locator('#step2') to be visible; locator resolved to hidden <section hidden id=step2>"}`.
Salida del paso 1: `Network: base mainnet (read-only, nothing was signed) ... Rescue is testnet beta only.`

Causa raíz: el commit M2d 362096d dejó `<option value="base" selected>` en `#chain` de web/index.html y scripts/e2e_web.py no selecciona `testnet`. El escaneo se hizo en mainnet y la web, por diseño, no muestra el paso 2. El fallo está en el script del E2E y no en el relayer, Turnstile ni la víctima.

## Saldos (bloques 61527535 -> 61527646): idénticos
| wallet | ETH wei | tUSDC | tGOV |
|---|---|---|---|
| víctima | 2895263811 -> igual | 300000000 -> 300000000 | 100e18 -> 100e18 |
| segura | 0 -> 0 | 0 -> 0 | 0 -> 0 |
| comisión | 0 -> 0 | 0 -> 0 | 0 -> 0 |
| atacante | 38118185816068 -> igual | 0 -> 0 | 0 -> 0 |

## Corrección propuesta (NO ejecutada en esta misión)
En e2e_web.py, antes de `#btnScan`: `page.select_option('#chain', 'testnet')`. Además, comprobar que STEP1 contiene 'Base Sepolia' y que la víctima conserva sus tokens (el sweeper no captura ERC-20).

## Registro
PostgreSQL dbname=unsweep, tabla e2e_actas (mision M2c-2c). Logs: .e2e/e2e_run_m2c2c.log y .e2e/m2c2c_balances.txt (no versionados).
