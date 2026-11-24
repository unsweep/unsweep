# Estado de las órdenes UNSWEEP abiertas: #1638, #1658, #1684 y #1690

Cierre documental (2026-11-24). Alcance: solo UNSWEEP (#1646), paso de cierre según #557.
Es un cambio solo de documentación: sin despliegue y sin tocar código, SRI ni estáticos. No se repitieron pruebas ni se abrieron solicitudes nuevas.
Base: memoria #1698 (y #1683, #1685-#1687, #1691, #1694, #1701-#1702, #1706-#1707) y `git log origin/main` (punta previa 8c50a8c).

Leyenda. HECHO = evidencia verificable (SHA en origin/main y ruta del acta). PENDIENTE = no acreditado. Bloqueo = solicitud abierta al humano (#144, #145 o #146) o «ninguno».

| Orden | Parte | Estado | Evidencia (SHA y ruta) | Bloqueo |
|---|---|---|---|---|
| #1638 | 1. #pkConfirm bajo #btnRescue con el texto exacto | HECHO | 96059b9, dbc2d66, ecded4e, 4eb816a; `docs/actas/orden1658_cierre.md` (paso 3, fila 1; index.html L77-78 servido = main) | ninguno |
| #1638 | 2. #btnRescue deshabilitado hasta marcar la casilla | HECHO | dbc2d66, ecded4e; `docs/actas/orden1658_cierre.md` (paso 3, fila 2; app.js L176/L203) | ninguno |
| #1638 | 3. #step4 con progreso y resultado | HECHO | ecded4e; `docs/actas/orden1658_cierre.md` (paso 3, fila 3; index.html L85-99) | ninguno |
| #1638 | 4. goStep 1..4 | HECHO | ecded4e; `docs/actas/orden1658_cierre.md` (paso 3, fila 4; app.js L259-268) | ninguno |
| #1638 | 5. SRI correcto | HECHO | 4eb816a (SRI style.css); `docs/actas/orden1658_cierre.md` (paso 3, fila 5; sha384 calculado = declarado). Bitácora: 10de389 `docs/BITACORA.md` | ninguno (Turnstile sin SRI queda fuera de alcance y depende de #141) |
| #1658 | (1a) Fix de tokens=[] en /api/scan (paginación del índice y reintento de balanceOf) | HECHO | d63d7c2 (desplegado; ancestro de 4eb816a); `docs/actas/orden1658_cierre.md` §1.2-1.3 | ninguno |
| #1658 | (1b) Caso USDC/BRETT de 0xa513…b441: balanceOf=0 en Base/ETH/ARB | PENDIENTE | `docs/actas/orden1658_cierre.md` §1.4 (scan en el bloque 61391516; reconfirmado en 61408945) | #144 |
| #1658 | (1c) Residual: completitud en carteras con más de ~1000 tokens (PASS 2/5) | PENDIENTE | `docs/actas/orden1658_cierre.md` (nota de alcance; ESTIMACION 6-10 h) | ninguno (no bloquea el cierre de (1); requiere su propia orden) |
| #1658 | (2) #pkConfirm: UX y despliegue | HECHO | 4eb816a; `docs/actas/orden1658_cierre.md` §2 (deploy_static, BYTE_MATCH) | ninguno |
| #1684 | 1. Causa raíz (w3 = RPC público, sin métodos alchemy_*) | HECHO | 39b62a4 `docs/actas/orden1684_extras.md` §1 | ninguno |
| #1684 | 2. Fix de extras en Base (cliente Alchemy por CHAIN_ID) | HECHO | a09d323 (desplegado); `docs/actas/orden1684_extras.md` §2-§4 | ninguno |
| #1684 | 3. Evidencias (scan Base, BRETT balanceRaw = balanceOf en el bloque 61434788) | HECHO | 522f9eb `docs/actas/orden1684_extras.md` (evidencias, pasos 1-4) | ninguno |
| #1684 | 4. Arbitrum (relayer-arb sin Alchemy) y riesgo de la lista OFAC | PENDIENTE | `docs/actas/orden1684_extras.md` §5 | #145 |
| #1684 | 5. Re-escaneo del caso real con extras | PENDIENTE | depende de la dirección confirmada (INFERENCIA) | #144 |
| #1690 | (1)+(2) UX de Step 1 en Base: extras en el recuadro y aviso de soporte | HECHO | cc76b70 (desplegado), acta fcbb44d `docs/actas/orden1690_parte1-2.md` (+ capturas a 375/1280 px) | ninguno |
| #1690 | (3) Código, tests (182 passed) y despliegue en Base de /api/quote_manual | HECHO | 0d7338b; `docs/actas/orden1690/acta_parte3.md` (a)-(f) | ninguno |
| #1690 | (3) Verificación local de un extra manual ACEPTADO | HECHO (local) | 0aa69e1 `docs/actas/orden1690/acta_parte3.md` (i), `verif_extra_manual.json/.py`: discover_extras real no detecta BRETT en el pool 0xBA3F… (bloque 61451093); unverified=true, value_usd=0, fee_bps=500, gas 56429<120000; 4.º contrato → 400; tests 182 passed | ninguno |
| #1690 | (3) Acreditación en producción de un extra manual aceptado | PENDIENTE | `docs/actas/orden1690/acta_parte3.md` (f), `quote_manual_brett.json`, `quote_manual_4.json` | #146 |
| #1690 | Arbitrum (UX y extras) | PENDIENTE | `docs/actas/orden1690/acta_parte3.md` (h) | #145 |

Resumen: 19 partes; 13 HECHO y 6 PENDIENTE. Bloqueos: #144 (2), #145 (2) y #146 (1). Pendiente sin bloqueo humano: #1658 (1c). Nota: la verificación de #1638 en navegador figura como NO_DISPONIBLE, porque la auditoría fue estática sobre los bytes servidos; no es una parte de la orden.

Siguiente paso por orden, condicionado al humano:
- #1638: ninguno. Queda cerrada.
- #1658: con la respuesta a #144, re-escanear la dirección y la red confirmadas. (1c) requiere su propia orden.
- #1684: con #145=A, preparar la lista OFAC y desplegar el fix en relayer-arb. Con #144, re-escanear el caso.
- #1690: con #146=A, una lectura en producción de /api/quote_manual. Arbitrum, según #145.

---

## Acta de traspaso: despliegue de 6f6fa05 en Base y estado final (#1646, 2026-11-24)

### 1. Despliegue en Base del fix de paginación pageKey (6f6fa05)
- Commit desplegado: `6f6fa05f488fd703718c19942043a8920ee344f8`, verificado en un worktree limpio desde origin/main.
- Revisión del código (`relayer/extras.py`):
  - Topes: `MAX_PAGES = 5` (L25), `MAX_TOKENS_SCANNED = 500` (L26) y corte por tiempo `now() - t0 >= time_budget`.
  - Fail-soft: `except Exception` corta el bucle o devuelve None, nunca lanza la excepción.
  - Los extras se valoran con `value_usd=0`.
  - La fee de los extras se cobra en especie (`bal*bps//10000`) con el mismo bps.
- Tests: **189 passed** (6.70 s) en el worktree.
- Despliegue con `deploy/deploy_relayer.sh --commit 6f6fa05f…`:
  - Resultado: `DESPLIEGUE OK`. Rollback disponible en `unsweep-relayer:rollback-0d7338b8`. Imagen `sha256:400a0550…`.
  - Hubo un 502 transitorio durante el arranque; después, health 3/3 en 200.
  - Secretos prohibidos dentro del contenedor: ninguno.
- Verificación posterior:
  - `/api/health`: 200 ×3 (`chainId 8453`, `mainnet true`, `ops ok`).
  - `index.html`, `/assets/app.js`, `/assets/ethers.min.js` y `/assets/style.css` son idénticos byte a byte a la línea base previa.
  - Los 3 `integrity` sha384 coinciden con la línea base.
- SHA servido:
  - Las etiquetas de la imagen no incluyen el commit.
  - El sha256 de `/app/relayer/extras.py` en el contenedor coincide con el del worktree 6f6fa05 (`b459d39e…`).
- Arbitrum: `unsweep-relayer-arb` no se tocó (llevaba 42 h en marcha) y sigue dependiendo de #145.

### 2. Estado final de las 19 partes
La tabla anterior sigue vigente: **13 HECHO y 6 PENDIENTE**. Esto corrige la memoria #1709, que registraba 12/7.

#1658 (1c) sigue **PENDIENTE**. 6f6fa05 pagina con topes (5 páginas, 500 tokens y tiempo), lo que hace la consulta acotada y fail-soft. Aun así, no garantiza completitud en carteras con cientos o miles de tokens basura.

### 3. Dependencias de #141 a #146
| Solicitud | Afecta a | Efecto |
|---|---|---|
| #141 | #1638 parte 5 (Turnstile sin SRI) | No reabre ninguna parte; solo cierra un hallazgo de auditoría |
| #142 | Transversal (medición del ingreso de UNSWEEP) | Ninguna parte; condiciona la contabilidad |
| #143 | Transversal (origen de los rescates de 5,0 y 4,0 USDC) | No cuentan como ingreso ni como validación hasta aclararlo |
| #144 | #1658 (1b) y #1684 (5) | Re-escaneo de la dirección y red confirmadas |
| #145 | #1684 (4) y #1690 Arbitrum | Lista OFAC de relayer-arb y despliegue de 6f6fa05 en Arbitrum |
| #146 | #1690 (3), acreditación en producción | Una lectura más de /api/quote_manual |

### 4. Propuesta: consulta dirigida para carteras con cientos de tokens basura (#1658 1c)
Es una HIPOTESIS de diseño. Requiere su propia orden. ESTIMACION: 6-10 h, tomada de `orden1658_cierre.md`.

1. **Lista prioritaria primero.** Reunir:
   - los tokens del índice listado;
   - los extras manuales (máx. 3, vía /api/quote_manual);
   - una lista curada de tokens líquidos por cadena.

   Leer sus saldos con `balanceOf` en lote mediante Multicall3 (`0xcA11bde05977b3631167028862bE2a173976CA11`), en una o pocas `eth_call`. El coste depende del tamaño de la lista, no de la basura.
2. **Descubrimiento por transferencias entrantes.** Usar `alchemy_getAssetTransfers` (`toAddress`=víctima, `category` erc20, deduplicado por contrato) o `eth_getLogs` de Transfer con `topic2`=víctima en ventanas de bloques. El resultado es el conjunto de contratos que alguna vez enviaron tokens a la cartera.
3. **Filtro de basura antes de leer saldos.** Descartar contratos sin pool líquido (comprobación con quoter en cadena) o que estén en la lista de spam. Solo los que pasen se leen con Multicall3.
4. **Barrido general al final.** pageKey con los topes actuales de 6f6fa05.
5. **Transparencia.** Devolver `truncated=true` cuando salte cualquier tope y mostrar en la UI que el resultado es parcial.

Se mantienen `value_usd=0` y la fee en especie en los extras.

### 5. Siguiente paso
Sin trabajo técnico pendiente que no dependa del humano, salvo #1658 (1c), que necesita una orden nueva.
