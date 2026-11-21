"""UNSWEEP M2d: escaner MAINNET de SOLO LECTURA (Base, Ethereum).

Nunca firma, nunca pide claves, nunca envia transacciones. No registra URLs de RPC
(llevan la clave en la ruta) ni la direccion escaneada.

Aprobaciones: Alchemy Free limita eth_getLogs a 10 bloques, asi que se reconstruyen
desde las tx SALIENTES del owner (alchemy_getAssetTransfers external, excludeZeroValue
False) filtrando el selector approve(0x095ea7b3) y confirmando con allowance().
Limitaciones declaradas en la respuesta: no detecta permit/Permit2 firmados off-chain
ni aprobaciones anteriores a la ventana o fuera de las MAX_TX tx mas recientes.
"""
import os, time, json, hashlib, threading
import requests

CHAINS = {
    'base': {'env': 'BASE_RPC_URL', 'chain_id': 8453, 'block_s': 2, 'native': 'ETH',
             'explorer': 'https://basescan.org/address/'},
    'ethereum': {'env': 'ETH_RPC_URL', 'chain_id': 1, 'block_s': 12, 'native': 'ETH',
                 'explorer': 'https://etherscan.io/address/'},
}
LOOKBACK_DAYS = 90
MAX_TX = int(os.environ.get('UNSWEEP_MAINNET_MAX_TX', '200'))
BATCH = 10
BUDGET_S = float(os.environ.get('UNSWEEP_MAINNET_BUDGET_S', '20'))
CACHE_TTL = 600
MAX_TOKENS = 15
SEL_APPROVE = '0x095ea7b3'
SEL_ALLOWANCE = '0xdd62ed3e'
DELEG_PREFIX = '0xef0100'
PG_DSN = os.environ.get('UNSWEEP_PG', 'dbname=unsweep')

_cache, _clock = {}, threading.Lock()
_session = requests.Session()
_session.headers.update({'Content-Type': 'application/json', 'User-Agent': 'unsweep-scan/1'})


class ScanError(Exception):
    pass


def _url(chain):
    u = os.environ.get(CHAINS[chain]['env'], '').strip().strip('"').strip("'")
    if not u:
        raise ScanError('chain not configured')
    return u


def _post(url, body, deadline, tries=5):
    for i in range(tries):
        left = deadline - time.time()
        if left <= 0.5:
            raise ScanError('time budget exceeded')
        try:
            r = _session.post(url, data=json.dumps(body), timeout=min(10, left))
        except requests.RequestException:
            raise ScanError('rpc unavailable') from None  # sin URL en el mensaje
        if r.status_code == 429:
            time.sleep(min(0.5 * 2 ** i, max(0, deadline - time.time() - 1)))
            continue
        if r.status_code != 200:
            raise ScanError('rpc http %d' % r.status_code)
        return r.json()
    raise ScanError('rpc rate limited')


def _rpc(url, method, params, deadline):
    j = _post(url, {'jsonrpc': '2.0', 'id': 1, 'method': method, 'params': params}, deadline)
    if 'result' not in j:
        raise ScanError('rpc error in %s' % method)
    return j['result']


def _word(a):
    return a[2:].lower().rjust(64, '0')


