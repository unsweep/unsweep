# UNSWEEP - Alcance del relayer en Base (8453)

Estado: PARCIAL (2026-11-21). Rama `assets-chainlink`, worktree `/opt/aire/workspace/unsweep-assets`, base cd23417. Sin cambios en contratos, sin push y sin despliegue. Producción no se ha tocado.

## 1. Qué permite UnsweepDelegate (HECHO, código fuente `src/UnsweepDelegate.sol`; despliegue en `deployments/mainnet.txt`)

- `rescue()` ejecuta `_runCalls` (llamadas `c.target.call(c.data)`) ANTES de `_sweepTokens` y `_sweepNfts`, todo en la MISMA transacción. El patrón "claim + transferencia" en una sola operación está soportado por diseño.
- Restricciones de cada llamada:
  - `value == 0`.
  - `target` debe estar autorizado en `UnsweepConfig.claimTarget`.
  - `target` no puede ser el propio delegate, ni un token de `r.tokens`, ni un NFT de `r.nfts`.
- Comprobaciones posteriores: revierte si algún NFT de la cesta deja de pertenecer a la víctima (`NftMoved`) o si bajan los saldos de los tokens de la cesta.
- En mainnet (Config `0x56a345661e3999F2b20f1E069aAC14097Fa0D118`, Delegate `0x38bcF425bC4d13624734e09376F2fafc799fA8c8`) la lista de `claimTarget` está VACÍA. HOY en la práctica solo se pueden barrer ERC-20 y ERC-721. Habilitar un claim exige que el owner de Config autorice el destino (decisión humana, fuera de esta misión).
- ETH nativo: no hay ruta de barrido.

## 2. Activos con feed oficial de Chainlink en Base (HECHO; evidencia en `evidence/chainlink/`)

Fuentes:
- Feeds: directorio oficial `https://reference-data-directory.vercel.app/feeds-ethereum-mainnet-base-1.json`, guardado en `feeds-ethereum-mainnet-base-1.json` (`fetched_at.txt`).
- Criterio de feed estándar: `path` sin "svr", `ens` no nulo y no oculto. En las entradas "Shared SVR" se usa el `secondaryProxyAddress` cuyo `secondaryProxyEns` no es nulo (p. ej. ETH/USD `0x71041dddad3595F9CEd3DcCFBe3D1F4b0a16Bb70`, ens eth-usd; BTC/USD `0x64c911996D3c6aC71f9b455B1E8E7266BcbD848F`, ens btc-usd).
- Verificación en cadena de 21 feeds (`onchain_check.txt`): description = par, decimals = directorio, answer > 0, antigüedad < heartbeat. Todos OK.
- Direcciones de tokens: Aave address book (`AaveV3Base.sol`), token lists de Superchain y Uniswap, docs.chain.link (LINK) y docs.ethena.fi (sUSDe). Verificadas en cadena en `tokens_onchain.txt` (code, symbol, decimals, supply).

Lista candidata (token -> feed):
- Feed directo a USD: USDC, USDT, DAI, WETH (ETH/USD), cbETH, cbBTC, LINK, AERO, EURC, GHO, tBTC, sUSDe, COMP, WELL, VIRTUAL, DEGEN.
- Compuestos X/ETH × ETH/USD: wstETH, rETH, weETH (dirección de Aave).

Excluidos:
- USDbC: no tiene feed propio en Base.
- AAVE: solo tiene feed SVR, no verificado como estándar.
- USDS: la dirección en Base no está en la documentación de Sky; solo aparece la etiqueta de BaseScan.
- weETH `0x4c94…5EFA` de la Superchain: supply ~0,0079.

Compuestos y feeds de exchange rate: requieren comprobar el heartbeat de AMBOS feeds. OPINION: dejar rETH (feed de exchange rate, categoría custom) y DEGEN/VIRTUAL (riesgo de mercado) para una segunda fase.

## 3. Pendiente (no implementado)

- `relayer/svc_core.py` y `svc_scan.py:99,102`: sustituir el `price_usd` estático y el `ETH_USD` fijo por `eth_call` a `latestRoundData`, con fail-closed si answer <= 0, `answeredInRound < roundId`, antigüedad > heartbeat o error de RPC. `service.py:17,149` también usa `ETH_USD`.
  - HECHO: `ETH_USD` fijo vale 3000 y el feed daba 1682,74 USD. El coste de gas sale sobreestimado (conservador), pero el valor es incorrecto.
- Ampliar `relayer/data/assets_8453.json` con un campo `feed` (y `feed_eth` en los compuestos) en lugar de `price_usd`.
- Tokens fuera de lista: rechazar con un mensaje que invite a registrar el caso; plantilla en `docs/CASOS.md`.
- Tests en fork de Base (anvil `--fork-url`): feed fresco, feed desactualizado, feed revertido y token fuera de lista. Después, CI en verde.

## 4. Conflicto a resolver

El `_note` de `assets_8453.json` dice "#85=A: solo USDC nativo de Circle". Ampliar la lista puede contradecir esa decisión humana. No se despliega nada hasta que se confirme.

Nota operativa: `cast` está en `/home/tecnoclic/.foundry/bin/cast` (no está en el PATH).
