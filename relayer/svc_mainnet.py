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
BUDGET_S = float(os.environ.get('UNSWEEP_MAINNET_BUDGET_S', '14'))  # #1658c: proxy corta a 20 s
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


# M2d-1: inyeccion de fallos SOLO para pruebas locales. Doble llave y nunca dentro de Docker (produccion).
_TEST_FAIL = (os.environ.get('UNSWEEP_TEST_FAIL', '').strip().lower()
              if os.environ.get('UNSWEEP_LOCAL_TEST') == '1' and not os.path.exists('/.dockerenv') else '')
_TEST_ERR = {'rpc': 'rpc unavailable', 'ratelimit': 'rpc rate limited', 'timeout': 'time budget exceeded'}


def _url(chain):
    u = os.environ.get(CHAINS[chain]['env'], '').strip().strip('"').strip("'")
    if not u:
        raise ScanError('chain not configured')
    return u


def _post(url, body, deadline, tries=5):
    if _TEST_FAIL in _TEST_ERR:
        raise ScanError(_TEST_ERR[_TEST_FAIL])
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


def _approvals(url, chain, addr, head, deadline, reasons):
    n0 = len(reasons)
    frm = max(0, head - LOOKBACK_DAYS * 86400 // CHAINS[chain]['block_s'])
    res = _rpc(url, 'alchemy_getAssetTransfers', [{
        'fromBlock': hex(frm), 'toBlock': 'latest', 'fromAddress': addr,
        'category': ['external'], 'order': 'desc', 'maxCount': hex(MAX_TX),
        'excludeZeroValue': False}], deadline) or {}
    if res.get('pageKey') or _TEST_FAIL == 'truncated':
        reasons.append('approval history truncated: page limit of %d transactions reached' % MAX_TX)
    hashes = list(dict.fromkeys(x['hash'] for x in res.get('transfers', [])))[:MAX_TX]
    pairs, scanned, failed = {}, 0, 0
    for i in range(0, len(hashes), BATCH):
        if time.time() > deadline - 3:
            reasons.append('time budget exceeded while reading transactions')
            break
        chunk = hashes[i:i + BATCH]
        batch = [{'jsonrpc': '2.0', 'id': j, 'method': 'eth_getTransactionByHash', 'params': [h]}
                 for j, h in enumerate(chunk)]
        try:
            out = _post(url, batch, deadline)
        except ScanError as e:
            reasons.append('transaction lookup failed: %s' % e)
            break
        if not isinstance(out, list):
            reasons.append('transaction lookup returned an invalid response')
            break
        failed += max(0, len(chunk) - len(out))
        for x in out:
            t = x.get('result') if isinstance(x, dict) else None
            if not t:
                failed += 1
                continue
            scanned += 1
            inp = t.get('input') or ''
            if inp[:10] == SEL_APPROVE and t.get('to') and len(inp) >= 138:
                tok, sp = t['to'].lower(), '0x' + inp[34:74]
                pairs.setdefault((tok, sp), t.get('hash'))
    if failed:
        reasons.append('%d transactions could not be read' % failed)
    live, cfail = [], 0
    for (tok, sp), txh in pairs.items():
        if time.time() > deadline - 1:
            reasons.append('time budget exceeded while checking allowances')
            break
        try:
            v = _rpc(url, 'eth_call', [{'to': tok, 'data': SEL_ALLOWANCE + _word(addr) + _word(sp)}, 'latest'], deadline)
            amt = int(v, 16) if v and v != '0x' else 0
        except (ScanError, ValueError):
            cfail += 1
            continue
        if amt > 0:
            live.append({'token': tok, 'spender': sp, 'allowance': str(amt),
                         'unlimited': amt >= 2 ** 255, 'approveTx': txh})
    if cfail:
        reasons.append('%d allowance checks failed' % cfail)
    return {'items': live, 'txScanned': scanned, 'truncated': len(reasons) > n0}


MAX_TOKEN_PAGES = int(os.environ.get('UNSWEEP_MAINNET_TOKEN_PAGES', '60'))
SEL_BALANCEOF = '0x70a08231'
_DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data')


def _listed(chain):
    """#1658b: tokens de assets_<chainId>.json (se consultan SIEMPRE con balanceOf)."""
    p = os.path.join(_DATA_DIR, 'assets_%d.json' % CHAINS[chain]['chain_id'])
    try:
        with open(p) as f:
            a = json.load(f)
    except FileNotFoundError:
        return []
    return [{'contract': t['address'].lower(), 'symbol': (t.get('symbol') or '')[:16],
             'decimals': t.get('decimals')} for t in a.get('tokens', [])]


TOKENS_SHARE = float(os.environ.get('UNSWEEP_MAINNET_TOKENS_SHARE', '0.6'))  # parte del presupuesto para tokens
BO_BATCH = 50
BO_SMALL = 10
ALT_RPC = {'base': os.environ.get('BASE_RPC_URL_ALT', 'https://mainnet.base.org').strip(),
           'ethereum': os.environ.get('ETH_RPC_URL_ALT', '').strip()}


def _bo_batch(url, addr, contracts, tag, deadline):
    """Un lote eth_call balanceOf -> {contract: raw} solo con las respuestas validas."""
    body = [{'jsonrpc': '2.0', 'id': i, 'method': 'eth_call',
             'params': [{'to': c, 'data': SEL_BALANCEOF + _word(addr)}, tag]}
            for i, c in enumerate(contracts)]
    j = _post(url, body, deadline, tries=2)
    if not isinstance(j, list):
        raise ScanError('rpc error in batch balanceOf')
    by = {x.get('id'): x for x in j if isinstance(x, dict)}
    out = {}
    for i, c in enumerate(contracts):
        r = (by.get(i) or {}).get('result')
        if isinstance(r, str):
            try:
                out[c] = int(r, 16) if r not in ('0x', '') else 0
            except ValueError:
                pass
    return out


def _balance_of(url, alt, addr, contracts, tag, deadline):
    """#1658c: balanceOf por lotes; lo que falle se reintenta UNA vez en lotes pequenos,
    en el RPC alternativo si existe. -> (balances, fallidos)."""
    out = {}
    for k in range(0, len(contracts), BO_BATCH):
        try:
            out.update(_bo_batch(url, addr, contracts[k:k + BO_BATCH], tag, deadline))
        except ScanError:
            pass
    miss = [c for c in contracts if c not in out]
    ru = alt or url
    for k in range(0, len(miss), BO_SMALL):
        if time.time() > deadline - 0.5:
            break
        try:
            out.update(_bo_batch(ru, addr, miss[k:k + BO_SMALL], tag, deadline))
        except ScanError:
            continue
    return out, [c for c in contracts if c not in out]


def _discover(url, addr, deadline):
    """Todas las paginas de alchemy_getTokenBalances -> ({contract: raw>0}, truncated)."""
    found, key, pages = {}, None, 0
    while True:
        params = [addr, 'erc20'] + ([{'pageKey': key}] if key else [])
        r = _rpc(url, 'alchemy_getTokenBalances', params, deadline) or {}
        pages += 1
        for t in r.get('tokenBalances', []):
            b = t.get('tokenBalance')
            if b and b != '0x' and int(b, 16) > 0:
                found[t['contractAddress'].lower()] = int(b, 16)
        key = r.get('pageKey')
        if not key or _TEST_FAIL == 'tokpage1':
            return found, bool(key)
        if pages >= MAX_TOKEN_PAGES or time.time() > deadline - 4:
            return found, True


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
    reasons = []

    def soft(label, fn):
        try:
            return fn()
        except (ScanError, ValueError, TypeError) as e:
            reasons.append('%s failed: %s' % (label, e))
            return None

    head = soft('block number', lambda: int(_rpc(url, 'eth_blockNumber', [], deadline), 16))
    code = soft('EIP-7702 code check', lambda: _rpc(url, 'eth_getCode', [addr, 'latest'], deadline) or '0x')
    deleg = None
    if code is not None and code.lower().startswith(DELEG_PREFIX) and len(code) == 48:
        deleg = '0x' + code[8:48]
    nonce = soft('nonce', lambda: int(_rpc(url, 'eth_getTransactionCount', [addr, 'latest'], deadline), 16))
    bal = soft('native balance', lambda: int(_rpc(url, 'eth_getBalance', [addr, 'latest'], deadline), 16))
    tok_deadline = min(deadline, t0 + BUDGET_S * TOKENS_SHARE)
    tag = hex(head) if head is not None else 'latest'  # mismo bloque que se devuelve en 'block'
    listed = _listed(chain)
    meta_l = {t['contract']: t for t in listed}
    disc = soft('token balances', lambda: _discover(url, addr, tok_deadline))
    idx = disc[0] if disc is not None else {}
    if disc is not None and disc[1]:
        reasons.append('token list truncated: more than %d pages or time budget reached' % MAX_TOKEN_PAGES)
    cands = [t['contract'] for t in listed] + sorted(c for c in idx if c not in meta_l)
    bals, failed = _balance_of(url, ALT_RPC.get(chain), addr, cands, tag, tok_deadline)
    nonzero, unknown = {}, set()
    for c in cands:
        if c in bals:  # eth_call al bloque head manda sobre el indice
            if bals[c] > 0:
                nonzero[c] = bals[c]
        elif c in idx:  # fallo de RPC: nunca desaparece ni queda a 0
            nonzero[c] = idx[c]
            unknown.add(c)
    if failed:
        reasons.append('balanceOf failed for %d tokens after retry (%d kept as unknown/retry)'
                       % (len(failed), len(unknown)))
    order = ([t['contract'] for t in listed if t['contract'] in nonzero]
             + sorted(c for c in nonzero if c not in meta_l))
    tokens, nmeta = [], 0
    for c in order:
        m = meta_l.get(c)
        sym, dec = (m['symbol'], m['decimals']) if m else ('', None)
        if not m and nmeta < MAX_TOKENS and time.time() < deadline - 6:
            nmeta += 1
            try:
                meta = _rpc(url, 'alchemy_getTokenMetadata', [c], deadline) or {}
                sym, dec = (meta.get('symbol') or '')[:16], meta.get('decimals')
            except ScanError:
                pass  # solo cosmetico (simbolo/decimales): no afecta a la completitud
        tokens.append({'contract': c, 'balanceRaw': str(nonzero[c]), 'symbol': sym,
                       'decimals': dec, 'listed': bool(m),
                       'balanceStatus': 'unknown/retry' if c in unknown else 'ok'})
    appr_err = None
    if head is None:
        appr = {'items': [], 'txScanned': 0, 'truncated': True}
        reasons.append('approvals not checked: no block number')
    else:
        try:
            appr = _approvals(url, chain, addr, head, deadline, reasons)
        except ScanError as e:
            appr_err = str(e)
            appr = {'items': [], 'txScanned': 0, 'truncated': True}
            reasons.append('approval history failed: %s' % e)
    status = 'complete' if not reasons else 'incomplete'
    out = {
        'status': status, 'partial': status != 'complete', 'incompleteReasons': reasons,
        'tokensUnknown': len(unknown),
        'chain': chain, 'chainId': CHAINS[chain]['chain_id'], 'address': addr, 'block': head,
        'readOnly': True, 'mode': 'Mainnet: read-only check. Rescue is testnet beta only.',
        'delegation7702': {'active': (deleg is not None) if code is not None else None, 'delegate': deleg},
        'isContract': (code not in ('0x', '0x0') and deleg is None) if code is not None else None,
        'nonce': nonce,
        'native': {'symbol': CHAINS[chain]['native'], 'balanceWei': str(bal) if bal is not None else None},
        'tokens': tokens, 'tokensTotalNonZero': len(nonzero),
        'approvals': appr['items'],
        'approvalsMeta': {'lookbackDays': LOOKBACK_DAYS, 'txScanned': appr['txScanned'],
                          'truncated': appr['truncated'], 'error': appr_err,
                          'note': 'Only on-chain approve() calls sent by this address are listed. '
                                  'Off-chain permit signatures and older approvals may not appear.'},
        'explorer': CHAINS[chain]['explorer'] + addr,
        'elapsedS': round(time.time() - t0, 2), 'cached': False,
    }
    if status == 'complete':  # nunca se cachea un resultado incompleto
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
                      (chain, bool(s['delegation7702'].get('active')), len(s['approvals']), ip_hash(ip),
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
