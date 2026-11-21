"""#92: approvals con RPC de pago principal; un 429 es error VISIBLE, nunca lista vacia."""
import pytest
import requests
import svc_scan as S


class _Eth:
    def __init__(self, err=None, head=100):
        self.err, self.head, self.calls = err, head, 0

    @property
    def block_number(self):
        self.calls += 1
        if self.err:
            raise self.err
        return self.head

    def get_logs(self, f):
        self.calls += 1
        if self.err:
            raise self.err
        return []


class _P:
    def __init__(self, err=None):
        self.eth = _Eth(err)


def _e429():
    r = requests.Response(); r.status_code = 429
    return requests.HTTPError('429 Client Error: Too Many Requests', response=r)


ADDR = '0x' + '11' * 20


def test_429_en_todos_es_error_visible_no_lista_vacia(monkeypatch):
    monkeypatch.setattr(S, '_ap_providers', lambda: [_P(_e429()), _P(_e429())])
    with pytest.raises(S.ApprovalsError) as ei:
        S.live_approvals(ADDR)
    assert '429' in str(ei.value)
    assert 'http' not in str(ei.value).lower().replace('(http 429)', '')  # sin URL


def test_principal_de_pago_se_usa_primero(monkeypatch):
    paid, pub = _P(), _P()
    monkeypatch.setattr(S, '_ap_providers', lambda: [paid, pub])
    assert S.live_approvals(ADDR) == []
    assert paid.eth.calls > 0 and pub.eth.calls == 0


def test_respaldo_si_principal_429(monkeypatch):
    paid, pub = _P(_e429()), _P()
    monkeypatch.setattr(S, '_ap_providers', lambda: [paid, pub])
    assert S.live_approvals(ADDR) == []
    assert pub.eth.calls > 0


def test_rpc_caido_es_error_visible(monkeypatch):
    monkeypatch.setattr(S, '_ap_providers', lambda: [_P(requests.ConnectionError('x'))])
    with pytest.raises(S.ApprovalsError) as ei:
        S.live_approvals(ADDR)
    assert str(ei.value) == 'rpc unavailable'


def test_providers_pago_principal_en_base(monkeypatch):
    monkeypatch.setattr(S, '_AP_W3', [])
    monkeypatch.setattr(S, 'CHAIN_ID', 8453)
    monkeypatch.setenv('BASE_RPC_URL', 'https://paid.invalid/x')
    ps = S._ap_providers()
    assert len(ps) == 2 and ps[0] is not S.w3 and ps[1] is S.w3


def test_api_scan_429_devuelve_503_visible(monkeypatch):
    from fastapi.testclient import TestClient
    import service
    monkeypatch.setattr(service, 'scan', lambda a: {'tokens': [], 'nfts': [], 'approvals': [],
                                                  'approvalsError': 'rpc rate limited (HTTP 429)'})
    monkeypatch.setattr(service, '_guard', lambda req: None)
    r = TestClient(service.app).post('/api/scan', json={'address': ADDR})
    assert r.status_code == 503
    assert 'approvals check unavailable' in r.json()['detail'] and '429' in r.json()['detail']
