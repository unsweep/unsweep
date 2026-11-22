"""UNSWEEP M2b escaner y simulacion (neto y comision). Solo lectura; nunca firma."""
import os
from web3 import Web3

from relayer import Quote, PolicyError, check_policy
import policy as P
from svc_core import w3, abi, assets, log, CHAIN_ID, DELEGATE, CONFIG, ETH_USD
import oracle as O
from relayer import TESTNETS
import extras as EX


def _token_px(a, t):
    """Precio USD por latestRoundData (fail-closed). price_usd fijo SOLO en testnet sin feed."""
    if t.get('feed'):
        return O.token_price_usd(w3, a, t)
    if CHAIN_ID in TESTNETS and 'price_usd' in t:
        return float(t['price_usd'])
    raise O.OracleError('no price feed for %s' % t.get('symbol', t.get('address')))


def _eth_usd():
    a = assets()
    if a.get('eth_usd_feed'):
        return O.eth_usd(w3, a)
    if CHAIN_ID in TESTNETS:
        return ETH_USD  # ESTIMACION fija solo testnet
    raise O.OracleError('no ETH/USD feed configured')

APPROVAL_LOOKBACK = int(os.environ.get('UNSWEEP_APPROVAL_LOOKBACK', '9000'))
LOG_CHUNK = 2000

ERC20 = [{'name': 'balanceOf', 'type': 'function', 'stateMutability': 'view', 'inputs': [{'name': 'a', 'type': 'address'}], 'outputs': [{'type': 'uint256'}]},
         {'name': 'allowance', 'type': 'function', 'stateMutability': 'view', 'inputs': [{'name': 'o', 'type': 'address'}, {'name': 's', 'type': 'address'}], 'outputs': [{'type': 'uint256'}]}]
ERC721 = [{'name': 'ownerOf', 'type': 'function', 'stateMutability': 'view', 'inputs': [{'name': 'i', 'type': 'uint256'}], 'outputs': [{'type': 'address'}]},
          {'name': 'isApprovedForAll', 'type': 'function', 'stateMutability': 'view', 'inputs': [{'name': 'o', 'type': 'address'}, {'name': 'op', 'type': 'address'}], 'outputs': [{'type': 'bool'}]}]


def h0x(b):
    s = b.hex() if hasattr(b, 'hex') else str(b)
    return s if s.startswith('0x') else '0x' + s


T_APPROVAL = h0x(Web3.keccak(text='Approval(address,address,uint256)'))
T_APPROVAL_ALL = h0x(Web3.keccak(text='ApprovalForAll(address,address,bool)'))
config_c = w3.eth.contract(address=CONFIG, abi=abi('UnsweepConfig.sol', 'UnsweepConfig'))


def delegation_of(addr):
    code = bytes(w3.eth.get_code(addr))
    if len(code) == 23 and code[:3] == b'\xef\x01\x00':
        return Web3.to_checksum_address(code[3:])
    return None


class ApprovalsError(Exception):
    """#92: approvals no verificables (429/RPC caido). NUNCA se devuelve lista vacia por error."""


_AP_W3 = []


def _ap_providers():
    """#92: RPC de pago (BASE_RPC_URL) PRINCIPAL en approvals; publico (w3) solo como respaldo."""
    if not _AP_W3:
        u = os.environ.get('BASE_RPC_URL', '').strip().strip('"').strip("'")
        if u and CHAIN_ID == 8453:
            _AP_W3.append(Web3(Web3.HTTPProvider(u, request_kwargs={'timeout': 20})))
        _AP_W3.append(w3)
    return _AP_W3


def _is_429(e):
    r = getattr(e, 'response', None)
    m = str(e).lower()
    return getattr(r, 'status_code', None) == 429 or 'too many requests' in m or 'rate limit' in m


