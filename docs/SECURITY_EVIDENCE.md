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
