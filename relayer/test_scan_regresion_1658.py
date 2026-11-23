"""ORDEN #1658: un fallo en la ruta de logs (429) nunca produce tokens=[] silencioso;
un fallo del indice de tokens es VISIBLE (incomplete) y no se cachea."""
import pytest
import svc_mainnet as M

ADDR = '0xa51389a213ba84bf99591b8b6482c41b2381b441'
USDC = '0x833589fcd6edb6e08f4c7c32d4f71b54bda02913'
BRETT = '0x532f27101965dd16442e59d40670faf5ebb142e4'
META = {USDC: {'symbol': 'USDC', 'decimals': 6}, BRETT: {'symbol': 'BRETT', 'decimals': 18}}


def _fake(fail=(), balances=None):
    calls = []

    def rpc(url, method, params, deadline):
        calls.append(method)
        if method in fail:
            raise M.ScanError('HTTP 429 request limit reached')
        if method == 'eth_blockNumber':
            return hex(61389970)
        if method == 'eth_getCode':
            return '0x'
        if method in ('eth_getTransactionCount', 'eth_getBalance'):
            return '0x0'
        if method == 'alchemy_getTokenBalances':
            return {'tokenBalances': balances if balances is not None else [
                {'contractAddress': USDC, 'tokenBalance': hex(5_000_000)},
                {'contractAddress': BRETT, 'tokenBalance': hex(123 * 10**18)}]}
        if method == 'alchemy_getTokenMetadata':
            return META.get(params[0].lower(), {})
        if method == 'alchemy_getAssetTransfers':
            return {'transfers': []}
        if method == 'eth_getLogs':
            return []
        if method == 'eth_call':  # #1658b: balanceOf de la lista, coherente con el indice simulado
            bl = balances if balances is not None else [
                {'contractAddress': USDC, 'tokenBalance': hex(5_000_000)},
                {'contractAddress': BRETT, 'tokenBalance': hex(123 * 10**18)}]
            to = params[0]['to'].lower()
            return next((b['tokenBalance'] for b in bl if b['contractAddress'].lower() == to), '0x0')
        return None
    return rpc, calls


def _post_from(rpc):
    """#1658b: los lotes JSON-RPC (balanceOf de la lista) pasan por el mismo fake."""
    def post(url, body, deadline, tries=5):
        if isinstance(body, list):
            out = []
            for c in body:
                try:
                    out.append({'id': c['id'], 'result': rpc(url, c['method'], c['params'], deadline)})
                except M.ScanError as e:
                    out.append({'id': c['id'], 'error': {'message': str(e)}})
            return out
        return {'id': 1, 'result': rpc(url, body['method'], body['params'], deadline)}
    return post


@pytest.fixture(autouse=True)
def _iso(monkeypatch):
    monkeypatch.setattr(M, '_url', lambda chain: 'http://mock')
    M._cache.clear()
    yield
    M._cache.clear()


def test_fallo_logs_429_tokens_conocidos_siguen_apareciendo(monkeypatch):
    rpc, _ = _fake(fail=('alchemy_getAssetTransfers', 'eth_getLogs'))
    monkeypatch.setattr(M, '_rpc', rpc)
    monkeypatch.setattr(M, '_post', _post_from(rpc))
    r = M.scan_mainnet('base', ADDR)
    by = {t['contract'].lower(): t for t in r['tokens']}
    assert r['tokensTotalNonZero'] == 2 and r['tokens'] != []
    assert by[USDC]['symbol'] == 'USDC' and by[USDC]['balanceRaw'] == '5000000'
    assert by[BRETT]['symbol'] == 'BRETT' and by[BRETT]['balanceRaw'] == str(123 * 10**18)
    assert r['status'] == 'incomplete' and r['incompleteReasons']  # fallo parcial explicito
    assert M.scan_mainnet('base', ADDR)['cached'] is False  # no se cachea lo incompleto


def test_vacio_legitimo_sin_errores_es_complete(monkeypatch):
    rpc, _ = _fake(balances=[])
    monkeypatch.setattr(M, '_rpc', rpc)
    monkeypatch.setattr(M, '_post', _post_from(rpc))
    r = M.scan_mainnet('base', ADDR)
    assert r['status'] == 'complete' and r['incompleteReasons'] == [] and r['tokens'] == []


def test_fallo_indice_tokens_es_visible_y_no_cacheado(monkeypatch):
    rpc, calls = _fake(fail=('alchemy_getTokenBalances',))
    monkeypatch.setattr(M, '_rpc', rpc)
    monkeypatch.setattr(M, '_post', _post_from(rpc))
    r = M.scan_mainnet('base', ADDR)
    assert r['status'] == 'incomplete'
    assert any('token balances failed' in x for x in r['incompleteReasons'])
    n = calls.count('alchemy_getTokenBalances')
    r2 = M.scan_mainnet('base', ADDR)
    assert r2['cached'] is False and calls.count('alchemy_getTokenBalances') > n