def _ap_call(fn):
    """fn(web3) en el RPC principal y, si falla, en el respaldo. Error visible y sin URL."""
    rl = False
    for p in _ap_providers():
        try:
            return fn(p)
        except Exception as e:
            rl = rl or _is_429(e)
            log.warning('approvals rpc %s: %s', 'public' if p is w3 else 'paid', type(e).__name__)
    raise ApprovalsError('rpc rate limited (HTTP 429)' if rl else 'rpc unavailable')


# #1152: eth_getLogs de approvals contra un RPC publico que acepta rangos de 2000 bloques
# filtrando por 'address' = contratos de assets_<chain>.json. Alchemy Free (BASE_RPC_URL) limita
# getLogs a 10 bloques (HTTP 400) y el respaldo publico sin filtro devolvia 429.
# El resto de llamadas (allowance/isApprovedForAll, saldos) siguen en el RPC actual.
APPROVAL_LOGS_RPC = {
    8453: 'https://base-rpc.publicnode.com',
    42161: 'https://arbitrum-one-rpc.publicnode.com',  # parametrizado; NO activo (publicnode exige token para 2000 bloques en Arbitrum)
}
APPROVAL_LOGS_ENABLED = {8453}
LOGS_ADDR_GROUP = 10  # publicnode: 'A maximum of 10 addresses is allowed' (HTTP 403)
CHUNK_RETRIES = 1
CHUNK_BACKOFF_S = 0.5
_LOGS_W3 = {}


def _logs_w3(chain_id=None):
    """Web3 del RPC de logs de approvals para la red, o None si la red no esta activada."""
    cid = CHAIN_ID if chain_id is None else chain_id
    if cid not in APPROVAL_LOGS_ENABLED or cid not in APPROVAL_LOGS_RPC:
        return None
    if cid not in _LOGS_W3:
        _LOGS_W3[cid] = Web3(Web3.HTTPProvider(APPROVAL_LOGS_RPC[cid], request_kwargs={'timeout': 20}))
    return _LOGS_W3[cid]


def _asset_contracts(a=None):
    a = assets() if a is None else a
    out = []
    for t in list(a.get('tokens', [])) + list(a.get('nfts', [])):
        c = Web3.to_checksum_address(t['address'])
        if c not in out:
            out.append(c)
    return out


def plan_chunks(head, lookback=None, chunk=None):
    """Rangos [frm, to] inclusivos que cubren (head-lookback .. head) en trozos de 'chunk' bloques."""
    lookback = APPROVAL_LOOKBACK if lookback is None else lookback
    chunk = LOG_CHUNK if chunk is None else chunk
    start, out = max(0, head - lookback), []
    frm = start
    while frm <= head:
        to = min(head, frm + chunk - 1)
        out.append((frm, to))
        frm = to + 1
    return out


def _get_logs_retry(p, flt, sleep=None):
    """get_logs con UN reintento tras backoff corto. Error visible y sin URL."""
    import time
    sleep = time.sleep if sleep is None else sleep
    last = None
    for i in range(CHUNK_RETRIES + 1):
        try:
            return p.eth.get_logs(flt)
        except Exception as e:
            last = e
            log.warning('approvals logs chunk try %d: %s', i + 1, type(e).__name__)
            if i < CHUNK_RETRIES:
                sleep(CHUNK_BACKOFF_S * (i + 1))
    raise ApprovalsError('rpc rate limited (HTTP 429)' if _is_429(last) else 'rpc unavailable')


