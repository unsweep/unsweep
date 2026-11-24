"""#1690 (3) salvedad 1 de #558: verificacion LOCAL del extra manual con un ERC-20 que discover_extras NO detecta.
No toca produccion ni llama a /api/quote_manual publico. Solo lecturas eth_call/estimateGas. Sin firmas.
Uso (desde relayer/): python ../docs/actas/orden1690/verif_extra_manual.py > ../docs/actas/orden1690/verif_extra_manual.json
"""
import json, os, re, subprocess, sys
sys.path.insert(0, os.getcwd())
import extras as EX, svc_scan as S, oracle as O
from svc_core import assets, w3

HERE = os.path.dirname(os.path.abspath(__file__))
H = '0xBA3F945812a83471d709BCe9C3CA699A19FB46f7'      # pool BRETT/WETH (holder real)
BRETT = '0x532f27101965dd16442E59d40670FaF5eBB142E4'

out = {'orden': '#1690 (3) salvedad 1 de #558', 'entorno': 'local, sin produccion, sin firmas',
       'token': BRETT, 'holder': H, 'chainId': 8453}

# 1) discover_extras REAL (Alchemy via _extras_rpc, como en produccion)
raw = S._extras_rpc('alchemy_getTokenBalances', [H, 'erc20']) or {}
ex = EX.discover_extras(S._extras_rpc, H, O.allowlist(assets()))
out['discover_extras'] = {'alchemy_entries_pagina1': len(raw.get('tokenBalances', []) or []),
                          'alchemy_pageKey_presente': bool(raw.get('pageKey')),
                          'extras_devueltos': len(ex),
                          'token_detectado': any(e['address'] == BRETT for e in ex),
                          'causa': 'discover_extras solo lee la 1a pagina de alchemy_getTokenBalances (sin pageKey); el token queda fuera'}

# 2) ruta manual local (verif_local.py: balanceOf/symbol/decimals por UNSWEEP_RPC, simulate_extra con limite de gas)
p = subprocess.run([sys.executable, os.path.join(HERE, 'verif_local.py')], capture_output=True, text=True, timeout=300)
if p.returncode != 0:
    print(p.stderr[-2000:], file=sys.stderr); sys.exit(1)
m = json.loads(p.stdout[p.stdout.index('{'):])
out['ruta_manual'] = m
out['block'] = m.get('block')
ml = (m.get('quote') or {}).get('manual_line') or [{}]
acc = (m.get('accepted') or [{}])
out['linea_manual'] = {'unverified': ml[0].get('unverified'), 'value_usd': acc[0].get('value_usd') if acc else None,
                       'fee_bps': (m.get('quote') or {}).get('feeBps'), 'amount': ml[0].get('amount'), 'fee': ml[0].get('fee'),
                       'gas_simulado': m.get('gas_extra'), 'gas_limite': m.get('gas_limit'),
                       'excluido_con_limite_1000': m.get('gas_limit_1000') is None}
cuarto = [r for r in m.get('rechazos', []) if r['caso'] == '4 contratos']
out['rechazo_cuarto_contrato'] = cuarto

# 3) UI (web/assets/app.js): bloque manual solo con token listado con valor; tope 3 en cliente
js = open(os.path.join(HERE, '..', '..', '..', 'web', 'assets', 'app.js')).read().splitlines()
ui = {k: [(i + 1, l.strip()[:200]) for i, l in enumerate(js) if re.search(pat, l)] for k, pat in {
    'habilitacion_por_valor': r'b\.hidden = !ok', 'tope_3_cliente': r'man\.length > 3'}.items()}
out['ui'] = ui

chk = {'token_no_detectado_por_discover_extras': out['discover_extras']['token_detectado'] is False,
       'unverified_true': ml[0].get('unverified') is True,
       'value_usd_0': bool(acc) and acc[0].get('value_usd') == 0,
       'fee_bps_500': (m.get('quote') or {}).get('feeBps') == 500 and bool(ml[0]) and int(ml[0]['fee']) == int(ml[0]['amount']) * 500 // 10000,
       'gas_bajo_limite': m.get('gas_extra') is not None and m['gas_extra'] < m['gas_limit'],
       'ui_solo_con_listado_con_valor': bool(ui['habilitacion_por_valor']) and any(r['caso'] == 'sin token listado con valor' and r['ok'] for r in m.get('rechazos', [])),
       'tope_3_cliente_y_servidor': bool(ui['tope_3_cliente']) and bool(cuarto) and cuarto[0]['ok'],
       'verif_local_todo_ok': m.get('todo_ok') is True}
out['checks'] = chk
out['todo_ok'] = all(chk.values())
print(json.dumps(out, indent=1, default=str))
