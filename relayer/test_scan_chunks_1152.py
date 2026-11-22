"""#1152/#1165: getLogs de approvals troceado (<=2000 bloques), filtro address (<=10), reintento 429 y fallo total controlado."""
import json
import os
import pytest
import requests
import svc_scan as S

ADDR = '0x' + '22' * 20
HERE = os.path.dirname(os.path.abspath(__file__))
ASSETS_8453 = json.load(open(os.path.join(HERE, 'data', 'assets_8453.json')))


def _e429():
    r = requests.Response(); r.status_code = 429
    return requests.HTTPError('429 Client Error: Too Many Requests', response=r)


class _LEth:
    """Proveedor de logs simulado: 'script' es una lista de excepciones/None consumida por llamada."""
    def __init__(self, head=10_000_000, script=None, always=None):
        self.head, self.script, self.always = head, list(script or []), always
        self.filters, self.calls = [], 0

    @property
    def block_number(self):
        return self.head

    def get_logs(self, f):
        self.calls += 1
        self.filters.append(f)
        if self.always is not None:
            raise self.always
        if self.script:
            e = self.script.pop(0)
            if e is not None:
                raise e
        return []


class _LP:
    def __init__(self, **kw):
        self.eth = _LEth(**kw)


@pytest.fixture
def base(monkeypatch):
    monkeypatch.setattr(S, 'assets', lambda: ASSETS_8453)
    sleeps = []
    monkeypatch.setattr('time.sleep', lambda s: sleeps.append(s))
    return sleeps


def test_a_chunk_429_luego_200_reintenta_con_backoff(base):
    p = _LP(script=[_e429(), None])
    out = S._get_logs_retry(p, {'fromBlock': 1, 'toBlock': 2000}, sleep=lambda s: base.append(s))
    assert out == []
    assert p.eth.calls == 2
    assert base == [S.CHUNK_BACKOFF_S]  # un backoff antes del reintento
    # y dentro de live_approvals completo: primer chunk 429 -> se recupera, sin error
    lp = _LP(script=[_e429()])
    S_live = S.live_approvals
    import unittest.mock as m
    with m.patch.object(S, '_logs_w3', lambda chain_id=None: lp):
        assert S_live(ADDR) == []
    assert any(s > 0 for s in base[1:])


def test_b_9000_bloques_chunks_2000_y_grupos_10(base, monkeypatch):
    head = 10_000_000
    lp = _LP(head=head)
    monkeypatch.setattr(S, '_logs_w3', lambda chain_id=None: lp)
    monkeypatch.setattr(S, 'APPROVAL_LOOKBACK', 9000)
    contracts = S._asset_contracts(ASSETS_8453)
    assert len(contracts) > 0
    assert S.live_approvals(ADDR) == []
    rngs = sorted({(f['fromBlock'], f['toBlock']) for f in lp.eth.filters})
    assert all(t - fr + 1 <= 2000 for fr, t in rngs)
    assert rngs[0][0] == head - 9000 and rngs[-1][1] == head
    assert all(rngs[i + 1][0] == rngs[i][1] + 1 for i in range(len(rngs) - 1))  # contiguo, sin huecos
    assert len(rngs) == 5  # 9001 bloques inclusivos -> 2000x4 + 1001
    for f in lp.eth.filters:
        assert 1 <= len(f['address']) <= 10
    seen = {a for f in lp.eth.filters for a in f['address']}
    assert seen == set(contracts)
    ngroups = -(-len(contracts) // 10)
    assert lp.eth.calls == 5 * 2 * ngroups  # chunks x topics (Approval, ApprovalForAll) x grupos


def test_c_todos_los_chunks_fallan_error_controlado_no_500(base, monkeypatch):
    lp = _LP(always=requests.ConnectionError('down'))
    monkeypatch.setattr(S, '_logs_w3', lambda chain_id=None: lp)
    with pytest.raises(S.ApprovalsError) as ei:
        S.live_approvals(ADDR)
    assert str(ei.value) == 'rpc unavailable'
    lp429 = _LP(always=_e429())
    monkeypatch.setattr(S, '_logs_w3', lambda chain_id=None: lp429)
    with pytest.raises(S.ApprovalsError) as ei2:
        S.live_approvals(ADDR)
    assert '429' in str(ei2.value) and 'publicnode' not in str(ei2.value)
    # Via HTTP: error controlado (503 con detalle), nunca 500
    from fastapi.testclient import TestClient
    import service
    def fake_scan(a):
        try:
            S.live_approvals(a); err = None
        except S.ApprovalsError as e:
            err = str(e)
        return {'tokens': [], 'nfts': [], 'approvals': [], 'approvalsError': err}
    monkeypatch.setattr(service, 'scan', fake_scan)
    monkeypatch.setattr(service, '_guard', lambda req: None)
    r = TestClient(service.app, raise_server_exceptions=False).post('/api/scan', json={'address': ADDR})
    assert r.status_code == 503 and r.status_code != 500
    assert 'approvals check unavailable' in r.json()['detail']
