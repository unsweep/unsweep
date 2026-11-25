# OP Mainnet (chainId 10): plan y checklist (ORDEN #2236, fase A)

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
| `relayer/data/assets_42161.json` | sí | NO_DISPONIBLE: no existe `assets_10.json`; `_listed` devuelve [] |
| Oráculos de precio (Chainlink, etc.) | según el repo | NO_DISPONIBLE: no hay direcciones de OP en el repo ni verificadas |
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
3. `assets_10.json` y oráculos de OP: solo con direcciones verificadas por RPC (getCode + symbol/decimals). USDC u otros: NO_DISPONIBLE.
4. Política y comisiones para el 10 (`policy.MAINNETS`, `ACTIVE_MAINNETS`): fuera del alcance; solo tras el punto 1.
5. Frontend (app.js e index.html: selector y explorador `optimistic.etherscan.io`), gen_portada y SRI.
6. svc_scan (logs de approvals en OP) y extras.
