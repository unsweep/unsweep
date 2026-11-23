"""#1684: extras via cliente Alchemy dedicado (no el RPC publico de w3).
Error con motivo concreto y fail-soft, error JSON-RPC con HTTP 200 no silencioso, 429 con backoff, exito con value_usd=0."""
import logging
import pytest
import svc_scan as S

ADDR = '0x' + '11' * 20
LISTED = '0x' + 'aa' * 20
EXTRA = '0x532f27101965dd16442E59d40670FaF5eBB142E4'  # BRETT (Base), solo como dato de prueba
KEYURL = 'https://base-mainnet.g.alchemy.com/v2/TESTKEY'


class _R:
    def __init__(self, code, j):
        self.status_code, self._j = code, j

    def json(self):
        return self._j


class _Fn:
    def __init__(self, v):
        self.v = v

    def call(self):
        return self.v


class _Funcs:
    def decimals(self):
        return _Fn(18)

    def symbol(self):
        return _Fn('BRETT')


class _C:
    functions = _Funcs()


class _Eth:
    def contract(self, address=None, abi=None):
        return _C()


class _W3:
    eth = _Eth()


class _Post:
    def __init__(self, *resps):
        self.resps, self.urls, self.methods = list(resps), [], []

    def __call__(self, url, json=None, timeout=None):
        self.urls.append(url); self.methods.append(json['method'])
        return self.resps.pop(0) if len(self.resps) > 1 else self.resps[0]


@pytest.fixture
def env(monkeypatch):
    monkeypatch.setenv('BASE_RPC_URL', KEYURL)
    monkeypatch.delenv('UNSWEEP_EXTRAS_RPC', raising=False)
    monkeypatch.setattr(S, 'CHAIN_ID', 8453)
    monkeypatch.setattr(S, 'w3', _W3())
    monkeypatch.setattr(S.O, 'allowlist', lambda a: {S.Web3.to_checksum_address(LISTED)})
    monkeypatch.setattr(S.time, 'sleep', lambda s: None)
    return monkeypatch


def _err(code, msg):
    return {'jsonrpc': '2.0', 'id': 1, 'error': {'code': code, 'message': msg}}


def test_url_por_cadena_sin_rpc_publico(env):
    assert S._extras_url() == KEYURL
    env.setattr(S, 'CHAIN_ID', 42161)
    assert S._extras_url() == 'https://arb-mainnet.g.alchemy.com/v2/TESTKEY'
    env.setenv('BASE_RPC_URL', 'https://mainnet.base.org')
    assert S._extras_url() is None


def test_error_401_motivo_concreto_fail_soft_sin_url(env, caplog):
    p = _Post(_R(401, _err(-32611, 'rejected due to request filter settings')))
    env.setattr(S.requests, 'post', p)
    with caplog.at_level(logging.WARNING):
        assert S.scan_extras(ADDR) == []
    assert p.urls and p.urls[0] == KEYURL  # nunca el RPC publico de w3
    assert '-32611' in caplog.text and 'request filter' in caplog.text
    assert 'extras no disponibles: HTTPError' not in caplog.text and 'TESTKEY' not in caplog.text


def test_error_jsonrpc_con_http_200_no_es_silencioso(env, caplog):
    p = _Post(_R(200, _err(-32601, 'the method alchemy_getTokenBalances does not exist/is not available')))
    env.setattr(S.requests, 'post', p)
    with caplog.at_level(logging.WARNING):
        assert S.scan_extras(ADDR) == []
    assert '-32601' in caplog.text


def test_sin_alchemy_motivo_explicito(env, caplog):
    env.setenv('BASE_RPC_URL', '')
    with caplog.at_level(logging.WARNING):
        assert S.scan_extras(ADDR) == []
    assert 'sin endpoint Alchemy' in caplog.text


def test_429_backoff_y_luego_exito(env):
    ok = {'jsonrpc': '2.0', 'id': 1, 'result': {'address': ADDR, 'tokenBalances': []}}
    sleeps = []
    p = _Post(_R(429, {}), _R(429, {}), _R(200, ok))
    assert S._extras_rpc('alchemy_getTokenBalances', [ADDR, 'erc20'], _post=lambda u, j: p(u, json=j), _sleep=sleeps.append) == ok['result']
    assert sleeps == [S.EXTRAS_BACKOFF, S.EXTRAS_BACKOFF * 2]


def test_429_persistente_motivo(env):
    with pytest.raises(S.ExtrasError) as ei:
        S._extras_rpc('m', [], _post=lambda u, j: _R(429, {}), _sleep=lambda s: None)
    assert '429' in str(ei.value)


def test_exito_extra_fuera_de_lista_value_usd_0(env):
    bal = '0x' + hex(5 * 10**18)[2:].rjust(64, '0')
    ok = {'jsonrpc': '2.0', 'id': 1, 'result': {'address': ADDR, 'tokenBalances': [
        {'contractAddress': EXTRA.lower(), 'tokenBalance': bal},
        {'contractAddress': LISTED, 'tokenBalance': bal}]}}
    env.setattr(S.requests, 'post', _Post(_R(200, ok)))
    exs = S.scan_extras(ADDR)
    addrs = [S.Web3.to_checksum_address(e['address']) for e in exs]
    assert S.Web3.to_checksum_address(EXTRA) in addrs
    assert S.Web3.to_checksum_address(LISTED) not in addrs
    e = exs[addrs.index(S.Web3.to_checksum_address(EXTRA))]
    assert e.get('value_usd', 0) == 0 and e['symbol'] == 'BRETT' and e['decimals'] == 18
