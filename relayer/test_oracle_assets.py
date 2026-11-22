"""Tests del oraculo Chainlink (fail-closed) y de la allowlist de Base 8453 (#90, verificacion #141)."""
import json
import types
from pathlib import Path

import pytest

import oracle as O
import policy as P
import svc_scan as S
from test_service_policy import scan_env, USDC  # noqa: F401

FEED = '0x7e860098F58bBFC8648a4311b374B1D669a2bc6B'
NOW = 1_800_000_000


class _Fn:
    def __init__(self, v):
        self.v = v

    def call(self):
        if isinstance(self.v, Exception):
            raise self.v
        return self.v


def _w3(answer=100_000_000, upd=NOW - 60, rid=10, air=10, dec=8, block_ts=NOW, block_err=False):
    st = {'round': (rid, answer, upd, upd, air), 'ts': block_ts}

    def contract(address, abi):
        return types.SimpleNamespace(functions=types.SimpleNamespace(
            latestRoundData=lambda: _Fn(st['round']), decimals=lambda: _Fn(dec)))

    def get_block(b):
        if block_err:
            raise ConnectionError('rpc caido')
        return {'timestamp': st['ts']}

    return types.SimpleNamespace(eth=types.SimpleNamespace(contract=contract, get_block=get_block)), st


@pytest.fixture(autouse=True)
def _clean_cache():
    O.clear_cache()
    yield
    O.clear_cache()


def test_oracle_error_is_policy_error():
    assert issubclass(O.OracleError, P.PolicyError)


def test_fresh_price_ok():
    w3, _ = _w3()
    assert O.read_feed(w3, FEED, 86400, 8) == pytest.approx(1.0)


def test_stale_price_rejected_by_chain_time():
    w3, _ = _w3(upd=NOW - 86401)
    with pytest.raises(P.PolicyError):
        O.read_feed(w3, FEED, 86400, 8)


def test_stale_uses_block_timestamp_not_local_clock():
    # updatedAt muy antiguo respecto al reloj local, pero fresco respecto al bloque
    w3, _ = _w3(upd=1_000_000_000 - 30, block_ts=1_000_000_000)
    assert O.read_feed(w3, FEED, 1200, 8) == pytest.approx(1.0)


def test_no_local_clock_fallback_when_block_unavailable():
    w3, _ = _w3(block_err=True)
    with pytest.raises(P.PolicyError):
        O.read_feed(w3, FEED, 86400, 8)


def test_cache_never_serves_stale():
    w3, st = _w3(upd=NOW - 60)
    assert O.read_feed(w3, FEED, 1200, 8) == pytest.approx(1.0)
    st['ts'] = NOW + 1200  # la cadena avanza: el dato cacheado supera el heartbeat
    with pytest.raises(P.PolicyError):
        O.read_feed(w3, FEED, 1200, 8)


@pytest.mark.parametrize('answer', [0, -1])
def test_answer_non_positive_rejected(answer):
    w3, _ = _w3(answer=answer)
    with pytest.raises(P.PolicyError):
        O.read_feed(w3, FEED, 86400, 8)


def test_answered_in_round_lt_round_rejected():
    w3, _ = _w3(rid=11, air=10)
    with pytest.raises(P.PolicyError):
        O.read_feed(w3, FEED, 86400, 8)


def test_decimals_mismatch_rejected():
    w3, _ = _w3(dec=18)
    with pytest.raises(P.PolicyError):
        O.read_feed(w3, FEED, 86400, 8)


def test_price_usd_token_outside_allowlist():
    w3, _ = _w3()
    cfg = {'tokens': [{'address': USDC, 'feed': {'address': FEED, 'quote': 'USD', 'heartbeat': 86400, 'decimals': 8}}]}
    intruso = {'address': '0x00000000000000000000000000000000000000C3',
               'feed': {'address': FEED, 'quote': 'USD', 'heartbeat': 86400, 'decimals': 8}}
    with pytest.raises(P.PolicyError):
        O.price_usd(w3, cfg, intruso)


def test_quote_rejects_token_outside_allowlist(scan_env):  # noqa: F811
    scan_env.setattr(S, 'CHAIN_ID', 84532)
    s = {'tokens': [{'address': '0x00000000000000000000000000000000000000C3', 'symbol': 'X', 'decimals': 6,
                     'price_usd': 1, 'fee_on_transfer': False, 'balance': str(500 * 10**6)}], 'nfts': []}
    with pytest.raises(P.PolicyError):
        S.quote(s)


def _norm(x):
    x = x.upper()
    return 'ETH' if x == 'WETH' else x


def test_assets_8453_16_symbols_16_feeds_coherent():
    d = json.loads((Path(__file__).parent / 'data' / 'assets_8453.json').read_text())
    toks = d['tokens']
    assert len(toks) == 16
    syms = [t['symbol'] for t in toks]
    assert len(set(syms)) == 16
    assert len({t['address'].lower() for t in toks}) == 16
    for t in toks:
        f = t['feed']
        base, quote = [p.strip() for p in f['pair'].split('/')]
        assert _norm(base) == _norm(t['symbol']), (t['symbol'], f['pair'])
        assert quote == f['quote'] and quote in ('USD', 'ETH')
        assert int(f['heartbeat']) > 0 and int(f['decimals']) == (8 if quote == 'USD' else 18)
    assert d['eth_usd_feed']['pair'] == 'ETH / USD'


def test_assets_42161_native_usdc_feeds_verified():
    d = json.loads((Path(__file__).parent / 'data' / 'assets_42161.json').read_text())
    assert d['chainId'] == 42161
    addrs = {t['address'].lower() for t in d['tokens']}
    assert '0xaf88d065e77c8cc2239327c5edb3a432268e5831' in addrs  # USDC nativo
    assert '0xff970a61a04b1ca14834a43f5de4533ebddb5cc8' not in addrs  # USDC.e excluido
    for f in [d['eth_usd_feed']] + [t['feed'] for t in d['tokens']]:
        assert f['aggregator'].startswith('0x') and int(f['aggregator'], 16) != 0
        assert int(f['heartbeat']) > 0 and int(f['decimals']) == (8 if f['quote'] == 'USD' else 18)
