# UNSWEEP: hoja de ruta por gates

Fuente: memoria AIRE #621 [DECISION|vigente|2026-11-21], consenso Agente A/B, aprobada por el humano. Leída de `psql aire: select * from notes where id=621`. Este fichero se consulta en cada planificación.

## Texto literal (ORDEN #621)

> REGLA: cuando un gate se cumpla, registrar la evidencia en HUMANO.md y ESPERAR aprobación humana antes de cualquier paso que gaste dinero o toque mainnet.

> GATE 1 (mainnet L2 + M3): E2E cerrada con hash en Base Sepolia + D2 con >=200 wallets con >=50 USD rescatables + revisión humana del contrato + login SSH por contraseña desactivado. Cadenas en el orden que indique el valor rescatable de la D2 (Base y Arbitrum por defecto). M3: repositorio público con README técnico, /llms.txt, JSON-LD SoftwareApplication (FAQPage opcional, sin contar con fragmentos), máximo 8 páginas EN con contenido útil por sí mismo y escáner arriba, comparativa honesta, comprobación diaria sin modelos en Google Safe Browsing y en eth-phishing-detect de MetaMask con aviso en HUMANO.md, OPS máximo 20 USD, rotar ETHERSCAN_API_KEY. Si la D2 da <50 wallets: congelar y no activar mainnet.

> GATE 2 (Ethereum mainnet vía Flashbots Protect; BSC solo si 48 Club acepta tx tipo 4 comprobado; español en portada + 3 guías): >=1 rescate en mainnet o >=50 escaneos válidos (que pasaron Turnstile y con activos detectados) en 45 días desde el primer despliegue en mainnet. Freno: <50 escaneos y 0 rescates a los 45 días = modo pasivo.

> GATE 3 (posiciones bloqueadas, ENS, migración completa, publicación en fechas de airdrops): >=3 rescates cobrados; no construir módulos de protocolos sin casos detectados en escaneos.

> GATE 4 (alertas por suscripción, más idiomas, investigación de bug bounties y documentación de SEAL Safe Harbor): >=10 rescates o 3 meses seguidos con >=1 rescate.

> Siempre prohibido intervenir en protocolos no adheridos o explotar fallos. Directorios y SEAL 911: solicitar solo con mainnet funcionando. La mejora visual de la UI queda EN PAUSA por decisión humana.

## Estado del GATE 1 (actualizado en la misión M2c-2d)

| Requisito | Estado | Evidencia |
|---|---|---|
| E2E cerrada con hash en Base Sepolia | PENDIENTE | M2c-2b bloqueada (Turnstile prod, memoria #607). M2c-2c bloqueada en el escaneo (la web toma mainnet por defecto, commit 15ab737). Intento único M2c-2d en curso; ver e2e_actas. |
| D2 con >=200 wallets con >=50 USD rescatables | PENDIENTE | D2 ciclos 1 y 2 (#588, #590): la muestra de Base cubre 9 días (no 90), con 133 EOAs con autorización 7702. No hay recuento registrado de wallets con >=50 USD rescatables (NO_DISPONIBLE). |
| Revisión humana del contrato | PENDIENTE | No hay registro en HUMANO.md (grep sin resultados). |
| Login SSH por contraseña desactivado | PENDIENTE | `sudo sshd -T`: passwordauthentication yes (2026-11-21). |
| M3: repo público con README técnico | PENDIENTE | Repo github.com/unsweep/unsweep (#56). README.md tiene 66 líneas. Push pendiente (solicitud #61). |
| M3: /llms.txt | PENDIENTE | https://unsweep.com/llms.txt devuelve HTTP 404. |
| M3: JSON-LD SoftwareApplication | PENDIENTE | No hay `@type` en la portada (curl + grep). |
| M3: <=8 páginas EN útiles, escáner arriba | PENDIENTE | sitemap.xml con 4 `<loc>`; falta verificar el contenido de cada página. |
| M3: comparativa honesta | PENDIENTE | No verificada. |
| M3: comprobación diaria Safe Browsing + eth-phishing-detect con aviso | PENDIENTE | No hay ninguna tarea en crontab. |
| M3: OPS máximo 20 USD | PENDIENTE | Se mide en el paso 3 de M2c-2d (saldo de la OPS en mainnet = sin fondear). |
| M3: rotar ETHERSCAN_API_KEY | PENDIENTE | No hay registro de rotación. |

GATE 2, 3 y 4: NO INICIADOS (requieren mainnet y la aprobación humana del GATE 1).

## Actualización 2026-11-21 (M2c-2d)
- GATE 1, sub-requisito 'E2E cerrada con hash en Base Sepolia': **HECHO**. Tx https://sepolia.basescan.org/tx/0x47fe95cfa08816b5d1a23903f3f115680be11fc1e4144dae2178b57ccbcf004d (status 0x1, bloque 61532746); reparto 85/15 verificado por saldos RPC; acta actas/M2c-2d.md. El resto de requisitos del GATE 1 sigue PENDIENTE según la tabla de arriba.
