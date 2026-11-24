# Acta ORDEN #1690 partes (1) y (2)

- Commit: cc76b70c03f02ed2fb6bf77e06c24fb9caa16c22 (push a origin/main, FF desde 522f9eb).
- Tests: relayer 154 passed (150 previos + 4 test_ux_1690.py) en imagen efímera unsweep-relayer-test:1690 (+nodejs), sin red; deploy/tests 9 passed.
- Backup previo de estáticos: tmp/bk1690_20261124T000329Z y /opt/aire/backups/unsweep-static/20261124T000407Z.
- Deploy: deploy/deploy_relayer.sh --commit cc76b70c… (relayer) + deploy/deploy_static.sh desde tmp/fase1 (main=cc76b70).
- Producción: /api/health 200 (chainId 8453); index.html 24c2bedb…, app.js 9d27435f…, style.css 0bd55c6b… idénticos a git show cc76b70; SRI sha384 de app.js y style.css OK; título «Additional tokens detected - optional» y supportHint presentes.
- Aviso de soporte en texto plano (sin un segundo mailto) para respetar el invariante de test_portada.

## POST /api/scan (Base, cuerpo {address}, igual que la UI)
```
holder http=200 ts=2026-11-24T00:05:43Z
vacia http=200 ts=2026-11-24T00:05:50Z
holder keys ['address', 'approvals', 'approvalsError', 'chainId', 'delegatedToUnsweep', 'delegation7702', 'eth_wei', 'extras', 'nfts', 'nonce', 'rescuable', 'tokens']
holder status None block None tokens 6 extras 50
  tok {'symbol': 'USDC', 'listed': None, 'balanceRaw': None, 'value_usd': None, 'valueUsd': None}
  tok {'symbol': 'WETH', 'listed': None, 'balanceRaw': None, 'value_usd': None, 'valueUsd': None}
  tok {'symbol': 'cbETH', 'listed': None, 'balanceRaw': None, 'value_usd': None, 'valueUsd': None}
  tok {'symbol': 'cbBTC', 'listed': None, 'balanceRaw': None, 'value_usd': None, 'valueUsd': None}
  tok {'symbol': 'LINK', 'listed': None, 'balanceRaw': None, 'value_usd': None, 'valueUsd': None}
  tok {'symbol': 'wstETH', 'listed': None, 'balanceRaw': None, 'value_usd': None, 'valueUsd': None}
  ext {'symbol': 'TOWNS', 'address': '0x00000000A22C618fd6b4D7E9A335C4B96B189a38', 'balanceRaw': None, 'value_usd': 0, 'fee_bps': None, 'feeBps': None}
  ext {'symbol': 'XDP', 'address': '0x07b3D902783c3C12b077508c3B5c00113d1291D0', 'balanceRaw': None, 'value_usd': 0, 'fee_bps': None, 'feeBps': None}
  ext {'symbol': 'BASED', 'address': '0x07d15798a67253D76cea61F0eA6F57AeDC59DffB', 'balanceRaw': None, 'value_usd': 0, 'fee_bps': None, 'feeBps': None}
  ext {'symbol': 'MISFIT', 'address': '0x08014382ee327a7e0C09b34A1ba6AD5675434613', 'balanceRaw': None, 'value_usd': 0, 'fee_bps': None, 'feeBps': None}
  ext {'symbol': 'VIRTUAL', 'address': '0x0b3e328455c4059EEb9e3f84b5543F74E24e7E1b', 'balanceRaw': None, 'value_usd': 0, 'fee_bps': None, 'feeBps': None}
  ext {'symbol': 'CHIP', 'address': '0x0C1c1C109FE34733fca54b82d7B46B75CFb71F6e', 'balanceRaw': None, 'value_usd': 0, 'fee_bps': None, 'feeBps': None}
vacia keys ['address', 'approvals', 'approvalsError', 'chainId', 'delegatedToUnsweep', 'delegation7702', 'eth_wei', 'extras', 'nfts', 'nonce', 'rescuable', 'tokens']
vacia status None block None tokens 0 extras 0
== supportVisible (app.js servido)
src: function supportVisible(s) { return !!s && !s.rescuable && !((s.tokens || []).some((t) => { try { return BigInt(t.balance || 0) > 0n; } catch (e) { return false; } })); }
holder supportVisible= false
vacia supportVisible= true
```

Pendiente: capturas 375/1280 px; parte (3); Arbitrum (#145).

## Capturas Step 1 (Chromium headless, playwright) — ORDEN #1690 paso (a)

Generadas con `docs/actas/orden1690/capturas.py`: se sirve `web/` del commit cc76b70 en local y se simulan `/api/config` y `/api/scan` con los JSON guardados (`scan_holder.json`, `scan_vacia.json`). No se hizo ninguna llamada a producción. El resultado de las aserciones está en `capturas.json`.

| Caso | Ancho | Archivo | Comprobación |
|---|---|---|---|
| Con valor rescatable | 375 | step1_con_valor_375.png | extrasBox visible dentro de #scanOut, título 'Additional tokens detected - optional', 20 extras, supportHint oculto, botón Step 2 visible |
| Con valor rescatable | 1280 | step1_con_valor_1280.png | igual |
| Sin valor | 375 | step1_sin_valor_375.png | supportHint visible 'Don't see your token? Email support@unsweep.com', extrasBox oculto, sin botón Step 2 |
| Sin valor | 1280 | step1_sin_valor_1280.png | igual |

SHA-256:
```
a6d8639ea89fc2e8149c50927ba712b07f2bc9d11308e4b9ad3adcc07f8c91b6  docs/actas/orden1690/step1_con_valor_1280.png
f797c7703d66a777ff5082b4f9089e1e2b657553c83fa505e256b10208a108f5  docs/actas/orden1690/step1_con_valor_375.png
b112ed5fd986a6131d077bc45ee2dc60fa62d3d6d915d107cf63132a58a07856  docs/actas/orden1690/step1_sin_valor_1280.png
40bb69da4aacdb4333707559b0a22cd5de23300c6c93066051fba8689d1a618e  docs/actas/orden1690/step1_sin_valor_375.png
```
