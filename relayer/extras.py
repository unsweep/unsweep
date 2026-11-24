"""#985 Tokens extra (no listados) SIN garantia. Logica pura e inyectable (testeable en fork).

Reglas:
- Descubrimiento: alchemy_getTokenBalances del RPC actual; lo que no esta en assets_<chain>.json
  va a 'extras' con unverified=True y value_usd=0 (NO cuenta para el tope 100k ni el umbral 10k).
- Solo se incluyen si hay al menos un token listado seleccionado.
- Cada extra se simula POR SEPARADO (eth_call de transfer desde la EOA + estimateGas, acotado por
  EXTRA_GAS_LIMIT); se excluye el que revierte o supera el limite.
- Maximo MAX_EXTRAS.
- Si la comision (USD) de los listados no cubre el gas total con extras -> se excluyen TODOS.
- Comision de extras en especie al mismo bps, minFee 0.
No modifica contratos ni firma nada.
"""
import logging
import time

from web3 import Web3

log = logging.getLogger(__name__)

MAX_EXTRAS = 20
EXTRA_GAS_LIMIT = 120_000
UNVERIFIED_NOTE = 'Unverified tokens, no guarantee, may include scam tokens'
SEL_TRANSFER = '0xa9059cbb'
MAX_PAGES = 5  # #1646: tope duro de paginas pageKey
MAX_TOKENS_SCANNED = 500  # #1646: tope duro de tokenBalances leidos
EXTRAS_TIME_BUDGET = 20.0  # s totales; se comprueba antes de cada pagina


def _word(x):
    return x[2:].lower().rjust(64, '0') if isinstance(x, str) else hex(int(x))[2:].rjust(64, '0')


def transfer_data(to, amount):
    return SEL_TRANSFER + _word(Web3.to_checksum_address(to)) + _word(int(amount))


def discover_extras(rpc, addr, allowed, max_pages=None, max_tokens=None, time_budget=None, _now=None):
    """rpc(method, params) -> result. allowed: set de checksum de assets_<chain>.json.
    #1646/#559: pagina con pageKey (alchemy_getTokenBalances) con topes duros: max_pages paginas,
    max_tokens tokenBalances leidos y time_budget segundos totales (se comprueba antes de cada pagina).
    Alcanzar un tope NO es error: devuelve lo acumulado. Un error de rpc se propaga (fail-soft en scan_extras)."""
    max_pages = MAX_PAGES if max_pages is None else max_pages
    max_tokens = MAX_TOKENS_SCANNED if max_tokens is None else max_tokens
    time_budget = EXTRAS_TIME_BUDGET if time_budget is None else time_budget
    now = _now or time.monotonic
    addr = Web3.to_checksum_address(addr)
    t0 = now()
    out, seen, key, scanned = [], set(), None, 0
    for page in range(max_pages):
        if page and now() - t0 >= time_budget:
            log.warning('extras: presupuesto de tiempo %.0fs agotado tras %d paginas', time_budget, page)
            break
        params = [addr, 'erc20'] + ([{'pageKey': key}] if key else [])
        res = rpc('alchemy_getTokenBalances', params) or {}
        for tb in res.get('tokenBalances', []) or []:
            if scanned >= max_tokens:
                break
            scanned += 1
            try:
                t = Web3.to_checksum_address(tb.get('contractAddress'))
                bal = int(tb.get('tokenBalance') or '0x0', 16)
            except Exception:
                continue
            if bal <= 0 or t in allowed or t in seen:
                continue
            seen.add(t)
            out.append({'address': t, 'balance': str(bal), 'unverified': True, 'value_usd': 0, 'price_usd': 0})
        key = res.get('pageKey')
        if not key:
            break
        if scanned >= max_tokens:
            log.warning('extras: tope de %d tokens alcanzado (quedan paginas)', max_tokens)
            break
    else:
        if key:
            log.warning('extras: tope de %d paginas alcanzado (quedan paginas)', max_pages)
    return out


def simulate_extra(sim, victim, safe, ex, limit=EXTRA_GAS_LIMIT):
    """sim = (call, estimate) o solo estimate. call(tx)->bytes (eth_call de transfer; lanza si revierte).
    Se excluye (None) si revierte, si devuelve false o si el gas supera el limite."""
    call, estimate = sim if isinstance(sim, tuple) else (None, sim)
    tx = {'from': Web3.to_checksum_address(victim), 'to': ex['address'],
          'data': transfer_data(safe, ex['balance']), 'gas': hex(limit)}
    try:
        if call is not None:
            ret = bytes(call(tx) or b'')
            if len(ret) not in (0, 32) or (len(ret) == 32 and int.from_bytes(ret, 'big') != 1):
                return None
        g = int(estimate(tx))
    except Exception:
        return None
    return g if 0 < g <= limit else None


def select_extras(estimate, victim, safe, extras, n_listed, listed_fee_usd, base_gas, gas_price_wei, eth_usd,
                  limit=EXTRA_GAS_LIMIT, max_extras=MAX_EXTRAS):
    """Devuelve (seleccionados, motivo). seleccionados lleva 'gas' por extra."""
    if not n_listed or not extras:
        return [], ('no listed tokens: extras unavailable' if extras else None)
    ok = []
    for ex in extras:
        if len(ok) >= max_extras:
            break
        g = simulate_extra(estimate, victim, safe, ex, limit)
        if g is not None:
            ok.append({**ex, 'gas': g})
    if not ok:
        return [], 'no extra token passed simulation'
    total_gas = int(base_gas) + sum(e['gas'] for e in ok)
    gas_usd = total_gas * int(gas_price_wei) / 1e18 * float(eth_usd)
    if float(listed_fee_usd) < gas_usd:
        return [], 'listed token fee does not cover gas with extras'
    return ok, None


def extra_lines(selected, bps):
    lines = []
    for e in selected:
        bal = int(e['balance'])
        fee = bal * int(bps) // 10000
        lines.append({'token': e['address'], 'symbol': e.get('symbol', ''), 'decimals': int(e.get('decimals', 18)),
                      'amount': str(bal), 'fee': str(fee), 'minFee': '0', 'net': str(bal - fee), 'unverified': True})
    return lines
