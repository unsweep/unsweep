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
from web3 import Web3

MAX_EXTRAS = 20
EXTRA_GAS_LIMIT = 120_000
UNVERIFIED_NOTE = 'Unverified tokens, no guarantee, may include scam tokens'
SEL_TRANSFER = '0xa9059cbb'


def _word(x):
    return x[2:].lower().rjust(64, '0') if isinstance(x, str) else hex(int(x))[2:].rjust(64, '0')


def transfer_data(to, amount):
    return SEL_TRANSFER + _word(Web3.to_checksum_address(to)) + _word(int(amount))


def discover_extras(rpc, addr, allowed):
    """rpc(method, params) -> result. allowed: set de checksum de assets_<chain>.json."""
    addr = Web3.to_checksum_address(addr)
    res = rpc('alchemy_getTokenBalances', [addr, 'erc20']) or {}
    out, seen = [], set()
    for tb in res.get('tokenBalances', []) or []:
        try:
            t = Web3.to_checksum_address(tb.get('contractAddress'))
            bal = int(tb.get('tokenBalance') or '0x0', 16)
        except Exception:
            continue
        if bal <= 0 or t in allowed or t in seen:
            continue
        seen.add(t)
        out.append({'address': t, 'balance': str(bal), 'unverified': True, 'value_usd': 0, 'price_usd': 0})
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
        return [], ('sin tokens listados: extras no disponibles' if extras else None)
    ok = []
    for ex in extras:
        if len(ok) >= max_extras:
            break
        g = simulate_extra(estimate, victim, safe, ex, limit)
        if g is not None:
            ok.append({**ex, 'gas': g})
    if not ok:
        return [], 'ningun extra paso la simulacion'
    total_gas = int(base_gas) + sum(e['gas'] for e in ok)
    gas_usd = total_gas * int(gas_price_wei) / 1e18 * float(eth_usd)
    if float(listed_fee_usd) < gas_usd:
        return [], 'la comision de los listados no cubre el gas con extras'
    return ok, None


def extra_lines(selected, bps):
    lines = []
    for e in selected:
        bal = int(e['balance'])
        fee = bal * int(bps) // 10000
        lines.append({'token': e['address'], 'symbol': e.get('symbol', ''), 'decimals': int(e.get('decimals', 18)),
                      'amount': str(bal), 'fee': str(fee), 'minFee': '0', 'net': str(bal - fee), 'unverified': True})
    return lines
