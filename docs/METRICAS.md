# METRICAS UNSWEEP (uso interno, NO publicar en la web)

## Tiempo E2E del rescate real de 2 USDC en Base mainnet (orden #964, PASO 2)

| Hito | Marca UTC | Fuente |
|---|---|---|
| C-pre: dry-run mainnet OK (victim_usdc=2000000, sin envio) | 2026-11-21T14:13:01Z | acta L307 |
| C: sweeper hostil activo | 2026-11-21T14:13:06Z | acta L308 |
| C: rescate enviado (rescue_exit=0) | 2026-11-21T14:13:09Z | acta L309 |
| Inclusion en cadena, bloque 60400067 (status 1) | 2026-11-21T14:13:09Z | timestamp del bloque via eth_getBlockByNumber en https://mainnet.base.org |
| Verificacion dual RPC (Alchemy + Chainstack) | 2026-11-21T14:13:57Z | acta L310 |

Resultados:
- HECHO: de la cotizacion/dry-run a la inclusion en cadena = 8 s (14:13:01Z -> 14:13:09Z).
- HECHO: del envio a la inclusion = 0 s, con resolucion de 1 s (mismo segundo del bloque).
- HECHO: de la cotizacion/dry-run a la verificacion independiente dual RPC = 56 s.

Limitaciones:
- Fue un rescate operado por AIRE con un script (MISION-PASO3-R3), no una sesion de usuario por la web. No incluye el escaneo en el navegador, la firma del usuario ni Turnstile. NO es representativo del tiempo de un usuario real.
- Las marcas del acta tienen resolucion de 1 s.

Fuentes:
- Acta: /opt/aire/workspace/unsweep-mainnet/.e2e/paso3_mainnet.log, lineas 307-311 (commit c82e3290ee6eebaaede349cffa8ec60210564cc9 del repo unsweep-mainnet).
- Tx: https://basescan.org/tx/0x61a0752e23a5bb31ee1c3ad116f4dbea4b4d2fbd40ddaa5cdbcd34469ce90730 (bloque 60400067).

Politica: este dato NO se publica en la web (orden #964).
