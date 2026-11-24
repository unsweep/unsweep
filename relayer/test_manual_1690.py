"""#1690 (3): contratos manuales en Step 2. Limites de entrada, sondas ERC-20 y endpoint. Sin red."""
import pytest
from eth_abi import encode
from web3 import Web3

import manual as MAN
import svc_manual as SM

A = [Web3.to_checksum_address('0x' + ('%02x' % i) * 20) for i in range(1, 6)]
HOLDER = Web3.to_checksum_address('0x' + 'ab' * 20)
SAFE = Web3.to_checksum_address('0x' + 'cd' * 20)
LISTED = Web3.to_checksum_address('0x' + 'ee' * 20)


def _w(n):
    return '0x' + n.to_bytes(32, 'big').hex()


def fake_rpc(bal=10**18, dec=18, sym='BRETT', code='0x6080', fail=()):
    def rpc(method, params):
        if method == 'eth_getCode':
            if 'code' in fail: raise RuntimeError('x')
            return code
        data = params[0]['data']
        if data.startswith(MAN.SEL_BALANCEOF):
            if 'bal' in fail: raise RuntimeError('x')
            return _w(bal)
        if data == MAN.SEL_DECIMALS:
            if 'dec' in fail: raise RuntimeError('x')
            return _w(dec)
        if data == MAN.SEL_SYMBOL:
            if 'sym' in fail: raise RuntimeError('x')
            return '0x' + encode(['string'], [sym]).hex()
        raise AssertionError(data)
    return rpc


# ---- parse_contracts: limites ----
def test_parse_0():
    assert MAN.parse_contracts(None) == [] and MAN.parse_contracts('') == [] and MAN.parse_contracts([]) == []

def test_parse_1_y_3():
    assert MAN.parse_contracts([A[0]]) == [A[0]]
    assert MAN.parse_contracts(' '.join(A[:3])) == A[:3]

def test_parse_4_rechaza():
    with pytest.raises(MAN.ManualInputError, match='maximo 3'):
        MAN.parse_contracts(A[:4])

def test_parse_invalida_y_checksum():
    with pytest.raises(MAN.ManualInputError, match='formato'):
        MAN.parse_contracts(['0x1234'])
    with pytest.raises(MAN.ManualInputError, match='checksum'):
        MAN.parse_contracts([A[0].lower().replace('0x', '0x', 1) if A[0] != A[0].lower() else '0x' + 'aB' * 20])

def test_parse_duplicados():
    with pytest.raises(MAN.ManualInputError, match='repetida'):
        MAN.parse_contracts([A[0], A[0]])


# ---- probe/resolve ----
def test_probe_ok_value_usd_0():
    e, why = MAN.probe(fake_rpc(), HOLDER, A[0])
    assert why is None and e['value_usd'] == 0 and e['unverified'] and e['symbol'] == 'BRETT' and e['decimals'] == 18

@pytest.mark.parametrize('kw,frag', [({'fail': ('sym',)}, 'symbol'), ({'sym': ''}, 'symbol'),
                                     ({'fail': ('dec',)}, 'decimals'), ({'bal': 0}, 'saldo 0'),
                                     ({'code': '0x'}, 'sin codigo'), ({'fail': ('code',)}, 'rpc')])
def test_probe_rechazos(kw, frag):
    e, why = MAN.probe(fake_rpc(**kw), HOLDER, A[0])
    assert e is None and frag in why

def test_resolve_token_listado_rechazado():
    acc, rej = MAN.resolve(fake_rpc(), HOLDER, [LISTED, A[0]], {LISTED})
    assert [e['address'] for e in acc] == [A[0]]
    assert rej == [{'address': LISTED, 'reason': 'duplicado de la lista verificada'}]

def test_add_manual_sin_valor_listado():
    s = {'address': HOLDER, 'tokens': [], 'extras': []}
    acc, rej = SM.add_manual(s, [A[0]], rpc=fake_rpc(), allowed=set())
    assert acc == [] and rej[0]['reason'] == MAN.DISABLED_REASON and s['extras'] == []

def test_manual_rpc_usa_w3_relayer_no_alchemy():
    import inspect
    src = inspect.getsource(SM)
    assert '_extras_rpc' not in src and 'alchemy' not in src.lower().split('discover_extras')[0].replace('alchemy queda', '')
    class P:
        def make_request(self, m, p): return {'jsonrpc': '2.0', 'id': 1, 'result': '0x1'}
    class W: provider = P()
    assert SM.manual_rpc('eth_call', [], _w3=W()) == '0x1'
    class PE:
        def make_request(self, m, p): return {'error': {'code': -32000}}
    class WE: provider = PE()
    with pytest.raises(SM.ManualRpcError):
        SM.manual_rpc('eth_call', [], _w3=WE())


# ---- endpoint ----
@pytest.fixture
def client(monkeypatch):
    from fastapi.testclient import TestClient
    import service
    state = {'listed_value': True, 'quote_extras': None}
    def fake_scan(a):
        toks = [{'address': LISTED, 'balance': str(10**6), 'decimals': 6, 'price_usd': 1.0}] if state['listed_value'] else []
        return {'address': HOLDER, 'tokens': toks, 'nfts': [], 'extras': []}
    def fake_quote(s, extras=None):
        state['quote_extras'] = extras
        return {'policy_ok': True, 'policy_reason': None, 'lines': []}, None
    monkeypatch.setattr(service, 'scan', fake_scan)
    monkeypatch.setattr(service, 'quote', fake_quote)
    monkeypatch.setattr(service, '_guard', lambda req: None)
    monkeypatch.setattr(service, 'screen', lambda *a: None, raising=False)
    monkeypatch.setattr(service, 'record', lambda *a, **k: None)
    monkeypatch.setattr(service, 'add_manual', lambda s, c: SM.add_manual(s, c, rpc=fake_rpc(), allowed={LISTED}))
    return TestClient(service.app, raise_server_exceptions=False), state

def _post(c, manual):
    return c.post('/api/quote_manual', json={'address': HOLDER, 'safe': SAFE, 'manual': manual})

@pytest.mark.parametrize('manual,code', [([], 400), (A[:1], 200), (A[:3], 200), (A[:4], 400),
                                         (['0xzz'], 400), ([A[0], A[0]], 400)])
def test_endpoint_limites(client, manual, code):
    c, st = client
    r = _post(c, manual)
    assert r.status_code == code, r.text
    if code == 200:
        assert r.json()['manual']['accepted'] == manual and st['quote_extras'] == manual

def test_endpoint_token_listado(client):
    c, _ = client
    j = _post(c, [LISTED, A[0]]).json()
    assert j['manual']['accepted'] == [A[0]] and j['manual']['rejected'][0]['address'] == LISTED

def test_endpoint_sin_valor_listado_400(client):
    c, st = client
    st['listed_value'] = False
    r = _post(c, A[:1])
    assert r.status_code == 400 and 'token listado' in r.text

def test_endpoint_rate_limit_igual_que_scan():
    import inspect, service
    assert '_guard(req)' in inspect.getsource(service.api_quote_manual)
