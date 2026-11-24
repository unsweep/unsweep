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
| #1690 | (3) Verificación local de un extra manual ACEPTADO | PENDIENTE (reclasificada) | 8c50a8c `docs/actas/orden1690/acta_parte3.md` (g)-(h), `verif_local.py/.json`. Corrección (memoria #1707): verif_local.py construye extras=[] sin ejecutar discover_extras. No acredita que BRETT no se descubriera para ese pool/bloque, así que la fila «CERRADA» de (h) queda sustituida por esta tabla | ninguno (necesita repetir la verificación ejecutando discover_extras, en otra misión) |
| #1690 | (3) Acreditación en producción de un extra manual aceptado | PENDIENTE | `docs/actas/orden1690/acta_parte3.md` (f), `quote_manual_brett.json`, `quote_manual_4.json` | #146 |
| #1690 | Arbitrum (UX y extras) | PENDIENTE | `docs/actas/orden1690/acta_parte3.md` (h) | #145 |

Resumen: 19 partes; 12 HECHO y 7 PENDIENTE. Bloqueos: #144 (2), #145 (2) y #146 (1). Pendientes sin bloqueo humano: #1658 (1c) y la verificación local de #1690 (3). Nota: la verificación de #1638 en navegador figura como NO_DISPONIBLE, porque la auditoría fue estática sobre los bytes servidos; no es una parte de la orden.

Siguiente paso por orden, condicionado al humano:
- #1638: ninguno. Queda cerrada.
- #1658: con la respuesta a #144, re-escanear la dirección y la red confirmadas. (1c) requiere su propia orden.
- #1684: con #145=A, preparar la lista OFAC y desplegar el fix en relayer-arb. Con #144, re-escanear el caso.
- #1690: con #146=A, una lectura en producción de /api/quote_manual. Rehacer la verificación local ejecutando discover_extras. Arbitrum, según #145.
