# Expediente de auditoría: ORDEN #1658 (UNSWEEP)

Redactado: 2026-11-23 ~22:30 UTC por el Ejecutor (Claude). Solo lectura: 0 tx, 0 despliegues, 0 contactos externos.
Raíz de artefactos: `/opt/aire/workspace/projects/unsweep/artifacts/` (abreviado `A/`).

## Veredictos

| Parte | Asunto | Veredicto |
|---|---|---|
| (1) | tokens=[] en /api/scan | **PENDIENTE DE #144** |
| (2) | #pkConfirm (UX y despliegue 4eb816af) | **CERRADA** |

Nota de alcance para la parte (1). El veredicto de la orden se refiere a la dirección del caso. El defecto de completitud en carteras grandes (PASS 2/5) es un hallazgo residual aparte, con propuesta en `A/orden1658/ESTADO_AUDITORIA_1658.md`, sección "Defecto residual (b)", estimada en 6-10 h (ESTIMACION). No bloquea el cierre de la parte (1), pero sí bloquea la afirmación "el escaneo es completo" en direcciones con más de unos 1000 tokens.

---

## Parte (1): tokens=[] en /api/scan

### 1.1 Diagnóstico (#547)

**HECHO** (memoria #1667; `A/orden1658b/compare.json`). En producción con el commit 4eb816a, entre los bloques ~61393257 y 61393400, se probaron 4 direcciones de muestra (0x18b0…9e, 0x0e74…77, 0x4446…ef y 0x8e92…17). Todas dieron:
- HTTP 200 y status=incomplete;
- `tokens` con 15 entradas y `tokensTotalNonZero` entre 70 y 95;
- USDC, BRETT y DEGEN ausentes de `tokens[]`, aunque tienen saldo ≠0 en cadena (`A/orden1658b/onchain_samples.json`, memoria #1666).

**HECHO** (`A/orden1658b/local_live.txt`). Ejecutado en local con la lógica corregida, las mismas direcciones devuelven 3927, 116, 3391 y 1331 tokens, con USDC, BRETT y DEGEN presentes. Causa: la enumeración del índice en `relayer/svc_mainnet.py` (memoria #1667, L171-208) no paginaba y descartaba tokens.

**HIPOTESIS.** No dispongo del texto literal de #547. La correspondencia "diagnóstico #547 = esta causa" se infiere del mensaje del commit d63d7c23 ("tests de regresion #547") y del fichero `relayer/test_scan_regresion_547.py`.

### 1.2 Despliegue d63d7c23 (#548)

**HECHO** (`git show -s d63d7c23`):
- SHA completo `d63d7c23c20de76f3ed595ba9f9a8bdba22786b2`, fecha 2026-11-23 21:37:10 +0000.
- Mensaje: "scan(mainnet): #1658c paginacion de indice, balanceOf con reintento en RPC alternativo, unknown/retry, presupuesto 14s con partial=true; tests de regresion #547".
- Ficheros: `relayer/svc_mainnet.py` (+140/−18 aprox.), `test_scan_paginacion_1658b.py`, `test_scan_regresion_1658.py` y `test_scan_regresion_547.py`. Total: 4 ficheros, 343 inserciones y 18 borrados.

**HECHO**:
- `git rev-parse origin/main` da d63d7c23c20d…; `A/orden1658/ESTADO_AUDITORIA_1658.md:14` confirma que es el HEAD desplegado.
- 4eb816af es ancestro de d63d7c23 (`git merge-base --is-ancestor`, rc=0).

### 1.3 Cinco verificaciones en producción (#549)

**HECHO** (`A/orden1658c/run3.log`, `A/orden1658c/verify_prod.json`, `A/orden1658c/INFORME_ORDEN1658_parte1.md`). balanceOf se leyó en el mismo bloque que devolvió /api/scan.

| Dirección | HTTP | Latencia | Bloque | status/partial | tokens[] | Faltan | Unknown | Resultado |
|---|---|---|---|---|---|---|---|---|
| 0x18b0f454… | 200 | 13,22 s | 61401204 | incomplete/true | 92 | 3835 (BRETT y DEGEN entre ellos) | 0 | DISCREPA |
| 0x0e749906… | 200 | 3,04 s | 61404156 | incomplete/true | 116 | 0 | 0 | No concluyente (5 balanceOf del verificador fallaron) |
| 0x4446adc0… | 200 | 13,15 s | 61404818 | incomplete/true | 3152 | 239 | 2776 | DISCREPA |
| 0x8e92d282… | 200 | 13,08 s | 61407516 | incomplete/true | 1331 | 0 | 952 | PASS |
| 0xa51389a2… | 200 | 0,47 s | 61408945 | complete/false | 0 | 0 | 0 | PASS |

Totales:
- PASS 2/5; mismatch=0 y zero_returned=0 en las 5.
- n429=26 (del verificador) y rpc_errors=5.
- Las 5 respuestas por debajo de BUDGET_S=14 s.

**HIPOTESIS.** Que estas 5 sean "las 5 verificaciones de #549" no consta literalmente en memoria (`ESTADO_AUDITORIA_1658.md:48`).

### 1.4 Resultado vacío de 0xa51389a213ba84bf99591b8b6482c41b2381b441

**HECHO.** /api/scan devolvió `status complete`, `tokens []` y `nz 0` en el **bloque 61391516**, cached=False (`A/orden1658/verify_after.log:12`; también `A/orden1658/scan_after_post_chain.json` y `A/orden1658b/scan_0xa51389a2.json`).

**HECHO.** balanceOf de USDC=0 y BRETT=0, medido con dos proveedores independientes en los bloques inmediatos:
- `verify_after.log`: Alchemy 61391518 y Chainstack 61391519.
- `deploy_static.log`: ambos en 61391849.

**PRECISIÓN (HECHO).** `A/orden1658b/compare.json` registra el scan en el bloque 61391516 con USDC, BRETT y DEGEN onchain="0", pero no anota el bloque de lectura (`balance_block=None`). La afirmación "balanceOf=0 en el bloque 61391516" queda probada con una tolerancia de +2 bloques. El historial de la dirección hace imposible un cambio en ese intervalo:
- nonce 0 y ETH 0;
- 0 transfers entrantes y 0 salientes (`alchemy_getAssetTransfers`);
- USDC y BRETT = 0 en −1 d, −7 d y −30 d (`A/orden1658/onchain_history.txt`).

**HECHO.** Reconfirmado en el bloque 61408945, ya en el mismo bloque que el scan: USDC=0, BRETT=0 y DEGEN=0 (`run3.log`). También da 0 en Ethereum (chainId 1) y Arbitrum (42161) (`A/orden1658/onchain_otherchains.txt`).

**Conclusión (HECHO).** La respuesta vacía es CORRECTA para esa dirección en Base: no es un falso negativo.

**HIPOTESIS.** La dirección o la red del caso podrían estar mal transcritas o no ser Base. Por eso el veredicto es **PENDIENTE DE #144**: el humano debe confirmar la dirección exacta y la red. No se duplica la solicitud.

---

## Parte (2): #pkConfirm

**HECHO** (`A/orden1658/ESTADO_AUDITORIA_1658.md:19`). Commit 4eb816af550ba644691377dc787f1809a4ba113e: "fix(#1658): #pkConfirm alineado (selector especifico, checkbox sin width:100%), SRI de style.css, test regresion scan …".

**HECHO** (`A/orden1658/deploy_static.log`). Desplegado con `deploy_static.sh`; backup en `/opt/aire/backups/unsweep-static/20261123T211904Z`. Después del despliegue:
- index.html BYTE_MATCH 4d3b516b…;
- style.css BYTE_MATCH 9930b0b2…;
- app.js BYTE_MATCH 342e934c…;
- health 200.

(El DIFF de `verify_after.log` a las 21:17:58Z es anterior a ese despliegue, de las 21:19:04Z.)

**HECHO** (`A/orden1658/ux/{before,after}_{375,1280}.txt`). Comparación antes y después:

| Medida | Antes, 375 px | Después, 375 px | Antes, 1280 px | Después, 1280 px |
|---|---|---|---|---|
| Ancho del checkbox | 325px | 13px | 554px | 13px |
| label display | block | flex (gap 8px) | block | flex (gap 8px) |
| cbInlineWithText | false | **true** | false | **true** |
| cbLeft / labelLeft | 29/25 | 25/25 | 367/363 | 363/363 |

**Invariantes (HECHO).** En las 4 capturas se cumplen todos:
- `pkBelowBtn=true`;
- `btnDisabledInitially=true`;
- `btnEnabledAfterCheck=true`;
- `rescueNotFired=true`.

Es decir, marcar la casilla no lanza el rescate.

**Veredicto: CERRADA.** La verificación contra producción en el momento actual se recoge en la sección 3.

---

## 3. Diff de solo lectura entre producción y main (#1638)
_Pendiente de completar en esta misma misión._

## 4. Timer unsweep-funnel (#1646)
_Pendiente de completar en esta misma misión._

## Paso 3: diff de solo lectura entre producción y main frente a la ORDEN #1638

Comando (2026-11-23 ~22:27Z): `curl -sS` de https://unsweep.com/ y de /assets/{style.css,app.js,ethers.min.js}, comparado con `git show origin/main:web/...`. Copias guardadas en `unsweep-audit/prod_snapshot/{prod,main}/`.

- HECHO: index.html http=200, 17632 B, sha256 4d3b516bdf6c0d3f… en prod y en main.
- HECHO: style.css 200/4766 B (9930b0b2c6ea190d…), app.js 200/18856 B (342e934ca60d4c94…) y ethers.min.js 200/394697 B (49befe7aed7827d5…) coinciden en sha256 entre prod y main.
- HECHO: `diff -q` da IDENTICO en los 4 ficheros. Producción = main en el front estático.

| # | Punto de la #1638 | Estado | Evidencia (fichero servido) |
|---|---|---|---|
| 1 | #pkConfirm bajo #btnRescue con texto exacto | **PRESENTE** | index.html L77 `<button id="btnRescue" ...>`; L78 `#pkConfirmRow` con `<input type="checkbox" id="pkConfirm" required> I confirm this is ONLY the compromised wallet key (not safe wallet or seed phrase) and signing happens locally here.`, idéntico al literal de la #1638 (memoria #1638) |
| 2 | #btnRescue deshabilitado hasta marcar la casilla | **PRESENTE** | index.html L77 atributo `disabled`; app.js L176 `sync = function(){ b.disabled = !c.checked; }; c.addEventListener('change', sync); sync();` (el change solo sincroniza, no dispara el rescate); L203 guarda `if (pkConf && !pkConf.checked) return ...` |
| 3 | #step4 con progreso y resultado | **PRESENTE** | index.html L85-99: `section#step4` aria-live, `ol#step4Phases` (phSign/phSend/phConfirm), `#step4Out` role=status, `#step4Result` (resStatus, resTx, resLink Basescan); app.js L181, L195-197 y L208 |
| 4 | goStep 1..4 | **PRESENTE** | app.js L259 `const MAX_STEP = 4;`; L262 `RangeError` fuera de 1..4; L263-268 bucle sobre step1..4; L208 `goStep(4)`; L45/281/285/287-289 goStep(1..3) |
| 5 | SRI correcto | **PRESENTE** | Cálculo `openssl dgst -sha384 -binary \| base64` frente a lo declarado en index.html: style.css L1 `sha384-yjdYVjnd…Fu4y` = calculado; app.js L155 `sha384-nO7yAD6D…IwRm` = calculado; ethers.min.js L154 `sha384-KFwRTLOj…CXfv` = calculado |

- Veredicto del paso 3: **0 pendientes de la #1638 en producción.** Alcance de la siguiente misión para la #1638: vacío.
- NO_DISPONIBLE (en esta misión): verificación en tiempo de ejecución en navegador. La auditoría es estática sobre los bytes servidos; las capturas de 375 y 1280 px de la parte (2) son la evidencia de render previa.
- Fuera de alcance: Turnstile sin SRI, pendiente de la solicitud #141 (no se duplica).