def live_approvals(addr, progress=None):
    out, seen = [], set()
    lp = _logs_w3()
    owner_topic = '0x' + '0' * 24 + addr[2:].lower()
    if lp is not None:
        try:
            head = lp.eth.block_number
        except Exception:
            head = _ap_call(lambda p: p.eth.block_number)
        contracts = _asset_contracts()
        groups = [contracts[i:i + LOGS_ADDR_GROUP] for i in range(0, len(contracts), LOGS_ADDR_GROUP)] or [[]]
    else:
        head = _ap_call(lambda p: p.eth.block_number)
        groups = [None]  # red sin RPC de logs activado: comportamiento anterior (sin filtro address)
    chunks = plan_chunks(head)
    total = len(chunks) * 2 * len(groups)
    n = 0
    for topic in (T_APPROVAL, T_APPROVAL_ALL):
        for frm, to in chunks:
            for g in groups:
                flt = {'fromBlock': frm, 'toBlock': to, 'topics': [topic, owner_topic]}
                if g is not None:
                    if not g:
                        n += 1
                        continue
                    flt['address'] = g
                    logs = _get_logs_retry(lp, flt)
                else:
                    logs = _ap_call(lambda p, f=flt: p.eth.get_logs(f))
                n += 1
                if progress:
                    progress(n, total)
                for lg in logs:
                    if len(lg['topics']) < 3:
                        continue
                    spender = Web3.to_checksum_address('0x' + h0x(lg['topics'][2])[-40:])
                    key = (lg['address'], spender, topic)
                    if key in seen:
                        continue
                    seen.add(key)
                    try:
                        if topic == T_APPROVAL_ALL:
                            c = _ap_providers()[0].eth.contract(address=lg['address'], abi=ERC721)
                            if c.functions.isApprovedForAll(addr, spender).call():
                                out.append({'token': lg['address'], 'spender': spender, 'type': 'ApprovalForAll'})
                        else:
                            c = _ap_providers()[0].eth.contract(address=lg['address'], abi=ERC20)
                            amt = c.functions.allowance(addr, spender).call()
                            if amt > 0:
                                out.append({'token': lg['address'], 'spender': spender, 'type': 'ERC20', 'amount': str(amt)})
                    except Exception as e:
                        if _is_429(e):
                            raise ApprovalsError('rpc rate limited (HTTP 429)') from None
                        # ERC-721 Approval (3 topics indexados) u otros: se ignoran
    return out


def scan(addr):
    addr = Web3.to_checksum_address(addr)
    a = assets()
    allowed = O.allowlist(a)  # misma allowlist que quote/rescate (assets_<chain>.json)
    tokens, nfts = [], []
    for t in a['tokens']:
        if Web3.to_checksum_address(t['address']) not in allowed:
            continue
        bal = w3.eth.contract(address=Web3.to_checksum_address(t['address']), abi=ERC20).functions.balanceOf(addr).call()
        if bal > 0:
            tokens.append({**t, 'balance': str(bal), 'price_usd': _token_px(a, t), 'price_feeds': _token_feeds(a, t)})
    for n in a['nfts']:
        c = w3.eth.contract(address=Web3.to_checksum_address(n['address']), abi=ERC721)
        for i in n.get('ids', []):
            try:
                if c.functions.ownerOf(int(i)).call() == addr:
                    nfts.append({'address': n['address'], 'symbol': n.get('symbol', ''), 'id': str(i)})
            except Exception:
                pass
    try:
        aps, ap_err = live_approvals(addr), None
    except ApprovalsError as e:
        aps, ap_err = [], str(e)  # #92: error visible, nunca lista vacia silenciosa
    deleg = delegation_of(addr)
    return {'address': addr, 'chainId': CHAIN_ID, 'eth_wei': str(w3.eth.get_balance(addr)),
            'nonce': w3.eth.get_transaction_count(addr, 'pending'),
            'delegation7702': deleg, 'delegatedToUnsweep': deleg == DELEGATE,
            'tokens': tokens, 'nfts': nfts, 'approvals': aps, 'approvalsError': ap_err,
            'rescuable': bool(tokens or nfts), 'extras': scan_extras(addr)}


def _token_feeds(a, t):
    """#98: [{'feed','age_s','heartbeat_s'}] de cada feed Chainlink usado (compuestos incluidos); None sin feed -> >10k se rechaza."""
    if t.get('feed'):
        return O.token_price_feeds(w3, a, t)
    return None


