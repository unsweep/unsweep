"""Genera relayer/data/assets_8453.json desde evidence/chainlink (fuentes oficiales + comprobacion on-chain).
Falla si falta cualquier dato: no hay valores por defecto."""
import json, re, sys, pathlib
R = pathlib.Path(__file__).resolve().parent.parent
E = R / 'evidence' / 'chainlink'
APPROVED = ['USDC','USDT','DAI','WETH','cbETH','cbBTC','LINK','AERO','EURC','GHO','tBTC','sUSDe','COMP','WELL','wstETH','weETH']
TOKEN_LINE = {'LINK': 'LINK_hip', 'sUSDe': 'sUSDe_hip', 'weETH': 'weETH_aave'}
FEED_LINE = {'WETH': 'ETH', 'tBTC': 'TBTC', 'wstETH': 'wstETH/ETH', 'weETH': 'weETH/ETH'}
toks = {}
for ln in (E / 'tokens_onchain.txt').read_text().splitlines():
    p = ln.split('|')
    if len(p) >= 5 and p[1].startswith('0x'):
        toks[p[0]] = {'address': p[1], 'sym': re.search(r'sym="([^"]*)"', ln).group(1), 'dec': int(re.search(r'dec=(\d+)', ln).group(1))}
feeds = {}
for ln in (E / 'onchain_check.txt').read_text().splitlines():
    p = ln.split('|')
    if len(p) >= 3 and p[1].startswith('0x'):
        feeds[p[0]] = {'address': p[1], 'ok': ln.rstrip().endswith('|OK'), 'line': ln}
d = json.load(open(E / 'feeds-ethereum-mainnet-base-1.json'))
idx = {}
for f in d:
    for k in ('proxyAddress', 'secondaryProxyAddress'):
        if f.get(k):
            idx[f[k].lower()] = f
def feed_for(label):
    fl = feeds.get(label)
    if not fl or not fl['ok']:
        sys.exit('feed sin verificar on-chain: %s' % label)
    rec = idx.get(fl['address'].lower())
    if not rec:
        sys.exit('feed no esta en el directorio oficial: %s %s' % (label, fl['address']))
    q = rec['name'].split('/')[-1].strip().upper()
    if q not in ('USD', 'ETH'):
        sys.exit('cotizacion no soportada %s: %s' % (label, rec['name']))
    return {'address': fl['address'], 'pair': rec['name'], 'quote': q, 'heartbeat': int(rec['heartbeat']), 'decimals': int(rec['decimals'])}
out_t = []
for s in APPROVED:
    t = toks.get(TOKEN_LINE.get(s, s))
    if not t or t['sym'] != s:
        sys.exit('token sin verificar: %s' % s)
    out_t.append({'address': t['address'], 'symbol': s, 'decimals': t['dec'], 'fee_on_transfer': False, 'feed': feed_for(FEED_LINE.get(s, s))})
eth = feed_for('ETH')
if eth['quote'] != 'USD':
    sys.exit('ETH/USD invalido')
dst = R / 'relayer' / 'data' / 'assets_8453.json'
old = json.load(open(dst))
doc = {'_note': 'Base mainnet (8453). Lista aprobada #90 (16 tokens). Direcciones: docs oficiales (Circle, Chainlink, Ethena, Aave address-book) y eth_call on-chain; feeds: directorio oficial Chainlink (evidence/chainlink). Precios SOLO por latestRoundData on-chain (relayer/oracle.py, fail-closed). Generado por tools/gen_assets_8453.py. ETH nativo NO incluido: el delegate solo barre ERC-20/ERC-721.',
       'eth_usd_feed': eth, 'tokens': out_t, 'nfts': old.get('nfts', [])}
json.dump(doc, open(dst, 'w'), indent=1)
print('OK', len(out_t), 'tokens')
