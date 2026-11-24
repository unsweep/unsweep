# UNSWEEP: evidencia técnica de seguridad (orden #1869)

> **No es una auditoría profesional.** Es un análisis automatizado más una revisión de código en lectura hecha por un agente de IA en una sola sesión acotada. Puede tener errores y omisiones.

Fecha: 2026-11-24 (UTC).

## 1. Commit

- `git rev-parse HEAD` = **`549205a0da8e4342021016a49f96693bd6a9db80`**
- Cambios sin confirmar ya existentes y ajenos a esta orden: 3 guías en `web/guides/*` (conservadas por la decisión humana #152) y varios `??` previos (actas, métricas, artefactos).
- `git status --short -- src relayer web/assets web/index.html foundry.toml` sale vacío: sin cambios en contratos, relayer ni frontend.
- Esta orden solo añade `LICENSE`, este documento y `docs/security/`.

## 2. Entorno y versiones

| Herramienta | Versión | Instalación |
|---|---|---|
| forge | 1.10.0 (commit 083e22994195d6a7e3ad3104d0b57f478c9b9062, build 2026-11-19) | ya presente en ~/.foundry/bin |
| solc | 0.8.39+commit.ce47f2c8.Linux.g++ | solc-select 1.2.0, venv aislado |
| slither | 0.11.6 (crytic-compile 0.4.2) | venv /opt/aire/tools/venv-slither |
| aderyn | **NO_DISPONIBLE** | ver 4.3 |
| Python | 3.12.3 | sistema |

`foundry.toml`: solc 0.8.39, evm prague, optimizer 200, via_ir. Pragma `^0.8.24`. Versiones crudas en `docs/security/versions.txt`.

## 3. Comandos

```bash
cd /opt/aire/workspace/projects/unsweep
python3 -m venv /opt/aire/tools/venv-slither
/opt/aire/tools/venv-slither/bin/pip install slither-analyzer solc-select
solc-select install 0.8.39 && solc-select use 0.8.39
forge build    > docs/security/forge-build.txt
forge test -vv > docs/security/forge-test.txt
slither . --filter-paths "lib/|node_modules/|test/|script/" > docs/security/slither.txt
slither . > docs/security/slither-full.txt
slither . --filter-paths "lib/|node_modules/|test/|script/" --json docs/security/slither.json
npm install --prefix /opt/aire/tools/aderyn @cyfrin/aderyn          # fallo 404
curl -fsSL -o cyfrinup_install.sh https://raw.githubusercontent.com/Cyfrin/aderyn/dev/cyfrinup/install  # revisado, NO ejecutado
# eth_getCode por RPC publico https://mainnet.base.org (solo lectura) de 0x38bc... y 0x56a3...
```

## 4. Resultados por herramienta

### 4.1 Foundry

- `forge build`: exit 0. El lint emite 27 avisos: calls-loop 12, require-revert-in-loop 8, reentrancy-events 2, uninitialized-local 2, block-timestamp 1, environment-read-across-mutation 1, missing-events-access-control 1.
- `forge test -vv`: **36 tests pasan, 0 fallan y 0 se omiten, en 4 suites** (6 + 5 + 12 + 13).

### 4.2 Slither

- Con filtros: 10 contratos, 102 detectores, **25 resultados**. Sin filtros: 34 (los 9 adicionales están en dependencias, tests o scripts).
- Todos los resultados filtrados están en `src/UnsweepDelegate.sol`:

| Impacto | Detector | N.º | Línea | Valoración |
|---|---|---|---|---|
| High | reentrancy-balance | 1 | 134 | **Falso positivo justificado.** Hay un lock transitorio tload/tstore (:135-139, se libera en :160). Los balanceOf antes y después (:210-219) son intencionados: miden lo transferido realmente y solo sirven para acotar la comisión (:223). |
| Medium | incorrect-equality | 1 | 195 (`bal == 0`, :203) | Falso positivo: solo omite saldos a cero. |
| Medium | locked-ether | 1 | 21 / receive :91 | **Real, severidad baja.** Con 7702 la EOA mueve su ETH con su propia clave, pero el ETH enviado a la dirección de la implementación se queda bloqueado. |
| Medium | uninitialized-local | 2 | 208, 214 | Falso positivo: en Solidity el valor por defecto es 0, que aquí es el correcto. |
| Low | calls-loop | 12 | 163, 195, 229 | Por diseño. Un token que revierte solo bloquea ese rescate concreto (DoS autoinfligido). |
| Low | reentrancy-events | 2 | 134 | Informativo: los eventos se emiten con el lock activo. |
| Low | timestamp | 1 | 141 | Aceptable: es el `deadline`. |
| Info | assembly 2, cyclomatic-complexity 2, low-level-calls 1 | 5 | — | Informativo. |

Totales: **High 1 (FP), Medium 4 (3 FP + 1 real de severidad Low), Low 14, Informational 6.**

### 4.3 Aderyn: NO_DISPONIBLE

- Intento 1: `404 Not Found - GET https://registry.npmjs.org/@cyfrin%2faderyn - Not found`.
- Intento 2: el instalador oficial dice textualmente: "Aderyn has been retired and is no longer maintained. This legacy installer no longer installs or updates software." y termina con exit 1.
- No se usaron binarios no oficiales. Detalle en `docs/security/aderyn-report.md`.

### 4.4 Contrato desplegado (Base mainnet)

- Delegate `0x38bcF425bC4d13624734e09376F2fafc799fA8c8`: el bytecode (6059 bytes) **coincide** con UnsweepDelegate del HEAD, con las immutables enmascaradas.
- Config `0x56a345661e3999F2b20f1E069aAC14097Fa0D118`: el bytecode (881 bytes) **coincide** con UnsweepConfig. La immutable `config` del Delegate apunta aquí.
- Leído con eth_call: owner = feeRecipient = 0x7e26916f1ff93fcf6ccd7eaaa0561007783fda1b, feeBps = 1500 (15 %), pendingOwner = 0.
- Basescan: https://basescan.org/address/0x38bcF425bC4d13624734e09376F2fafc799fA8c8#code. **No he comprobado en esta ejecución que el código fuente esté verificado en Basescan.** La equivalencia con el repo se demostró solo comparando el bytecode.

## 5. Revisión manual

### 5.1 Contratos

| ID | Sev. | Clase | Hallazgo |
|---|---|---|---|
| C-1 | Medium | HECHO `src/UnsweepDelegate.sol:204-207,223` | `minFees[j]` **no está acotado por MAX_FEE_BPS** (:25). Solo se limita a `bal` (:207) y el control de :223 lo excluye (`fGot > minFee`). Una minFee alta firmada puede llevarse hasta el 100 % de un token. La víctima la firma, pero sobre lo que cotiza el relayer. HIPOTESIS no verificada: que la UI la muestre o la limite. |
| C-2 | Low | HECHO `:21,:91` | locked-ether en la implementación. |
| C-3 | Info (+) | HECHO `:112-152` | EIP-712 con chainId y verifyingContract = EOA (:114). Rechaza s alta (:150), exige que el firmante sea la propia EOA (:152), nonce de bitmap (:144-148) y deadline (:141). |
| C-4 | Info (+) | HECHO `:170-186` | Las llamadas solo van a un claimTarget autorizado, con value 0 y nunca a tokens o NFTs de la cesta. Después comprueba que no se ha movido ningún NFT ni ha bajado ningún saldo. En mainnet la lista de claimTarget está vacía (`docs/UNSWEEP_ALCANCE.md:13`). |
| C-5 | Info | HECHO (lint) | missing-events-access-control: no he identificado qué función de Config lo provoca. |

### 5.2 Frontend (web/)

| ID | Sev. | Clase | Hallazgo |
|---|---|---|---|
| W-1 | Info (+) | HECHO `web/assets/app.js:245,254,265-266` | La clave se usa solo en el navegador para firmar y se descarta en :266. |
| W-2 | Info (+) | HECHO `web/assets/app.js:267-269` | El POST a /api/rescue envía firmas y datos públicos, **sin la clave**. |
| W-3 | Info (+) | HECHO `web/assets/app.js:251-253` | Se niega a firmar si el delegate no es el esperado. |
| W-4 | Info (+) | HECHO | Los 3 SRI sha384 de `web/index.html` coinciden con los archivos (recalculados). |
| W-5 | Info (+) | HECHO `x402-netcheck/Caddyfile:187` (fuera del repo) | La CSP incluye `connect-src 'self'`, `frame-ancestors 'none'` y `object-src 'none'`, y en script-src solo `'self'` y challenges.cloudflare.com. |
| W-6 | Low | HECHO `web/assets/app.js:191` | Turnstile se carga sin SRI en el mismo documento en el que se introduce la clave. Lo mitiga la CSP. Ya está abierto como decisión humana #141. |
| W-7 | — | NO VERIFICADO `app.js:201-207` | No he confirmado que `readKey` limpie el campo del DOM (la salida se recortó). |

### 5.3 Relayer (relayer/)

Secretos citados **solo por nombre**: `OPS_PK` (`relayer/service.py:28`) y `TURNSTILE_SECRET` (`relayer/svc_core.py:26`). No he abierto ningún .env.

| ID | Sev. | Clase | Hallazgo |
|---|---|---|---|
| R-1 | Info (+) | HECHO `relayer/service.py:88-102` | build_auth comprueba chainId (:93) y el delegate esperado (:95) antes de recuperar la autoridad (:97-99). |
| R-2 | Info (+) | HECHO `relayer/service.py:189-268` | Controles en /api/rescue: rate limit (:191), Turnstile (:193), OPS_PK presente (:196), allowlist (:203), tope de extras (:204, EX_MAX = 20 en :57), screen OFAC/ScamSniffer/GoPlus (:209) y maxFeeBps firmado ≤ cotizado (:232). Errores genéricos (:265-268). |
| R-3 | Info (+) | HECHO `relayer/service.py:41-44`, `relayer/Dockerfile:7` | La IP sale de client.host con `--forwarded-allow-ips 172.18.0.0/16`, así que XFF no se puede falsificar desde fuera. |
| R-4 | Low | HECHO `relayer/svc_core.py:97-99` | GoPlus es **fail-open**: si falla, se acepta sin marca. |
| R-5 | Medium (si se confirma) | HIPOTESIS | El relayer valida maxFeeBps (HECHO, `relayer/service.py:232`), pero no he verificado que acote `minFees` con MAX_FEE_BPS. Si no lo hace, C-1 sería explotable por un relayer comprometido o con errores. |
| R-6 | — | NO VERIFICADO | Implementación de `rate_limited`, carga y frescura de la lista OFAC (`ofac_update.py`), límites de gas y fee en `relayer.py` y si `exceptionRef` (:241, lo envía el cliente) puede saltarse `check_cap`. |

## 6. Limitaciones

- No es una auditoría: sin fuzzing ni invariantes propios, sin verificación formal y con revisión manual parcial (R-6, W-7).
- Aderyn no está disponible porque el proyecto se ha retirado.
- El estado en cadena y los bytecodes son de 2026-11-24 y pueden cambiar.

## 7. Recuento de hallazgos manuales

HECHO: Medium 1 (C-1), Low 3 (C-2, W-6, R-4), Info 11 (C-3, C-4, C-5, W-1 a W-5, R-1 a R-3; 10 de ellas son controles positivos y C-5 es neutro). HIPOTESIS: Medium 1 (R-5, misma causa raíz que C-1). NO VERIFICADO: 2 bloques (W-7, R-6). Critical/High manuales: 0.

Artefactos crudos en `docs/security/`: versions.txt, forge-build.txt, forge-test.txt, slither.txt, slither-full.txt, slither.json, aderyn-report.md.

## 8. Verificación adicional 2026-11-24 (orden #2137)

Base de la revisión: commit `218839ac328243c69c8c9253e2c11919cdd80b3f` (HEAD previo a esta sección). Todo en solo lectura. No se ha modificado ningún contrato ni el relayer.

### 8.1 W-7: limpieza del input de clave (`#pk`) en el DOM — PARCIAL

- HECHO `web/assets/app.js:203`: `el.value = ''; // the key never stays in the DOM`, dentro de `readKey()` (`app.js:201`), antes de validar el formato y antes de firmar.
- HECHO `web/assets/app.js:245`: `w = new E.Wallet(readKey());`. El input se vacía al intentar firmar, así que queda limpio en el camino de firma y en los errores posteriores: formato inválido o seed phrase (`app.js:204-205`) y fallo de `/api/rescue` en el `catch` (`app.js:287-289`, que además hace `w = null`).
- NO CUMPLE en las salidas anteriores a `readKey()`: los returns tempranos de `app.js:236`, `app.js:238` y `app.js:239` (faltan pasos 1-2, falta la confirmación o falta Turnstile) dejan la clave en el input.
- NO CUMPLE al cancelar o editar: `app.js:323-325` (`edit1`/`edit2`/`edit3` → `goStep(n)`) no vacía `#pk`, y no hay manejador de `pagehide`/`beforeunload`. Los únicos usos de `$('pk')` son `app.js:202` y `app.js:327` (toggle Show/Hide).
- OPINION (severidad Low): es la clave de una wallet ya comprometida y no sale del navegador, pero permanece en el DOM más tiempo del necesario. Mitigación sugerida, no aplicada en esta orden: vaciar `#pk` en los returns tempranos, en `goStep()` y en `pagehide`.

### 8.2 R-5: acotar `minFees` en el relayer — PARCIAL (se mantiene el riesgo de C-1)

- HECHO `relayer/eip712.py:44-45`: `maxFeeBps` acotado a `(0, MAX_FEE_BPS]` = `(0, 1500]`.
- HECHO `relayer/service.py:232-233`: se rechaza si el `maxFeeBps` firmado supera al cotizado.
- HECHO `relayer/policy.py:76-77`: en la cotización, la comisión total en USD no puede superar el 15 % de lo rescatado.
- HECHO `relayer/svc_scan.py:399-400`: el `minFee` cotizado se limita al saldo (`mn = min(bal, int(need_usd / px * 10**dec) + 1)`).
- NO CUMPLE: `relayer/eip712.py:46-47` solo valida la longitud de `minFees`. En el envío (`relayer/service.py:228-242`) no se comparan los valores de `minFees` firmados con los cotizados ni con un techo derivado de `MAX_FEE_BPS`.
- Contrato `src/UnsweepDelegate.sol:204-207`: `if (fee < minFee) fee = minFee; if (fee > bal) fee = bal;`. `minFee` solo queda acotado por el saldo, no por `MAX_FEE_BPS`.
- Conclusión: el techo del 15 % sobre `minFees` solo se aplica en la cotización. Una firma con `minFees` arbitrarios o un relayer con errores podría cobrar más del 15 %, hasta el saldo del token. Requiere la firma de la víctima, y la UI muestra la simulación antes de firmar. R-5 pasa de HIPOTESIS a HECHO, severidad Medium, misma causa raíz que C-1.

### 8.3 R-6: rate_limited, ofac_update.py y exceptionRef — CUMPLE

- HECHO `relayer/svc_core.py:130`: `def rate_limited(ip):`. HECHO `relayer/service.py:48-49`: `if rate_limited(_ip(req)): raise HTTPException(429, 'demasiadas peticiones')`.
- HECHO `relayer/ofac_update.py` existe (1761 bytes): descarga la lista SDN (`:11-12`), extrae direcciones `Digital Currency Address - ETH` (`:17-21`), no sobrescribe si hay menos de 50 (`:22-23`), guarda `publish_date` y `fetched_at` (`:24-26`) y escribe de forma atómica con `os.replace` (`:28-31`). NO_DISPONIBLE: programación periódica (cron/systemd) y frescura de la lista en producción.
- HECHO `relayer/service.py:241`: `exception_ref=str(b.get('exceptionRef', ''))[:64]`, que llega a `P.check_cap(...)` en `relayer/relayer.py:118`. HECHO `relayer/policy.py:111-119`: `check_cap` no usa `ref`; el límite `cap_usd(tr)` es duro, así que un `exceptionRef` enviado por el cliente no puede saltárselo.

### 8.4 Bytecode en Arbitrum One frente a `forge build` en HEAD — COINCIDE (con immutables enmascaradas)

- Direcciones tomadas del repo (`deployments/mainnet.txt`, `README.md`).
- RPC público de solo lectura `https://arb1.arbitrum.io/rpc`, `eth_chainId` = `0xa4b1` (42161), `eth_getCode` en el bloque 527221874 (`0x1f6cc472`). Foundry 1.10.0, `forge build` exit 0.
- Metodología igual que en Base (§4.4): sha256 y keccak256 del runtime completo y sin el sufijo CBOR, en bruto y con las posiciones de `immutableReferences` puestas a cero en el bytecode de la cadena.

| Contrato | Variante | sha256 | keccak256 |
|---|---|---|---|
| UnsweepDelegate `0x38bcF425bC4d13624734e09376F2fafc799fA8c8` | local completo (6059 B) | `13fc6573f70e1b0f27b46e6d405c297b19bfd8c7e330193cdd6639d192f18f63` | `032492147403d9d46954e04540f72c9133f762286341d6c85d83b45787ef8405` |
| | cadena en bruto | `20971ec7c28e7fd8e6e5959cfc03802d1b9f1bbd1413d84b3118dd8839841d68` | `9ad0a014d76b357321899bb3454001c0c746a6c06e3caf90550a7c12bb0b4f96` |
| | cadena enmascarada | `13fc6573f70e1b0f27b46e6d405c297b19bfd8c7e330193cdd6639d192f18f63` | `032492147403d9d46954e04540f72c9133f762286341d6c85d83b45787ef8405` |
| | local sin CBOR (6006 B) | `ab3760000d03a96896cc65c4cd520062da1011e7b740acd2914a75bcc3d3082a` | `d1c7a16412db57a0245175f0cdd79e80cce67ce144804f90340391d055da1f5d` |
| | cadena sin CBOR en bruto | `225020b1fca229d6abe46a241a3b0c58adecec5b305f1ceb4cc9b317a16c2bd5` | `ac72e00018571b93a11e693c9ddc646030d8ebb8f1dce99aabd08008b76c0ece` |
| | cadena sin CBOR enmascarada | `ab3760000d03a96896cc65c4cd520062da1011e7b740acd2914a75bcc3d3082a` | `d1c7a16412db57a0245175f0cdd79e80cce67ce144804f90340391d055da1f5d` |
| UnsweepConfig `0x56a345661e3999F2b20f1E069aAC14097Fa0D118` | local completo (881 B) | `3bf179f13463bf684f190c783d12bf9f250525fa5d17f8e2c614162ddfb45485` | `214def2b66f8e5bd6b06170bae715cac54251aab849cbe02e223e73a328bf622` |
| | cadena en bruto | `fc1ad05cb5a081a6274e2a8a1ee3cb08fb04202bbc00658a242457375f54c3f4` | `496a7d17f0c74bc2354cb4733d5641c538a13b24f41df754aa4a83c44d2f2629` |
| | cadena enmascarada | `3bf179f13463bf684f190c783d12bf9f250525fa5d17f8e2c614162ddfb45485` | `214def2b66f8e5bd6b06170bae715cac54251aab849cbe02e223e73a328bf622` |
| | local sin CBOR (828 B) | `31f8f53c5264aebcdfc4fbc88f92c1a83a25aff02b8c3b118e42318804599ed2` | `6f56c55fe3880d8073542fb474a0f3a05ae5928644ddfc9053ee6727670ae06c` |
| | cadena sin CBOR en bruto | `dd88ede240d016f76278197f156454e891dc4a99136798c35d84bca6f15f99f6` | `23dc567052f8922eea2b12b2639e9a2f2123952a2cceb092d24ad29d80db39fa` |
| | cadena sin CBOR enmascarada | `31f8f53c5264aebcdfc4fbc88f92c1a83a25aff02b8c3b118e42318804599ed2` | `6f56c55fe3880d8073542fb474a0f3a05ae5928644ddfc9053ee6727670ae06c` |

- En bruto no coinciden; las diferencias son exclusivamente immutables:
  - Delegate: 60 bytes distintos (rango 457-5711) = immutable `44128` en los offsets 445, 1004 y 5680, valor `0x56a345661e3999f2b20f1e069aac14097fa0d118` (dirección de UnsweepConfig, 20 B × 3).
  - Config: 22 bytes distintos (rango 510-743) = immutable `43801` (offset 498), owner `0x7e26916f1ff93fcf6ccd7eaaa0561007783fda1b`, e immutable `43803` (offset 712), `0x05dc` = 1500 (feeBps).
- Con las immutables enmascaradas, los dos contratos coinciden byte a byte, con y sin CBOR. Al ser idéntico el CBOR de metadatos, el código fuente compilado es equivalente al de HEAD.
- Limitación: el exact_match en Sourcify para Arbitrum es una afirmación del README que no se ha vuelto a comprobar en esta orden.

### 8.5 app.js en producción frente al repo — COINCIDE

Consulta a las `2026-11-24T20:22:38Z`:

```
$ curl -s https://unsweep.com/assets/app.js | sha256sum
85f9dce6162ec60f5a97386f61c785a57959038ad5423121e2373696bd1f9245  -
$ sha256sum web/assets/app.js
85f9dce6162ec60f5a97386f61c785a57959038ad5423121e2373696bd1f9245  web/assets/app.js
```

HTTP 200, 22163 bytes en los dos lados y `diff` vacío. Último commit que toca `web/assets/app.js`: `549205a0da8e4342021016a49f96693bd6a9db80`. Limitación: es una sola muestra, desde una IP y en un instante; un CDN o una caché podrían servir otro contenido a otros clientes.

### 8.6 Recuento actualizado

- R-5: de HIPOTESIS a HECHO (Medium, misma causa raíz que C-1).
- W-7: PARCIAL (Low, severidad como OPINION).
- R-6: CUMPLE; la programación de la lista OFAC en producción queda NO_DISPONIBLE.
- El bytecode de Arbitrum y el app.js de producción coinciden con el repo.
- Critical/High manuales: 0.
