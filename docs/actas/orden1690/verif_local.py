# ORDEN #1690 parte (3): verificacion LOCAL en solo lectura del camino de /api/quote_manual.
# Sin API de produccion, sin record() (PG), sin Alchemy, sin claves. RPC publico de Base.
# Uso: UNSWEEP_RPC=https://mainnet.base.org UNSWEEP_CHAIN_ID=8453 TURNSTILE_SECRET=local-no-secret \
#      TURNSTILE_SITEKEY=local-no-sitekey python verif_local.py
import json, os, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', '..', 'relayer'))
from web3 import Web3
import manual as MAN
import extras as EX
import oracle as O
import svc_scan as S
from svc_core import assets, w3, CHAIN_ID
from svc_manual import add_manual, manual_rpc

BRETT = '0x532f27101965dd16442E59d40670FaF5eBB142E4'
WETH = '0x4200000000000000000000000000000000000006'
FACTORY = '0x420DD381b31aEf6683db6B902084cB0FFECe40Da'  # Aerodrome PoolFactory (sin decimals)
SAFE = '0x000000000000000000000000000000000000dEaD'
out = {'chainId': CHAIN_ID, 'rpc': 'https://mainnet.base.org (publico)'}
blk = w3.eth.block_number
out['block'] = blk
# Holder: pool Uniswap v3 BRETT/WETH fee 1% (getPool(address,address,uint24) por eth_call): >10k USD en WETH listado -> tramo 500 bps
UNI3 = '0x33128a8fC17869897dcE68Ed026d694621f6FDfD'
sel = Web3.keccak(text='getPool(address,address,uint24)')[:4].hex()
sel = sel if sel.startswith('0x') else '0x' + sel
data = sel + BRETT[2:].lower().rjust(64, '0') + WETH[2:].lower().rjust(64, '0') + hex(10000)[2:].rjust(64, '0')
r = w3.eth.call({'to': UNI3, 'data': data}, blk)
holder = Web3.to_checksum_address('0x' + bytes(r)[-20:].hex())
out['holder'] = holder
out['manual_contract'] = BRETT
allowed = O.allowlist(assets())
out['manual_en_allowlist'] = BRETT in allowed

# scan() sin live_approvals/scan_extras/delegation (evita Alchemy y logs): mismo bucle de tokens listados
a = assets(); toks = []
for t in a['tokens']:
    ca = Web3.to_checksum_address(t['address'])
    if ca not in allowed:
        continue
    bal = w3.eth.contract(address=ca, abi=S.ERC20).functions.balanceOf(holder).call(block_identifier=blk)
    if bal > 0:
        toks.append({**t, 'balance': str(bal), 'price_usd': S._token_px(a, t), 'price_feeds': S._token_feeds(a, t)})
s = {'address': holder, 'chainId': CHAIN_ID, 'tokens': toks, 'nfts': [], 'extras': [], 'safe': SAFE}
out['listed'] = [(t['symbol'], t['balance']) for t in toks]
out['listed_value_usd'] = round(MAN.listed_value_usd(s), 2)
out['manual_enabled'] = MAN.manual_enabled(s)

acc, rej = add_manual(s, MAN.parse_contracts([BRETT]))
out['accepted'] = acc; out['rejected'] = rej
q, _ = S.quote(s, extras=[BRETT])
ml = [l for l in q['lines'] if l['token'] == BRETT]
out['quote'] = {'feeBps': q['feeBps'], 'policy_ok': q['policy_ok'], 'policy_reason': q['policy_reason'],
                'rescued_usd': q['rescued_usd'], 'fee_usd': q['fee_usd'], 'manual_line': ml}
e = acc[0] if acc else None
if e:
    est = lambda tx: w3.eth.estimate_gas(tx); call = lambda tx: w3.eth.call(tx)
    g = EX.simulate_extra((call, est), holder, SAFE, e)
    out['gas_extra'] = g; out['gas_limit'] = EX.EXTRA_GAS_LIMIT
    out['gas_limit_1000'] = EX.simulate_extra((call, est), holder, SAFE, e, limit=1000)
    gp = w3.eth.gas_price; eth = S._eth_usd()
    gas_usd = (1_500_000 + (g or 0)) * gp / 1e18 * eth
    out['gas_total_usd'] = gas_usd; out['listed_fee_usd'] = q['fee_usd']
    out['gas_cubierto'] = q['fee_usd'] >= gas_usd
chk = {}
chk['unverified'] = bool(ml) and ml[0].get('unverified') is True and e['unverified'] is True
chk['value_usd_0'] = bool(e) and e['value_usd'] == 0
chk['fee_bps_500'] = q['feeBps'] == 500 and bool(ml) and int(ml[0]['fee']) == int(ml[0]['amount']) * 500 // 10000
chk['gas_limite'] = e is not None and out.get('gas_extra') is not None and out['gas_extra'] <= EX.EXTRA_GAS_LIMIT and out['gas_limit_1000'] is None
chk['gas_cubierto'] = out.get('gas_cubierto') is True
out['checks'] = chk

# Rechazos
R = []
def pc(label, raw):
    try:
        v = MAN.parse_contracts(raw)
        R.append({'caso': label, 'resultado': 'HTTP 400 indica entre 1 y %d contratos' % MAN.MANUAL_MAX if not v else 'aceptado', 'ok': not v})
    except MAN.ManualInputError as ex:
        R.append({'caso': label, 'resultado': 'HTTP 400 ' + str(ex), 'ok': True})
pc('0 contratos', [])
pc('4 contratos', [BRETT, WETH, FACTORY, SAFE])
pc('direccion invalida', ['0x1234'])
pc('checksum invalido', [BRETT.lower()])
s2 = {'address': holder, 'tokens': toks, 'nfts': [], 'extras': [], 'safe': SAFE}
a2, r2 = add_manual(s2, [FACTORY])
R.append({'caso': 'contrato sin decimals (Aerodrome PoolFactory)', 'resultado': r2, 'ok': not a2 and 'no es ERC-20' in r2[0]['reason']})
a3, r3 = add_manual(dict(s2, extras=[]), ['0x0000000000000000000000000000000000000001'])
R.append({'caso': 'direccion sin codigo', 'resultado': r3, 'ok': not a3 and 'sin codigo' in r3[0]['reason']})
a4, r4 = add_manual(dict(s2, extras=[]), [WETH])
R.append({'caso': 'token ya listado', 'resultado': r4, 'ok': not a4 and 'duplicado' in r4[0]['reason']})
a5, r5 = add_manual(dict(s2, extras=[{'address': BRETT}]), [BRETT])
R.append({'caso': 'ya detectado por discover_extras', 'resultado': r5, 'ok': not a5 and 'ya detectado' in r5[0]['reason']})
s6 = {'address': holder, 'tokens': [], 'nfts': [], 'extras': []}
en6 = MAN.manual_enabled(s6); a6, r6 = add_manual(s6, [BRETT])
R.append({'caso': 'sin token listado con valor', 'resultado': {'manual_enabled': en6, 'rejected': r6}, 'ok': en6[0] is False and not a6})
out['rechazos'] = R
out['todo_ok'] = all(chk.values()) and all(x['ok'] for x in R)
print(json.dumps(out, indent=1, default=str))
