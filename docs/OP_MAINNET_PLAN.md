# OP Mainnet (chainId 10): plan y checklist (ORDEN #2236, fases A y B)

Base: origin/main 749f147a168a51a7e8e9883d413bd7ead454d53d (verificado con `git ls-remote`). Rama local: prep-2236. Sin push ni despliegue.

Alcance de la fase A: solo diagnóstico read-only. **El rescate en OP está DESHABILITADO** (`op_mainnet.RESCUE_ENABLED = False`; 10 no está en `policy.MAINNETS` ni en `relayer.ACTIVE_MAINNETS`).

## Checklist: dónde está parametrizado Arbitrum (42161 / arb) y su estado para OP

| Punto | Arbitrum | OP (10) en fase A |
|---|---|---|
| `relayer/policy.py` `MAINNETS = {1, 8453, 42161}` | sí | NO añadido (a propósito: el rescate sigue rechazado) |
| `relayer/relayer.py` `ACTIVE_MAINNETS` | sí | NO añadido (sin firma/envío en OP) |
| `relayer/service.py` `/api/scan` usa `svc_mainnet.CHAINS` | vía config | HECHO: `optimism` acepta el scan por herencia de CHAINS |
| `relayer/svc_mainnet.py` `CHAINS` | env/chain_id/explorer | HECHO: `optimism` -> `OP_RPC_URL`, 10, `https://optimistic.etherscan.io/address/` |
| `relayer/svc_scan.py` mapa RPC por chainId (líneas ~100-103) y `APPROVAL_LOGS_ENABLED` | 42161 parametrizado, no activo | PENDIENTE (fase B) |
| `relayer/data/assets_42161.json` | sí | HECHO (fase B): `assets_10.json`, 8 tokens (USDC, USDT, DAI, WETH, OP, WBTC, LINK y wstETH) verificados por eth_call en el bloque 160020169 |
| Oráculos de precio (Chainlink, etc.) | según el repo | HECHO (fase B): 8 feeds /USD del directorio oficial (copia en `evidence/chainlink/feeds-ethereum-mainnet-optimism-1.json`), con decimals(), latestRoundData() y aggregator() comprobados por eth_call |
| Extras (`test_extras_1684.py`) | sí | PENDIENTE (fase B) |
| `web/assets/app.js` (selector/`explorerAddressUrl`) | `arbiscan.io` | NO TOCADO: PENDIENTE (fase B, requiere node --check y SRI) |
| `web/index.html` selector de red | sí | NO TOCADO |
| `tools/gen_portada.py` y `relayer/test_portada.py` | sí | NO TOCADO |
| `scripts/check7702.sh`, `scripts/check7702_rpc.py` | sí | NO TOCADO |
| Tests existentes (`test_service_policy`, `test_min_fee_token_731`, `test_ux_1638`) | sí | sin cambios; `test_service_policy` sigue exigiendo el rechazo de 10 |

## Hecho en la fase A
- `relayer/op_mainnet.py`: constantes de OP y bandera `RESCUE_ENABLED = False`.
- `relayer/svc_mainnet.py`: entrada `optimism` en CHAINS (lectura de saldos y getCode de la delegación EIP-7702).
- `relayer/test_op_mainnet_2236.py`: 6 tests unitarios sin red.
- e2e read-only (script fuera del repo): eth_chainId = 0xa en el bloque 160019929.

## Verificado on-chain (no añadido aún)
- WETH predeploy de OP Stack `0x4200000000000000000000000000000000000006`: eth_getCode = 2041 bytes, symbol() = WETH, decimals() = 18 (vía OP_RPC_URL). Candidato para `assets_10.json` en la fase B.

## Pendiente (NO_DISPONIBLE / requiere decisión)
1. Desplegar y verificar UnsweepDelegate (y Config) en OP: no existe dirección en OP; no se despliega en esta fase.
2. Financiar el gas en OP de la wallet OPS (saldo en OP = 0 wei, medido en el e2e). Requiere una solicitud al humano con la simulación previa.
3. HECHO en la fase B (ver abajo). Excluidos: USDC.e, ETH 0xDead (OVM), TRX/APT/SOL puenteados y emparejamientos no equivalentes.
4. Política y comisiones para el 10 (`policy.MAINNETS`, `ACTIVE_MAINNETS`): fuera del alcance; solo tras el punto 1.
5. Frontend (app.js e index.html: selector y explorador `optimistic.etherscan.io`), gen_portada y SRI.
6. svc_scan (logs de approvals en OP) y extras.

## Hecho en la fase B (ORDEN #2236)
- e2e de solo lectura `relayer/test_e2e_op_2236.py` (skip si falta OP_RPC_URL): eth_chainId == 10, scan con getCode y detección de delegación EIP-7702 sobre WETH 0x4200…0006 (contrato) y 0x…dEaD (EOA). 4 passed.
- **UnsweepDelegate `0x38bcF425bC4d13624734e09376F2fafc799fA8c8` NO tiene bytecode en OP (eth_getCode = 0 bytes)**, así que el rescate en OP queda **NO_DISPONIBLE** hasta que se despliegue. No se ha implementado ninguna ruta de envío (`RESCUE_ENABLED = False`, 10 fuera de `policy.MAINNETS` y de `ACTIVE_MAINNETS`).
- `tools/gen_assets_10.py` genera `relayer/data/assets_10.json` y la evidencia `artifacts/m2236/onchain_10.json` (bloque 160020169). Fuentes: `evidence/chainlink/superchain.tokenlist.json` (chainId 10) y el directorio oficial de Chainlink (`feeds-optimism.source`, con sha256).
- Tests sin red: `relayer/test_assets_10_2236.py` (6) y `test_op_mainnet_2236.py` actualizado (`_listed` == `assets_10.json`).