def _high_value_items(toks):
    """#98 fail-closed: precio y antiguedad por feed releidos en servidor desde assets (nunca del cliente)."""
    a = assets()
    by = {Web3.to_checksum_address(x['address']): x for x in a['tokens']}
    items = []
    for (t, _b, _d, _p, u) in toks:
        cfg_t = by.get(Web3.to_checksum_address(t['address']))
        if not cfg_t or not cfg_t.get('feed'):
            raise PolicyError('token sin feed Chainlink verificable en rescate >10.000 USD')
        items.append({'symbol': cfg_t.get('symbol', ''), 'value_usd': u,
                      'price_usd': O.token_price_usd(w3, a, cfg_t),
                      'price_feeds': O.token_price_feeds(w3, a, cfg_t)})
    return items, O.eur_usd(w3, a)


def _safe_sym(x):
    return ''.join(ch for ch in str(x or '') if ch.isalnum())[:12]


ERC20_META = [{'name': 'decimals', 'type': 'function', 'stateMutability': 'view', 'inputs': [], 'outputs': [{'type': 'uint8'}]},
              {'name': 'symbol', 'type': 'function', 'stateMutability': 'view', 'inputs': [], 'outputs': [{'type': 'string'}]}]


def scan_extras(addr):
    """#985: ERC-20 fuera de assets -> unverified, value_usd 0. Fail-soft: cualquier error -> []."""
    try:
        allowed = O.allowlist(assets())
        rpc = lambda m, p: w3.provider.make_request(m, p).get('result')
        exs = EX.discover_extras(rpc, addr, allowed)
    except Exception as e:
        log.warning('extras no disponibles: %s', type(e).__name__)
        return []
    for e in exs[:50]:
        c = w3.eth.contract(address=e['address'], abi=ERC20_META)
        try:
            e['decimals'] = int(c.functions.decimals().call())
        except Exception:
            e['decimals'] = 18
        try:
            e['symbol'] = _safe_sym(c.functions.symbol().call())
        except Exception:
            e['symbol'] = ''
    return exs[:50]


