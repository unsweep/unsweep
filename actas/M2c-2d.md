# Acta UNSWEEP M2c-2d (Base Sepolia, chainId 84532), 2026-11-21

Resultado: **COMPLETADA**. Único intento E2E por la web real https://unsweep.com, sin reintento.

## Correcciones aplicadas
- d97849b: ROADMAP_GATES.md (gates 1-4 literales de la ORDEN #621).
- 2df7854 + b0d1f45: e2e_web.py hace select_option('#chain','testnet') antes de escanear y exige 'Base Sepolia' en la red seleccionada de STEP1 (en #scanOut no aparece nunca la red: la primera versión de la comprobación daba un falso negativo en la ejecución en seco). web/index.html, el relayer y el escáner de mainnet no se han tocado.

## Validación sin clave (ejecución en seco hasta el paso 2)
- STEP1_NETWORK: Base Sepolia testnet (rescue beta)
- STEP2: cotización de $400 (< límite de beta de 500), comisión de $60; tUSDC 300 -> 255/45; tGOV 100 -> 85/15
- /api/health: chainId 84532, mainnet false, turnstile "test"

## Preparación
- Víctima 0xbAD61DA6AcfB81639591802762679976C25DedCB | Segura 0x259A23db05D3123e189C7d318fD534888f245211 | Comisión 0x7E26916f1FF93FcF6CCd7eAaa0561007783FDA1B (feeBps=1500 leído en cadena del Config 0xbe0E049F17836736772206E6BA3C3EfF21C2E0bC) | Atacante 0x7Dd4071C33D40CDb50Dfa3096610F72aa409E0A7
- Sweeper v2, pid 125296: activo antes y después del intento (arranque 02:31:07Z); parado al cerrar el acta.
- OPS 0xF48c54ab4D91C2328111082331ABb4eBA8c2c031: 0.003505 ETH, gas suficiente.

## Rescate
- Tx: https://sepolia.basescan.org/tx/0x47fe95cfa08816b5d1a23903f3f115680be11fc1e4144dae2178b57ccbcf004d
- Recibo por RPC: status 0x1 (Success), bloque 61532746, gasUsed 181680, from OPS, to víctima (EIP-7702)
- /api/rescue HTTP 200; Turnstile en modo test con token obtenido en 2 s.

## Saldos por RPC (antes: bloque 61532215; después: bloque 61532802)
| wallet | tUSDC raw | tGOV raw | ETH wei |
|---|---|---|---|
| víctima | 300000000 -> 0 | 100e18 -> 0 | 2895263811 -> igual |
| segura | 0 -> 255000000 | 0 -> 85e18 | 0 -> 0 |
| comisión | 0 -> 45000000 | 0 -> 15e18 | 0 -> 0 |

Reparto: tUSDC 255/300 = 85 % y 45/300 = 15 %; tGOV 85/100 = 85 % y 15/100 = 15 %. Se conserva todo (salidas = entradas). El sweeper no capturó nada.
Limitación: el parser de logs Transfer del recibo no imprimió líneas. El reparto se prueba con la diferencia de saldos por RPC.

## Registro
PostgreSQL dbname=unsweep, tabla e2e_actas (mision M2c-2d). Logs: .e2e/e2e_run_m2c2d.log, .e2e/m2c2d_saldos_antes.txt, .e2e/m2c2d_saldos_despues.txt