def _approvals(url, chain, addr, head, deadline):
    frm = max(0, head - LOOKBACK_DAYS * 86400 // CHAINS[chain]['block_s'])
    res = _rpc(url, 'alchemy_getAssetTransfers', [{
        'fromBlock': hex(frm), 'toBlock': 'latest', 'fromAddress': addr,
        'category': ['external'], 'order': 'desc', 'maxCount': hex(MAX_TX),
        'excludeZeroValue': False}], deadline)
    hashes = list(dict.fromkeys(x['hash'] for x in res.get('transfers', [])))[:MAX_TX]
    truncated = bool(res.get('pageKey'))
    pairs, scanned = {}, 0
    for i in range(0, len(hashes), BATCH):
        if time.time() > deadline - 3:
            truncated = True
            break
        batch = [{'jsonrpc': '2.0', 'id': j, 'method': 'eth_getTransactionByHash', 'params': [h]}
                 for j, h in enumerate(hashes[i:i + BATCH])]
        out = _post(url, batch, deadline)
        for x in (out if isinstance(out, list) else []):
            t = x.get('result') or {}
            scanned += 1
            inp = t.get('input') or ''
            if inp[:10] == SEL_APPROVE and t.get('to') and len(inp) >= 138:
                tok, sp = t['to'].lower(), '0x' + inp[34:74]
                pairs.setdefault((tok, sp), t.get('hash'))
    live = []
    for (tok, sp), txh in pairs.items():
        if time.time() > deadline - 1:
            truncated = True
            break
        try:
            v = _rpc(url, 'eth_call', [{'to': tok, 'data': SEL_ALLOWANCE + _word(addr) + _word(sp)}, 'latest'], deadline)
            amt = int(v, 16) if v and v != '0x' else 0
        except (ScanError, ValueError):
            continue
        if amt > 0:
            live.append({'token': tok, 'spender': sp, 'allowance': str(amt),
                         'unlimited': amt >= 2 ** 255, 'approveTx': txh})
    return {'items': live, 'txScanned': scanned, 'truncated': truncated}


def scan_mainnet(chain, addr):
    if chain not in CHAINS:
        raise ScanError('unsupported chain')
    addr = addr.lower()
    key = (chain, addr)
    with _clock:
        hit = _cache.get(key)
        if hit and time.time() - hit[0] < CACHE_TTL:
            return dict(hit[1], cached=True)
    t0 = time.time()
    deadline = t0 + BUDGET_S
    url = _url(chain)
    head = int(_rpc(url, 'eth_blockNumber', [], deadline), 16)
    code = _rpc(url, 'eth_getCode', [addr, 'latest'], deadline) or '0x'
    deleg = '0x' + code[8:48] if code.lower().startswith(DELEG_PREFIX) and len(code) == 48 else None
    nonce = int(_rpc(url, 'eth_getTransactionCount', [addr, 'latest'], deadline), 16)
    bal = int(_rpc(url, 'eth_getBalance', [addr, 'latest'], deadline), 16)
    tb = _rpc(url, 'alchemy_getTokenBalances', [addr, 'erc20'], deadline)
    toks = [t for t in tb.get('tokenBalances', [])
            if t.get('tokenBalance') and int(t['tokenBalance'], 16) > 0]
    tokens = []
    for t in toks[:MAX_TOKENS]:
        meta = {}
        if time.time() < deadline - 6:
            try:
                meta = _rpc(url, 'alchemy_getTokenMetadata', [t['contractAddress']], deadline) or {}
            except ScanError:
                meta = {}
        tokens.append({'contract': t['contractAddress'], 'balanceRaw': str(int(t['tokenBalance'], 16)),
                       'symbol': (meta.get('symbol') or '')[:16], 'decimals': meta.get('decimals')})
    try:
        appr = _approvals(url, chain, addr, head, deadline)
    except ScanError as e:
        appr = {'items': [], 'txScanned': 0, 'truncated': True, 'error': str(e)}
    out = {
        'chain': chain, 'chainId': CHAINS[chain]['chain_id'], 'address': addr, 'block': head,
        'readOnly': True, 'mode': 'Mainnet: read-only check. Rescue is testnet beta only.',
        'delegation7702': {'active': deleg is not None, 'delegate': deleg},
        'isContract': code not in ('0x', '0x0') and deleg is None,
        'nonce': nonce,
        'native': {'symbol': CHAINS[chain]['native'], 'balanceWei': str(bal)},
        'tokens': tokens, 'tokensTotalNonZero': len(toks),
        'approvals': appr['items'],
        'approvalsMeta': {'lookbackDays': LOOKBACK_DAYS, 'txScanned': appr['txScanned'],
                          'truncated': appr['truncated'], 'error': appr.get('error'),
                          'note': 'Only on-chain approve() calls sent by this address are listed. '
                                  'Off-chain permit signatures and older approvals may not appear.'},
        'explorer': CHAINS[chain]['explorer'] + addr,
        'elapsedS': round(time.time() - t0, 2), 'cached': False,
    }
    with _clock:
        if len(_cache) > 5000:
            _cache.clear()
        _cache[key] = (time.time(), out)
    return out


# ---- registro (sin direccion completa) ----
_SALT_FILE = os.path.join(os.path.dirname(__file__), 'data', 'ip_salt')


def _salt():
    try:
        with open(_SALT_FILE, 'rb') as f:
            return f.read()
    except FileNotFoundError:
        s = os.urandom(32)
        os.makedirs(os.path.dirname(_SALT_FILE), exist_ok=True)
        with open(_SALT_FILE, 'wb') as f:
            f.write(s)
        return s


def ip_hash(ip):
    return hashlib.sha256(_salt() + (ip or '').encode()).hexdigest()[:32]


def is_own(ip, ua=''):
    own = {x.strip() for x in os.environ.get('UNSWEEP_OWN_IPS', '').split(',') if x.strip()}
    return (ip in own) or ('unsweep-selftest' in (ua or ''))


def record_scan(chain, s, ip, ua, referer):
    import psycopg
    try:
        with psycopg.connect(PG_DSN, connect_timeout=3) as c:
            c.execute('INSERT INTO unsweep_scans (chain, hallazgo_7702, n_approvals, ip_hash, propio, cached, ua_bot, referer_host)'
                      ' VALUES (%s,%s,%s,%s,%s,%s,%s,%s)',
                      (chain, bool(s['delegation7702']['active']), len(s['approvals']), ip_hash(ip),
                       is_own(ip, ua), bool(s.get('cached')), _is_bot(ua), _host(referer)))
    except Exception:
        pass  # el registro nunca rompe el escaneo


def _is_bot(ua):
    ua = (ua or '').lower()
    return any(b in ua for b in ('bot', 'crawl', 'spider', 'curl', 'python', 'wget', 'headless', 'scrapy', 'httpx'))


def _host(ref):
    from urllib.parse import urlparse
    try:
        return (urlparse(ref or '').hostname or '')[:100] or None
    except ValueError:
        return None
