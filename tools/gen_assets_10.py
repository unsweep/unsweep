"""ORDEN #2236 fase B: genera relayer/data/assets_10.json (OP Mainnet, chainId 10).

Regla: una direccion solo entra si (1) aparece en una fuente del repo
(evidence/chainlink/superchain.tokenlist.json para tokens chainId 10;
evidence/chainlink/feeds-ethereum-mainnet-optimism-1.json, copia del directorio oficial
de Chainlink, para feeds) y (2) symbol()/decimals()/latestRoundData() se confirman por
eth_call en OP en un bloque fijo. Nada por defecto: lo no verificado se EXCLUYE con motivo.
Lee OP_RPC_URL del entorno y nunca la imprime. Solo lectura (eth_chainId, eth_blockNumber,
eth_getBlockByNumber, eth_getCode, eth_call).
"""
import json, os, sys, time, pathlib, urllib.request, urllib.error

R = pathlib.Path(__file__).resolve().parent.parent
E = R / 'evidence' / 'chainlink'
OUT = R / 'relayer' / 'data' / 'assets_10.json'
EVID = R / 'artifacts' / 'm2236' / 'onchain_10.json'

# simbolo del token -> path del feed en el directorio oficial (par simple / USD)
APPROVED = [
    ('USDC', 'usdc-usd'),
    ('USDT', 'usdt-usd'),
    ('DAI', 'dai-usd'),
    ('WETH', 'eth-usd'),
    ('OP', 'op-usd'),
    ('WBTC', 'wbtc-usd'),
    ('LINK', 'link-usd'),
    ('wstETH', 'wsteth-usd'),
]
EXCLUDED_BY_POLICY = {
    'USDC.e': 'USDC puenteado (0x7F5c...1607); solo USDC nativo, mismo criterio que Arbitrum (#1017)',
    'ETH(0xDead...0000)': 'ETH legacy OVM, no es ERC-20 real',
    'TRX/APT/SOL': 'tokens puenteados; el feed cotiza el activo nativo de otra cadena',
    'STETH->wstETH, BTC->WBTC': 'emparejamiento por simbolo no equivalente; se usan wsteth-usd y wbtc-usd',
}
SEL = {'symbol': '0x95d89b41', 'decimals': '0x313ce567', 'latestRoundData': '0xfeaf968c',
       'aggregator': '0x245a7bfc', 'description': '0x7284e416'}

URL = os.environ.get('OP_RPC_URL', '').strip().strip('"').strip("'")
if not URL:
    sys.exit('OP_RPC_URL no definida')

_id = [0]


def rpc(method, params):
    for i in range(8):
        _id[0] += 1
        body = json.dumps({'jsonrpc': '2.0', 'id': _id[0], 'method': method, 'params': params}).encode()
        req = urllib.request.Request(URL, data=body, headers={'Content-Type': 'application/json'})
        try:
            with urllib.request.urlopen(req, timeout=20) as r:
                j = json.loads(r.read())
        except urllib.error.HTTPError as e:
            if e.code == 429:
                time.sleep(min(1.0 * 2 ** i, 15)); continue
            raise SystemExit('rpc http error %d (url oculta)' % e.code) from None
        except Exception as e:
            raise SystemExit('rpc no disponible: %s (url oculta)' % type(e).__name__) from None
        if 'error' in j:
            if 'rate' in json.dumps(j['error']).lower():
                time.sleep(min(1.0 * 2 ** i, 15)); continue
            return None, j['error']
        time.sleep(0.15)
        return j['result'], None
    raise SystemExit('rpc rate limited persistente')


def call(to, sel, block):
    res, err = rpc('eth_call', [{'to': to, 'data': sel}, block])
    if err or not res or res == '0x':
        return None
    return res


def dec_uint(h, idx=0):
    return int(h[2 + 64 * idx: 2 + 64 * (idx + 1)], 16)


def dec_int(h, idx):
    v = dec_uint(h, idx)
    return v - (1 << 256) if v >= 1 << 255 else v


def dec_str(h):
    b = bytes.fromhex(h[2:])
    if len(b) >= 96 and int.from_bytes(b[0:32], 'big') == 32:
        n = int.from_bytes(b[32:64], 'big')
        return b[64:64 + n].decode('utf-8', 'replace')
    if len(b) == 32:  # bytes32
        return b.rstrip(b'\x00').decode('utf-8', 'replace')
    return None


