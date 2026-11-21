"""Precios on-chain Chainlink (latestRoundData) para UNSWEEP. FAIL-CLOSED, sin API externa.

Rechaza (OracleError, subclase de PolicyError) si: error RPC, answer<=0, answeredInRound<roundId,
updatedAt==0, antiguedad > heartbeat del feed (directorio oficial Chainlink), o decimales on-chain distintos.
La antiguedad se mide SIEMPRE con el timestamp del ultimo bloque de la cadena (nunca el reloj local).
La cache nunca sirve un dato caducado: en cada acierto se revalida updatedAt contra el bloque actual.
"""
import time
from web3 import Web3

from policy import PolicyError

AGG_ABI = [
    {'name': 'latestRoundData', 'type': 'function', 'stateMutability': 'view', 'inputs': [],
     'outputs': [{'name': 'roundId', 'type': 'uint80'}, {'name': 'answer', 'type': 'int256'},
                 {'name': 'startedAt', 'type': 'uint256'}, {'name': 'updatedAt', 'type': 'uint256'},
                 {'name': 'answeredInRound', 'type': 'uint80'}]},
    {'name': 'decimals', 'type': 'function', 'stateMutability': 'view', 'inputs': [],
     'outputs': [{'type': 'uint8'}]},
    {'name': 'description', 'type': 'function', 'stateMutability': 'view', 'inputs': [],
     'outputs': [{'type': 'string'}]},
]
CACHE_TTL = 15  # segundos (monotonic) para refrescar latestRoundData; NO decide la frescura
_cache = {}


class OracleError(PolicyError):
    pass


def _now(w3):
    """Timestamp del ultimo bloque. Sin fallback al reloj local: si falla, fail-closed."""
    try:
        return int(w3.eth.get_block('latest')['timestamp'])
    except Exception as e:
        raise OracleError('chain time unavailable (%s)' % type(e).__name__) from None


def _check_age(now, upd, heartbeat):
    age = int(now) - int(upd)
    if age > int(heartbeat):
        raise OracleError('price feed stale (%ds > heartbeat %ds)' % (age, int(heartbeat)))


def validate_round(rid, ans, upd, air, heartbeat, now):
    """Validacion pura de una ronda; lanza OracleError (PolicyError)."""
    if ans <= 0:
        raise OracleError('price feed answer <= 0')
    if air < rid:
        raise OracleError('price feed round incomplete (answeredInRound < roundId)')
    if upd == 0:
        raise OracleError('price feed not updated')
    _check_age(now, upd, heartbeat)


def read_feed(w3, feed, heartbeat, decimals=None, now=None):
    """Devuelve el precio (float) del feed o lanza OracleError. Nunca devuelve un valor por defecto."""
    key = Web3.to_checksum_address(feed)
    hit = _cache.get(key)
    if hit and time.monotonic() - hit['at'] < CACHE_TTL:
        t = now if now is not None else _now(w3)
        _check_age(t, hit['upd'], heartbeat)  # la cache nunca sirve datos caducados
        return hit['px']
    _cache.pop(key, None)
    try:
        c = w3.eth.contract(address=key, abi=AGG_ABI)
        rid, ans, _st, upd, air = c.functions.latestRoundData().call()
        dec = int(c.functions.decimals().call())
    except Exception as e:
        raise OracleError('price feed unavailable (%s)' % type(e).__name__) from None
    if decimals is not None and dec != int(decimals):
        raise OracleError('price feed decimals mismatch')
    t = now if now is not None else _now(w3)
    validate_round(int(rid), int(ans), int(upd), int(air), heartbeat, t)
    px = int(ans) / 10 ** dec
    _cache[key] = {'at': time.monotonic(), 'px': px, 'upd': int(upd)}
    return px


def eth_usd(w3, cfg):
    f = cfg['eth_usd_feed']
    return read_feed(w3, f['address'], f['heartbeat'], f.get('decimals'))


def token_price_usd(w3, cfg, tok):
    """Precio USD de un token de la lista. feed USD directo, o feed X/ETH * ETH/USD."""
    if Web3.to_checksum_address(tok['address']) not in allowlist(cfg):
        raise PolicyError('token fuera de la allowlist')
    f = tok.get('feed')
    if not f:
        raise OracleError('no price feed for token')
    px = read_feed(w3, f['address'], f['heartbeat'], f.get('decimals'))
    if f.get('quote') == 'ETH':
        px *= eth_usd(w3, cfg)
    elif f.get('quote') != 'USD':
        raise OracleError('unsupported feed quote')
    return px


def token_price_age_s(w3, cfg, tok, now=None):
    """#927(a): antiguedad (s) del dato mas viejo usado para valorar tok (feed del token y, si cotiza en ETH,
    tambien ETH/USD). Valida antes con token_price_usd (fail-closed) y lee el updatedAt cacheado."""
    token_price_usd(w3, cfg, tok)
    f = tok['feed']
    feeds = [f['address']] + ([cfg['eth_usd_feed']['address']] if f.get('quote') == 'ETH' else [])
    t = now if now is not None else _now(w3)
    ages = []
    for a in feeds:
        hit = _cache.get(Web3.to_checksum_address(a))
        if not hit:
            raise OracleError('price feed age unavailable')
        ages.append(int(t) - int(hit['upd']))
    return max(ages)


price_usd = token_price_usd


def allowlist(cfg):
    return {Web3.to_checksum_address(t['address']) for t in cfg.get('tokens', [])}


def clear_cache():
    _cache.clear()
