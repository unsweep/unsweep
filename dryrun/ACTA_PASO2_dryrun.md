# ACTA UNSWEEP FASE 2, PASO 2: dry-run CREATE2 en forks (2026-11-21T06:20:28Z)

Estado de la OPS 0xF48c54ab4D91C2328111082331ABb4eBA8c2c031: eth_getBalance = 0x0 en Base (chainId 0x2105) y en Arbitrum One (0xa4b1). Por tanto, caso SIN FONDOS: no se ha gastado nada ni se ha firmado nada en mainnet.

Script: script/DeployMainnetCreate2.s.sol (CREATE2 mediante el deployer determinista 0x4e59b44847b379578588920cA78FbF26c0B4956C; idempotente: si hay código en la dirección predicha, lo omite).
Constructor: owner = feeRecipient = 0x7E26916f1FF93FcF6CCd7eAaa0561007783FDA1B, feeBps = 1500, claimTargets = [].
Forks: anvil 1.10.0, Base en el bloque 60257733 y Arbitrum en el bloque 526159551. Firmante: clave pública 0 de anvil (con CREATE2 la dirección no depende de quién despliega; no se usó OPS_PK).

## Resultado (idéntico en las dos cadenas)
- UnsweepConfig:   0x56a345661e3999F2b20f1E069aAC14097Fa0D118
- UnsweepDelegate: 0x38bcF425bC4d13624734e09376F2fafc799fA8c8
- Leído tras el despliegue (cast call) en 8453 y 42161: owner = 0x7E26…DA1B, feeRecipient = 0x7E26…DA1B, feeBps = 1500, pendingOwner = 0x0
- claimTargets vacía: 0 eventos ClaimTargetSet (keccak 0x30f1e4f6…). El único log es 0xa2ea9883… (cambio de owner)
- Recibos en el fork: status 0x1; gasUsed 278262 (Config) + 1367532 (Delegate)

## Coste real (lectura sin firma en mainnet: eth_estimateGas, gasPrice, GasPriceOracle.getL1Fee de Base, NodeInterface de Arbitrum)
- estimateGas real: 281638 + 1391575 en las dos cadenas
- Base: gasPrice 8139100 wei; tarifa L1 2.67e10 + 1.096e11 wei (cota superior 4.30e10 + 1.58e11)
- Arbitrum: gasPrice 20074000 wei; gasEstimateL1Component = 0 en los dos tx (l1BaseFeeEstimate = 0). gasEstimateComponents revierte con contractCreation=true (observación; cubierta por el margen)
- Base 8453: estimado 0.00001375 ETH = 0.0216 USD | peor caso (gas x5, L1 cota x3) 0.00006870 ETH = 0.1077 USD | tope 10 USD: OK
- Arbitrum 42161: estimado 0.00003359 ETH = 0.0527 USD | peor caso (gas x5, L1 cota x3) 0.00016794 ETH = 0.2633 USD | tope 10 USD: OK
- ETH/USD Chainlink Base = 1567.90
- Feed: Chainlink ETH/USD en Base 0x71041dddad3595F9CEd3DcCFBe3D1F4b0a16Bb70 (antigüedad 63 s)

Conclusión: las dos cadenas quedan muy por debajo del tope de 10 USD. Datos en bruto: dryrun/dryrun_raw.log, dryrun/cost_raw.log, dryrun/arb_l1_raw.log.

Verificación de UI-2 y la #773: origin/main = e403182 = rama ui-2; los sha256 de index.html y style.css en https://unsweep.com coinciden con origin/main (subtítulo y font-size 1rem servidos).