def main():
    cid, _ = rpc('eth_chainId', [])
    if int(cid, 16) != 10:
        sys.exit('chainId != 10')
    bn_hex, _ = rpc('eth_blockNumber', [])
    blk, _ = rpc('eth_getBlockByNumber', [bn_hex, False])
    bts = int(blk['timestamp'], 16)
    bn = int(bn_hex, 16)

    tl = json.load(open(E / 'superchain.tokenlist.json'))
    toks = {}
    for t in tl['tokens']:
        if t.get('chainId') == 10:
            toks.setdefault(t['symbol'], []).append(t)
    fd = json.load(open(E / 'feeds-ethereum-mainnet-optimism-1.json'))
    by_path = {}
    for f in fd:
        by_path.setdefault(f.get('path'), []).append(f)

    log = {'chainId': 10, 'block': bn, 'block_ts': bts, 'tokens': [], 'feeds': [], 'excluded': []}

    def verify_feed(path):
        recs = by_path.get(path) or []
        if len(recs) != 1:
            return None, 'feed %s: %d entradas en el directorio' % (path, len(recs))
        rec = recs[0]
        docs = rec.get('docs') or {}
        if docs.get('hidden') or docs.get('shutdownDate') or 'deprecat' in json.dumps(docs).lower():
            return None, 'feed %s oculto/deprecating' % path
        name = rec['name']
        if not name.endswith(' / USD'):
            return None, 'feed %s no cotiza USD' % path
        addr = rec['proxyAddress']
        code, _ = rpc('eth_getCode', [addr, bn_hex])
        d = call(addr, SEL['decimals'], bn_hex)
        lr = call(addr, SEL['latestRoundData'], bn_hex)
        ag = call(addr, SEL['aggregator'], bn_hex)
        ds = call(addr, SEL['description'], bn_hex)
        entry = {'path': path, 'address': addr, 'pair': name, 'code_bytes': (len(code) - 2) // 2 if code else 0}
        if not code or code == '0x' or d is None or lr is None or ag is None:
            entry['ok'] = False; log['feeds'].append(entry)
            return None, 'feed %s: eth_call fallido' % path
        dec = dec_uint(d)
        rid, ans, upd, air = dec_uint(lr, 0), dec_int(lr, 1), dec_uint(lr, 3), dec_uint(lr, 4)
        hb = int(rec['heartbeat'])
        age = bts - upd
        entry.update({'decimals': dec, 'roundId': str(rid), 'answer': str(ans), 'updatedAt': upd,
                      'age_s': age, 'heartbeat': hb, 'aggregator': '0x' + ag[-40:],
                      'description': dec_str(ds) if ds else None})
        problems = []
        if dec != int(rec['decimals']): problems.append('decimals != directorio')
        if ans <= 0: problems.append('answer<=0')
        if air < rid: problems.append('answeredInRound<roundId')
        if upd == 0 or age > hb + 600: problems.append('stale age=%ds hb=%ds' % (age, hb))
        entry['ok'] = not problems; entry['problems'] = problems
        log['feeds'].append(entry)
        if problems:
            return None, 'feed %s: %s' % (path, ';'.join(problems))
        return {'address': addr, 'pair': name, 'quote': 'USD', 'heartbeat': hb, 'decimals': dec,
                'aggregator': '0x' + ag[-40:]}, None

    eth, err = verify_feed('eth-usd')
    if not eth:
        sys.exit('ETH/USD no verificado: %s' % err)

    out = []
    for sym, path in APPROVED:
        cands = toks.get(sym) or []
        if len(cands) != 1:
            log['excluded'].append({'symbol': sym, 'motivo': '%d entradas en tokenlist chainId 10' % len(cands)}); continue
        addr = cands[0]['address']
        code, _ = rpc('eth_getCode', [addr, bn_hex])
        s = call(addr, SEL['symbol'], bn_hex)
        d = call(addr, SEL['decimals'], bn_hex)
        te = {'symbol_expected': sym, 'address': addr, 'code_bytes': (len(code) - 2) // 2 if code else 0,
              'symbol_onchain': dec_str(s) if s else None, 'decimals_onchain': dec_uint(d) if d else None,
              'decimals_tokenlist': cands[0].get('decimals')}
        log['tokens'].append(te)
        if not code or code == '0x' or te['symbol_onchain'] != sym or te['decimals_onchain'] is None \
                or te['decimals_onchain'] != te['decimals_tokenlist']:
            log['excluded'].append({'symbol': sym, 'motivo': 'verificacion on-chain del token fallida', 'detalle': te}); continue
        feed, ferr = (eth, None) if path == 'eth-usd' else verify_feed(path)
        if not feed:
            log['excluded'].append({'symbol': sym, 'motivo': ferr}); continue
        out.append({'address': addr, 'symbol': sym, 'decimals': te['decimals_onchain'], 'fee_on_transfer': False,
                    'feed': feed,
                    '_evidence': {'token': 'evidence/chainlink/superchain.tokenlist.json (chainId 10) + eth_call symbol()/decimals()/getCode',
                                  'feed': 'evidence/chainlink/feeds-ethereum-mainnet-optimism-1.json path=%s + eth_call decimals()/latestRoundData()/aggregator()' % path}})
    for k, v in EXCLUDED_BY_POLICY.items():
        log['excluded'].append({'symbol': k, 'motivo': v})

    EVID.parent.mkdir(parents=True, exist_ok=True)
    EVID.write_text(json.dumps(log, indent=1) + '\n')
    doc = {'chainId': 10, 'eth_usd_feed': eth, 'tokens': out, 'nfts': [],
           '_verified': {'block': bn, 'block_ts': bts,
                         'method': 'eth_call proxy.aggregator()/decimals()/latestRoundData() + token symbol()/decimals()/getCode',
                         'evidence': 'artifacts/m2236/onchain_10.json',
                         'sources': ['evidence/chainlink/superchain.tokenlist.json',
                                     'evidence/chainlink/feeds-ethereum-mainnet-optimism-1.json (https://reference-data-directory.vercel.app/feeds-ethereum-mainnet-optimism-1.json, ver feeds-optimism.source)']}}
    OUT.write_text(json.dumps(doc, indent=1) + '\n')
    print('OK', len(out), 'tokens; excluidos', len(log['excluded']), '; bloque', bn)
    for x in log['excluded']:
        print('EXCL', x['symbol'], '|', x['motivo'])


if __name__ == '__main__':
    main()