def quote(s, gas=1_500_000, extras=None):
    """Cotizacion M4: tramos 15/10/5 %; en Ethereum minimo = gas x1.5 (va firmado como minFees)."""
    toks = []
    allowed = O.allowlist(assets())  # misma allowlist que scan y check_allowlist (rescate)
    bad = [str(t.get('address'))[:42] for t in s['tokens']
           if not Web3.is_address(str(t.get('address'))) or Web3.to_checksum_address(t['address']) not in allowed]
    if bad:
        raise PolicyError('token fuera de la allowlist: %s' % ', '.join(bad[:5]))
    for t in s['tokens']:
        bal = int(t['balance']); dec = int(t.get('decimals', 18)); px = float(t.get('price_usd', 0))
        toks.append((t, bal, dec, px, bal / 10**dec * px))
    rescued_usd = sum(x[4] for x in toks) + sum(float(n.get('value_usd', 0)) for n in s['nfts'])
    gas_cost_usd = gas * w3.eth.gas_price / 1e18 * _eth_usd()
    try:
        plan = P.fee_plan(CHAIN_ID, rescued_usd, gas_cost_usd); ok, why = True, None
    except PolicyError as e:
        plan, ok, why = None, False, str(e)
    bps = plan.max_fee_bps if plan else 0
    # minimo de Ethereum (#718 p.3): UN solo token (el de mayor valor) lleva minFee, el resto 0.
    # Su minFee cubre solo lo que falte tras el tramo del resto, de modo que la comision total es
    # max(tramo, gas x1.5) y no se multiplica por el numero de tokens. Acotado a su saldo.
    big = -1
    if plan and plan.min_fee_usd > 0 and toks:
        try:  # #731: USDC/WETH/DAI/USDT > mayor valor sin comision al transferir > nunca FOT
            big, _rule = P.pick_min_fee_token(CHAIN_ID, [{'address': t['address'], 'value_usd': u,
                                              'fee_on_transfer': t.get('fee_on_transfer')}
                                             for (t, _b, _d, _p, u) in toks], plan.min_fee_usd, bps)
        except P.NotViableOnEthereum as e:
            ok, why = False, str(e)
    rest_tier_usd = sum((bal * bps // 10000) / 10**dec * px
                        for k, (_, bal, dec, px, _) in enumerate(toks) if k != big)
    lines, fee_usd = [], 0.0
    for k, (t, bal, dec, px, _) in enumerate(toks):
        mn = 0
        need_usd = (plan.min_fee_usd - rest_tier_usd) if plan else 0.0
        if plan and plan.min_fee_usd > 0 and k == big and px > 0 and need_usd > 0:
            mn = min(bal, int(need_usd / px * 10**dec) + 1)
        fee = max(bal * bps // 10000, mn)
        fee_usd += fee / 10**dec * px
        lines.append({'token': t['address'], 'symbol': t.get('symbol', ''), 'decimals': dec, 'amount': str(bal),
                      'fee': str(fee), 'minFee': str(mn), 'net': str(bal - fee)})
    n_nft = len(s['nfts'])  # #66: los NFTs viajan gratis con un rescate de ERC-20
    if ok and n_nft and not toks:
        ok, why = False, 'rescate solo de NFTs no disponible (los NFTs viajan gratis junto a tokens ERC-20)'
    q = Quote(rescued_usd=rescued_usd, fee_usd=fee_usd, gas_cost_usd=gas_cost_usd)
    if ok and CHAIN_ID not in P.MAINNETS:
        try:
            check_policy(q)
        except PolicyError as e:
            ok, why = False, str(e)
    if ok and CHAIN_ID in P.MAINNETS and P.needs_extra_checks(rescued_usd):
        # #927(a)+(b) con #98: heartbeat por feed, lista de alto valor y bandas de stablecoins/EURC; si falla, no se ofrece
        try:
            items, eur = _high_value_items(toks)
            P.check_high_value(rescued_usd, items, eur_usd=eur)
        except PolicyError as e:
            ok, why = False, str(e)
        except Exception as e:  # fail-closed ante cualquier error del oraculo
            ok, why = False, 'precio no verificable (%s)' % type(e).__name__
    # #985: extras sin garantia; no alteran rescued_usd, tope ni umbral (value_usd 0)
    ex_reason, ex_gas, ex_lines = None, 0, []
    if extras:
        want = set()
        for x in extras:
            try:
                want.add(Web3.to_checksum_address(str(x)))
            except Exception:
                pass
        avail = [e for e in s.get('extras', []) if e['address'] in want]
        if not ok:
            ex_reason = 'cotizacion de listados no valida: extras excluidos'
        else:
            gp = w3.eth.gas_price
            est = lambda tx: w3.eth.estimate_gas(tx)
            call = lambda tx: w3.eth.call(tx)
            sel, ex_reason = EX.select_extras((call, est), s['address'], s.get('safe') or s['address'], avail, len(toks),
                                              fee_usd, gas, gp, _eth_usd())
            ex_lines = EX.extra_lines(sel, bps)
            ex_gas = sum(e['gas'] for e in sel)
    lines = lines + ex_lines
    has_min = any(l.get('minFee', '0') != '0' for l in lines)
    if not has_min:
        for l in lines: l.pop('minFee', None)
    # sin datos de gas en la respuesta al usuario (gas interno)
    fee_pct = round(fee_usd / rescued_usd * 100, 2) if rescued_usd > 0 else 0.0
    return {'feeBps': bps, 'maxFeeBps': bps, 'lines': lines, 'nfts': n_nft,
            'rescued_usd': round(rescued_usd, 4), 'fee_usd': round(fee_usd, 4), 'fee_pct': fee_pct, 'policy_ok': ok, 'policy_reason': why,
            'extra_checks': P.needs_extra_checks(rescued_usd),
            'breakdown': P.breakdown([l for l in lines if not l.get('unverified')], rescued_usd, fee_usd),
            'extras_reason': ex_reason, 'extras_note': EX.UNVERIFIED_NOTE if ex_lines else None}, q
