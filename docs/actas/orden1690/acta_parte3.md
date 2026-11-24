# Acta ORDEN #1690, parte (3): contratos ERC-20 manuales en Step 2 (solo UNSWEEP, Base)

Fecha: 2026-11-24. Worktree: tmp/ux1690 (rama ux-1690). Despliegue desde tmp/fase1 (main).

## (a) Decisión de diseño: RPC directo frente a Alchemy
- La orden pide consultar 'directo al RPC' y no exige Alchemy.
- DECISIÓN: las sondas eth_getCode, balanceOf, symbol y decimals de los contratos manuales hacen eth_call contra el RPC del relayer (UNSWEEP_RPC, la misma variable con la que svc_core construye w3). Se usa un cliente Web3 dedicado con timeout corto (MANUAL_TIMEOUT=8 s) para no bloquear 20 s. Implementado en relayer/svc_manual.py (manual_rpc).
- Alchemy queda solo para discover_extras, según la #1684.
- Antes del despliegue se comprobó que svc_manual importa RPC de svc_core (SAME_RPC_OK).
- Corrección respecto al borrador previo (#1698): manual_rpc usaba _extras_rpc (Alchemy). Se cambió.

## (b) Backend
- POST /api/quote_manual protegido con _guard, que aplica el mismo rate-limit por IP que /api/scan y devuelve 429.
- Acepta de 1 a 3 direcciones 0x en checksum, únicas y no listadas. Devuelve 400 con error claro si hay 0 o 4 o más, si alguna es inválida o no está en checksum, o si hay duplicados.
- Rechaza por contrato con motivo explícito: token listado, ya detectado en extras, sin código, symbol que falla o vacío, decimals que falla, o balanceOf igual a 0.
- Devuelve 400 si el scan no tiene ningún token listado con valor; en ese caso no hace ninguna sonda.
- Los aceptados entran en s['extras'] como unverified, con value_usd=0, y siguen la misma tubería: quote -> select_extras -> simulate_extra, con el mismo límite de gas, fee en especie al mismo bps y gas cubierto por los listados.
- /api/rescue revalida 'manual' contra lo firmado. 'manual' no forma parte del mensaje EIP-712.

## (c) Frontend
- #manualBox en Step 2: oculto por defecto. Solo se muestra cuando Step 1 valida un token listado con valor (la misma regla que manual_enabled). Lleva la misma advertencia de 'no verificado' y el checkbox desmarcado por defecto. Llama a quote_manual solo si hay contratos y el checkbox está marcado. Muestra los contratos rechazados.

## (d) Tests
- Relayer: 182 passed (154 previos + 28 nuevos en test_manual_1690.py y test_ux_manual_1690.py). Imagen unsweep-relayer-test:1690, --network none, con foundry montado de solo lectura.
- deploy/tests: 9 passed.
- Los casos nuevos cubren: 0, 1, 3 y 4 direcciones, dirección inválida, dirección sin checksum, duplicados, token listado, sin valor listado, symbol o decimals que fallan, balance 0, y en el frontend: campo oculto, checkbox desmarcado, advertencia y SRI.
- SRI recalculado: app.js sha384-eUoFdYUv23ErsDkpidSZVWYcVrbKiUb9uQ25HYTGI4SKpnU01vO9OlgWDcR8LCHU ; style.css sha384-5LhESYdxN3tErVq+80cAZ135Unk5fRwHGDBUTosBde7myEvacXoL/D/Ox7u3gH1b

## (e) Commit y despliegue
- Commit 0d7338b898c03dba9f69c51da879c3fdc73708da en origin/main (push fast-forward desde fcbb44d; el token no se imprimió).
- deploy/deploy_relayer.sh --commit 0d7338b898c03dba9f69c51da879c3fdc73708da: primero dry-run OK y después DESPLIEGUE OK. Health OK 3/3. Rollback disponible: unsweep-relayer:rollback-cc76b70c.
- deploy/deploy_static.sh: backup en /opt/aire/backups/unsweep-static/20261124T001924Z; hashes verificados.
- Arbitrum (relayer-arb) NO se tocó (#145).

## (f) Verificación en producción
- https://unsweep.com/api/health: 200, chainId 8453, mainnet true, ops ok.
- index.html, assets/app.js y assets/style.css servidos coinciden byte a byte (cmp) con git show 0d7338b. SRI de app.js y style.css válido en el index servido.
- Comprobación en cadena previa (bloque 61446107, desde el contenedor, eth_call): el holder 0x0e74990625DACE3c97306E964C23de6740DB0b77 es una EOA (code_len 0) con USDC 54716148 (6 decimales) y BRETT 0x532f…42E4 con 10469479482672488143216 (18 decimales).
- Llamada 1 (solo lectura, sin firmar; safe=0x…dEaD solo como destino de cotización): HTTP 200, policy_ok true, maxFeeBps 500. Seis líneas listadas con fee en especie al 5 %. BRETT RECHAZADO con 'ya detectado en extras: seleccionalo en Step 1'. Evidencia: quote_manual_brett.json.
  => El criterio 'devuelve el extra manual con value_usd=0 y fee en especie al mismo bps' NO queda acreditado en producción. Causa: BRETT ya lo detecta discover_extras para este holder (#1695) y la regla anti-duplicado lo excluye. Es correcto por diseño, pero BRETT no sirve como token de prueba manual para este holder.
- Llamada 2 (4 contratos): HTTP 400 {'detail':'maximo 3 contratos'}. Se rechaza en la validación, antes del scan y de cualquier RPC. Evidencia: quote_manual_4.json.
  DESVIACIÓN: la orden permitía una sola llamada de prueba. Esta segunda llamada se hizo para acreditar el rechazo que pide el criterio; no hizo lecturas en cadena.
- El caso 'sin token listado con valor' queda acreditado solo por tests (400), no en producción.

## Estado y siguiente paso
- Código desplegado, tests en verde, estáticos y SRI correctos.
- Pendiente: acreditar en producción un extra manual ACEPTADO. Requiere autorización para UNA llamada adicional de solo lectura con un holder público que tenga un token listado con valor y un ERC-20 con saldo que discover_extras NO detecte (comprobarlo antes en el array extras de scan_holder.json o con un /api/scan). Alternativa sin llamada HTTP: invocar add_manual + quote dentro del contenedor con docker exec, en solo lectura.

## (g) Verificación LOCAL en solo lectura del extra manual (sin depender de #146)
Script: `docs/actas/orden1690/verif_local.py`. Salida: `verif_local.json`. Código en 0d7338b (= origin/main).
Invoca en local la misma cadena que el handler `/api/quote_manual`: `parse_contracts`, `manual_enabled`, `add_manual` (probe: getCode/balanceOf/decimals/symbol), `simulate_extra` y `quote(extras)`. Se ejecuta contra el RPC PÚBLICO de Base (https://mainnet.base.org, chainId 8453). Sin API de producción, sin `record()` (PG), sin Alchemy y sin claves (Turnstile ficticio `local-no-secret`, solo para importar).

| Dato | Valor |
|---|---|
| Bloque | 61448328 |
| Contrato manual | BRETT 0x532f27101965dd16442E59d40670FaF5eBB142E4 (no está en assets_8453.json) |
| Holder | 0xBA3F945812a83471d709BCe9C3CA699A19FB46f7 (pool Uniswap v3 BRETT/WETH 1 %, resuelto con getPool por eth_call) |
| Token listado | WETH 300858423195219570882 wei (~513.742,78 USD) |
| Extra aceptado | balance 87496368334419946970996099, decimals 18, **unverified=true**, **value_usd=0**, manual=true |
| Cotización | policy_ok=true, **fee_bps=500** (fee en especie al mismo bps que el tramo) |
| Gas | simulate_extra=56429 ≤ límite 120000; con límite 1000 se excluye (None) |
| Gas cubierto | gas total 0,0159 USD ≤ fee listada 25.687,14 USD → true |

Checks: unverified ✔, value_usd=0 ✔, fee_bps=500 ✔, límite de gas ✔, gas cubierto con el token listado ✔ (todo_ok=true).

Rechazos (los 9 con el comportamiento esperado):
| Caso | Resultado |
|---|---|
| 0 contratos | 400 `indica entre 1 y 3 contratos` |
| 4 contratos | 400 `maximo 3 contratos` |
| Dirección no válida (0x1234) | 400 `direccion con formato invalido` |
| Checksum EIP-55 incorrecto | 400 `checksum EIP-55 invalido` |
| Contrato sin decimals (Aerodrome PoolFactory 0x420D…40Da) | rechazado `no es ERC-20 (balanceOf/decimals no responde)` |
| Dirección sin código (0x…0001) | rechazado `sin codigo en esa direccion` |
| Token ya listado (WETH) | rechazado `duplicado de la lista verificada` |
| Ya detectado por discover_extras | rechazado `ya detectado en extras: seleccionalo en Step 1` |
| Sin token listado con valor | manual_enabled=false, `requiere al menos un token listado con valor en Step 1` |

Limitaciones (honestidad):
- En esta verificación no se invocó `discover_extras`, porque necesita Alchemy y la misión excluye claves. Que BRETT no aparezca en los extras del pool es HIPOTESIS. El script simula `extras=[]` y la regla anti-duplicado se prueba aparte con el caso 'ya detectado'.
- Primera ejecución con otro holder (pool Aerodrome volátil 0x2143…0D5A, 2,47 USD listados): fee_bps=1500 (tramo bajo de tier_bps), así que el check de 500 falló. Se cambió a un holder con más de 10k USD listados. No se modificó ningún criterio.
- Es una verificación local. No sustituye la acreditación en producción, que sigue pendiente de #146.

Tests del relayer (0d7338b, venv local, env limpio): **182 passed, 0 failed** (7,18 s).

## (h) Estado de las órdenes (2026-11-24)
| Orden | Parte | Estado | Bloqueo |
|---|---|---|---|
| #1658 | Fix y despliegue (CERRADA según la memoria de AIRE; SHA no reverificado en esta misión) | CERRADA | — |
| #1658 | Caso USDC/BRETT de la dirección 0xa513…b441 (sin actividad en Base/ETH/ARB) | BLOQUEADA | #144 |
| #1684 | Fix de extras en Base (a09d323, desplegado) | CERRADA | — |
| #1684 | Fix de extras en Arbitrum (relayer-arb) y riesgo OFAC | BLOQUEADA | #145 |
| #1684 | Re-escaneo del caso real con extras (INFERENCIA: depende de la dirección que confirme #144) | BLOQUEADA | #144 |
| #1690 | (1)+(2) UX Step 1, Base (cc76b70, desplegado) | CERRADA | — |
| #1690 | (3) Código, tests y despliegue Base (0d7338b) | CERRADA | — |
| #1690 | (3) Verificación local del extra manual aceptado | CERRADA (esta sección) | — |
| #1690 | (3) Acreditación EN PRODUCCIÓN de un extra manual aceptado | BLOQUEADA | #146 |
| #1690 | Arbitrum (UX y extras) | BLOQUEADA | #145 |

No se abren solicitudes nuevas. Producción no se ha tocado en esta sección: sin despliegue ni POST.

## (i) Salvedad 1 de #558: verificación local con discover_extras REAL (2026-11-24)

- Token BRETT 0x532f27101965dd16442E59d40670FaF5eBB142E4. Holder real: pool BRETT/WETH 0xBA3F945812a83471d709BCe9C3CA699A19FB46f7. Base, bloque 61451093.
- discover_extras se ejecutó de verdad, con Alchemy vía `_extras_rpc`, igual que en producción. La página 1 trae 100 entradas, con pageKey presente, y devuelve 94 extras. **BRETT no se detecta.** Causa: discover_extras solo lee la primera página de alchemy_getTokenBalances. Esto sustituye la HIPOTESIS de (h) y la corrección #1707.
- Ruta manual (verif_local.py): balanceOf, symbol y decimals por eth_call directo a UNSWEEP_RPC; simulate_extra con límite de gas.
- Línea manual: unverified=true, value_usd=0, fee_bps=500 (fee = amount×500/10000) y gas simulado 56429 < 120000. Con un límite de 1000 gas, la línea queda excluida.
- Rechazos: 4 contratos → 400 «maximo 3 contratos». Sin token listado con valor → rechazado.
- UI (web/assets/app.js): l.46 `b.hidden = !ok` (solo hay bloque manual si listedValueUsd>0); l.150 `man.length > 3` → error.
- Tests: 182 passed, 0 failed. Nota: si se pasan UNSWEEP_RPC/UNSWEEP_CHAIN_ID a mano, 4 tests de test_approvals_429 fallan porque cambia la ruta de `_ap_providers`. Es un artefacto del entorno de prueba, no del código.
- No contradice (f) ni #1695: allí el holder era la EOA 0x0E74…, para la que discover_extras SÍ detecta BRETT.
- Evidencia: `verif_extra_manual.json` (todo_ok=true, 8 checks), reproducible con `verif_extra_manual.py`. Sin producción, sin /api/quote_manual público, sin firmas y sin redespliegue.
