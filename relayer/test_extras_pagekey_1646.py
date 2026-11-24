"""#1646/#559: discover_extras pagina alchemy_getTokenBalances con pageKey y topes duros."""
import extras as EX
from web3 import Web3

ADDR = '0x' + '11' * 20
BRETT = Web3.to_checksum_address('0x532f27101965dd16442E59d40670FaF5eBB142E4')  # dato de prueba
BAL = '0x' + hex(10**18)[2:].rjust(64, '0')


def _tok(i):
    return {'contractAddress': '0x' + hex(0x1000 + i)[2:].rjust(40, '0'), 'tokenBalance': BAL}


class _Rpc:
    def __init__(self, pages):
        self.pages, self.calls = pages, []

    def __call__(self, method, params):
        assert method == 'alchemy_getTokenBalances'
        self.calls.append(params)
        i = len(self.calls) - 1
        return self.pages[i]


def test_dos_paginas_token_en_la_segunda():
    p1 = {'tokenBalances': [_tok(i) for i in range(100)], 'pageKey': 'PK2'}
    p2 = {'tokenBalances': [{'contractAddress': BRETT.lower(), 'tokenBalance': BAL}]}
    rpc = _Rpc([p1, p2])
    out = EX.discover_extras(rpc, ADDR, set())
    assert len(rpc.calls) == 2
    assert rpc.calls[0] == [Web3.to_checksum_address(ADDR), 'erc20']
    assert rpc.calls[1] == [Web3.to_checksum_address(ADDR), 'erc20', {'pageKey': 'PK2'}]
    e = [x for x in out if x['address'] == BRETT]
    assert len(e) == 1 and e[0]['unverified'] is True and e[0]['value_usd'] == 0
    assert len(out) == 101


def test_tope_de_paginas():
    pages = [{'tokenBalances': [_tok(i)], 'pageKey': 'K%d' % i} for i in range(10)]
    rpc = _Rpc(pages)
    out = EX.discover_extras(rpc, ADDR, set(), max_pages=5)
    assert len(rpc.calls) == 5 and len(out) == 5


def test_tope_de_tokens():
    pages = [{'tokenBalances': [_tok(i * 100 + j) for j in range(100)], 'pageKey': 'K%d' % i} for i in range(10)]
    rpc = _Rpc(pages)
    out = EX.discover_extras(rpc, ADDR, set(), max_pages=10, max_tokens=250)
    assert len(rpc.calls) == 3 and len(out) == 250


def test_presupuesto_de_tiempo():
    t = iter([0.0, 0.0, 30.0, 30.0])
    pages = [{'tokenBalances': [_tok(i)], 'pageKey': 'K%d' % i} for i in range(5)]
    rpc = _Rpc(pages)
    out = EX.discover_extras(rpc, ADDR, set(), time_budget=20, _now=lambda: next(t))
    assert len(rpc.calls) == 2 and len(out) == 2


def test_topes_por_defecto():
    assert EX.MAX_PAGES <= 5 and EX.MAX_TOKENS_SCANNED <= 500 and EX.EXTRAS_TIME_BUDGET <= 30


def test_error_en_segunda_pagina_se_propaga():
    class _Boom(Exception):
        pass

    calls = []

    def rpc(m, p):
        calls.append(p)
        if len(calls) == 2:
            raise _Boom('x')
        return {'tokenBalances': [_tok(1)], 'pageKey': 'K'}
    try:
        EX.discover_extras(rpc, ADDR, set())
        assert False, 'debia propagar'
    except _Boom:
        pass


def test_scan_extras_fail_soft_y_pagekey_via_http(monkeypatch, caplog):
    import logging
    import svc_scan as S
    import test_extras_1684 as T
    monkeypatch.setenv('BASE_RPC_URL', T.KEYURL)
    monkeypatch.delenv('UNSWEEP_EXTRAS_RPC', raising=False)
    monkeypatch.setattr(S, 'CHAIN_ID', 8453)
    monkeypatch.setattr(S, 'w3', T._W3())
    monkeypatch.setattr(S.O, 'allowlist', lambda a: set())
    monkeypatch.setattr(S.time, 'sleep', lambda s: None)
    bodies = []
    resps = [T._R(200, {'jsonrpc': '2.0', 'id': 1, 'result': {'tokenBalances': [_tok(1)], 'pageKey': 'PK2'}}),
             T._R(200, {'jsonrpc': '2.0', 'id': 1, 'result': {'tokenBalances': [{'contractAddress': BRETT, 'tokenBalance': BAL}]}})]

    def post(url, json=None, timeout=None):
        bodies.append(json)
        return resps.pop(0)
    monkeypatch.setattr(S.requests, 'post', post)
    exs = S.scan_extras(ADDR)
    assert bodies[1]['params'][2] == {'pageKey': 'PK2'}
    assert BRETT in [e['address'] for e in exs]
    # fallo en la 2a pagina -> fail-soft [] con WARNING
    resps[:] = [T._R(200, {'jsonrpc': '2.0', 'id': 1, 'result': {'tokenBalances': [], 'pageKey': 'PK2'}}),
                T._R(401, {'error': {'code': -32611, 'message': 'denied'}})]
    with caplog.at_level(logging.WARNING):
        assert S.scan_extras(ADDR) == []
    assert 'extras no disponibles' in caplog.text
