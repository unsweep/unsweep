# #1690 (3): contratos ERC-20 anadidos a mano en Step 2 (max 3).
# Solo si el scan tiene un token LISTADO con valor. eth_getCode/balanceOf/decimals/symbol por eth_call
# directo al RPC del relayer (UNSWEEP_RPC; decision #1690(a), Alchemy solo en discover_extras), fail-soft por contrato. Los aceptados entran en s['extras'] como
# unverified, value_usd 0, y siguen la MISMA tuberia: quote -> select_extras -> simulate_extra.
import re

from eth_abi import decode
from web3 import Web3

from relayer import PolicyError

MANUAL_MAX = 3
MANUAL_TIMEOUT = 8
SEL_BALANCEOF = '0x70a08231'
SEL_DECIMALS = '0x313ce567'
SEL_SYMBOL = '0x95d89b41'
_HEX = re.compile(r'^0x[0-9a-fA-F]{40}$')
DISABLED_REASON = 'requires at least one listed token with value in Step 1'


class ManualInputError(PolicyError):
    pass


def parse_contracts(raw):
    if raw is None:
        return []
    if isinstance(raw, str):
        items = [x for x in re.split(r'[\s,;]+', raw.strip()) if x]
    elif isinstance(raw, (list, tuple)):
        items = [str(x).strip() for x in raw if str(x).strip()]
    else:
        raise ManualInputError('invalid format: address list expected')
    if len(items) > MANUAL_MAX:
        raise ManualInputError('maximum %d contracts' % MANUAL_MAX)
    out = []
    for x in items:
        if not _HEX.match(x):
            raise ManualInputError('invalid address format: %s' % x[:44])
        if not Web3.is_checksum_address(x):
            raise ManualInputError('invalid EIP-55 checksum: %s' % x)
        if x in out:
            raise ManualInputError('duplicate address: %s' % x)
        out.append(x)
    return out


def listed_value_usd(s):
    v = 0.0
    for t in (s or {}).get('tokens', []) or []:
        try:
            v += int(t.get('balance', 0)) / 10 ** int(t.get('decimals', 18)) * float(t.get('price_usd', 0) or 0)
        except Exception:
            continue
    return v


def manual_enabled(s):
    ok = listed_value_usd(s) > 0
    return ok, (None if ok else DISABLED_REASON)


def _bytes(r):
    if not isinstance(r, str) or not r.startswith('0x'):
        raise ValueError('respuesta no hex')
    return bytes.fromhex(r[2:])


def _clean(x):
    return ''.join(ch for ch in str(x) if ch.isalnum())[:12]


def decode_symbol(b):
    if len(b) >= 64:
        try:
            return _clean(decode(['string'], b)[0])
        except Exception:
            pass
    if len(b) == 32:
        return _clean(b.rstrip(b'\x00').decode('utf-8', 'ignore'))
    return ''


def _call(rpc, to, data):
    return _bytes(rpc('eth_call', [{'to': to, 'data': data}, 'latest']))


def probe(rpc, holder, token):
    # (extra, None) o (None, motivo). Nunca lanza.
    try:
        code = rpc('eth_getCode', [token, 'latest'])
    except Exception as e:
        return None, 'RPC unavailable (%s)' % type(e).__name__
    if not isinstance(code, str) or code.lower() in ('', '0x', '0x0'):
        return None, 'no contract code at this address'
    try:
        b = _call(rpc, token, SEL_BALANCEOF + holder[2:].lower().rjust(64, '0'))
        d = _call(rpc, token, SEL_DECIMALS)
    except Exception:
        return None, 'not an ERC-20 (balanceOf/decimals failed)'
    if len(b) != 32 or len(d) != 32:
        return None, 'not an ERC-20 (non-ABI response)'
    dec = int.from_bytes(d, 'big')
    if dec > 255:
        return None, 'not an ERC-20 (invalid decimals)'
    bal = int.from_bytes(b, 'big')
    if bal <= 0:
        return None, 'zero balance'
    try:
        sym = decode_symbol(_call(rpc, token, SEL_SYMBOL))
    except Exception:
        return None, 'not an ERC-20 (symbol failed)'
    if not sym:
        return None, 'not an ERC-20 (invalid symbol)'
    return {'address': token, 'balance': str(bal), 'decimals': dec, 'symbol': sym, 'unverified': True,
            'value_usd': 0, 'price_usd': 0, 'manual': True}, None


def resolve(rpc, holder, contracts, allowed, existing=()):
    # allowed: checksum de la lista verificada; existing: extras ya detectados por el scan.
    holder = Web3.to_checksum_address(holder)
    ex = {Web3.to_checksum_address(e['address']) if isinstance(e, dict) else Web3.to_checksum_address(e) for e in existing}
    acc, rej = [], []
    for t in contracts:
        if t in allowed:
            rej.append({'address': t, 'reason': 'already in verified token list'}); continue
        if t in ex:
            rej.append({'address': t, 'reason': 'already detected in extras: select it in Step 1'}); continue
        e, why = probe(rpc, holder, t)
        if e is None:
            rej.append({'address': t, 'reason': why})
        else:
            acc.append(e)
    return acc, rej
