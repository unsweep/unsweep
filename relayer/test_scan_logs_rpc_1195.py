"""#1195 v12f PASO 0: RPC de logs de approvals para 42161 = arb1 con User-Agent explicito (sin red; mocks)."""
import json
import os
import pytest
import requests
import svc_scan as S

HERE = os.path.dirname(os.path.abspath(__file__))
ASSETS_42161 = json.load(open(os.path.join(HERE, 'data', 'assets_42161.json')))
ADDR = '0x' + '33' * 20


@pytest.fixture(autouse=True)
def _fresh_cache(monkeypatch):
    monkeypatch.setattr(S, '_LOGS_W3', {})


def test_config_42161_arb1_activo_y_base_intacto():
    assert S.APPROVAL_LOGS_RPC[42161] == 'https://arb1.arbitrum.io/rpc'
    assert 42161 in S.APPROVAL_LOGS_ENABLED
    assert S.APPROVAL_LOGS_RPC[8453] == 'https://base-rpc.publicnode.com'
    assert 8453 in S.APPROVAL_LOGS_ENABLED
    assert 8453 not in S.APPROVAL_LOGS_UA  # Base sin cambios de cabeceras
    assert S.LOG_CHUNK == 2000


def _capture(monkeypatch):
    seen = []

    def fake_post(self, url, *a, **kw):
        seen.append((url, dict(kw.get('headers') or {}), dict(self.headers)))
        r = requests.Response()
        r.status_code = 200
        r._content = json.dumps({'jsonrpc': '2.0', 'id': 0, 'result': '0x10'}).encode()
        r.headers['Content-Type'] = 'application/json'
        return r
    monkeypatch.setattr(requests.Session, 'post', fake_post)
    return seen


def _ua(entry):
    _, h_kw, h_sess = entry
    for h in (h_kw, h_sess):
        for k, v in h.items():
            if k.lower() == 'user-agent':
                return v
    return None


def test_42161_envia_user_agent_explicito_a_arb1(monkeypatch):
    seen = _capture(monkeypatch)
    w3 = S._logs_w3(42161)
    assert w3 is not None
    assert w3.eth.block_number == 16
    assert seen and seen[-1][0] == 'https://arb1.arbitrum.io/rpc'
    ua = _ua(seen[-1])
    assert ua == 'curl/8.5.0'
    assert 'python' not in ua.lower()


def test_8453_sin_user_agent_forzado(monkeypatch):
    seen = _capture(monkeypatch)
    w3 = S._logs_w3(8453)
    assert w3.eth.block_number == 16
    assert seen[-1][0] == 'https://base-rpc.publicnode.com'
    assert _ua(seen[-1]) != 'curl/8.5.0'


class _LEth:
    def __init__(self, head):
        self.head, self.filters = head, []

    @property
    def block_number(self):
        return self.head

    def get_logs(self, f):
        self.filters.append(f)
        return []


class _LP:
    def __init__(self, head):
        self.eth = _LEth(head)


def test_live_approvals_42161_chunks_2000_y_address_assets(monkeypatch):
    monkeypatch.setattr(S, 'CHAIN_ID', 42161)
    monkeypatch.setattr(S, 'assets', lambda: ASSETS_42161)
    lp = _LP(head=526_440_395)
    monkeypatch.setattr(S, '_logs_w3', lambda chain_id=None: lp)
    S.live_approvals(ADDR)
    fl = lp.eth.filters
    assert fl, 'sin llamadas a get_logs'
    contracts = set(S._asset_contracts(ASSETS_42161))
    for f in fl:
        assert f['toBlock'] - f['fromBlock'] + 1 <= 2000
        assert 0 < len(f['address']) <= S.LOGS_ADDR_GROUP
        assert set(f['address']) <= contracts
    cubiertos = set()
    for f in fl:
        cubiertos |= set(f['address'])
    assert cubiertos == contracts
