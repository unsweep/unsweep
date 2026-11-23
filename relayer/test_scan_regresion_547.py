"""#1658c: regresion de las 4 direcciones de #547 (USDC/BRETT/DEGEN ausentes en /api/scan),
token fuera de la lista de 16, reintento de balanceOf con RPC alternativo, unknown/retry y partial.
Saldos tomados de artifacts/orden1658b/compare.json (bloques 61393257-61393464). Todo mockeado."""
import time
import pytest
import svc_mainnet as M

USDC = '0x833589fcd6edb6e08f4c7c32d4f71b54bda02913'
BRETT = '0x532f27101965dd16442e59d40670faf5ebb142e4'
DEGEN = '0x4ed4e862860bed51a9570b96d89af5e1b0efefed'
PRIMARY, ALT = 'http://primary.invalid/rpc', 'http://alt.invalid/rpc'

CASES = {
    '0x18b0f4547a89fe4c5fe84f258bea3601fa281e9f': {USDC: 517557536534, BRETT: 21089434571592522440176561, DEGEN: 78580622058842414724666858},
    '0x0e74990625dace3c97306e964c23de6740db0b77': {USDC: 43288395756, BRETT: 486809178567667780231333, DEGEN: 0},
    '0x4446adc0b8136ffc55ddb7a488ba5509ace2a5ef': {USDC: 372206330732, BRETT: 126432474909005049460437, DEGEN: 68358733762260022834824},
    '0x8e92d28216ac924bbf01f2e7fe4fffd575ec3f17': {USDC: 5745977625, BRETT: 745270473303148055177062, DEGEN: 1186936358961761483057426},
}
SPAM = ['0x' + ('%040x' % (0xdead0000 + i)) for i in range(300)]
PAGES = 3


def make(truth, fail_primary_batch=False, fail_alt_batch=False, page_sleep=0.0, endless=False):
    """truth: {contract: saldo en cadena}. Indice: 3 paginas de spam (1 c/u), BRETT/DEGEN solo en la ultima."""
    chain = dict(truth)
    for s in SPAM:
        chain.setdefault(s, 1)
    per = len(SPAM) // PAGES

    def _post(url, body, deadline, tries=5):
        if isinstance(body, list):
            if (url == PRIMARY and fail_primary_batch) or (url == ALT and fail_alt_batch):
                raise M.ScanError('rpc http 503')
            return [{'jsonrpc': '2.0', 'id': c['id'],
                     'result': hex(chain.get(c['params'][0]['to'].lower(), 0))} for c in body]
        m, p = body['method'], body['params']
        if m == 'eth_blockNumber': r = hex(61393400)
        elif m == 'eth_getCode': r = '0x'
        elif m in ('eth_getTransactionCount', 'eth_getBalance'): r = '0x0'
        elif m == 'alchemy_getAssetTransfers': r = {'transfers': []}
        elif m == 'alchemy_getTokenMetadata': r = {'symbol': 'X', 'decimals': 18}
        elif m == 'alchemy_getTokenBalances':
            if page_sleep: time.sleep(page_sleep)
            pg = int(p[2]['pageKey']) if len(p) > 2 else 0
            items = [{'contractAddress': a, 'tokenBalance': '0x1'} for a in SPAM[pg * per:(pg + 1) * per]]
            r = {'tokenBalances': items}
            if pg + 1 < PAGES or endless:
                r['pageKey'] = str(pg + 1)
            else:  # ultima pagina: tokens fuera de lista (el indice NO trae USDC)
                r['tokenBalances'] += [{'contractAddress': c, 'tokenBalance': hex(v)}
                                       for c, v in truth.items() if c != USDC and v > 0]
        else:
            raise AssertionError(m)
        return {'jsonrpc': '2.0', 'id': 1, 'result': r}
    return _post


def run(monkeypatch, addr, truth, **kw):
    M._cache.clear()
    monkeypatch.setenv('BASE_RPC_URL', PRIMARY)
    monkeypatch.setitem(M.ALT_RPC, 'base', ALT)
    monkeypatch.setattr(M, '_post', make(truth, **kw))
    t0 = time.time()
    s = M.scan_mainnet('base', addr)
    return s, time.time() - t0


def by_contract(s):
    return {t['contract']: t for t in s['tokens']}


@pytest.mark.parametrize('addr', sorted(CASES))
def test_direcciones_547_todos_los_tokens_con_saldo(monkeypatch, addr):
    truth = CASES[addr]
    s, _ = run(monkeypatch, addr, truth)
    got = by_contract(s)
    for c, v in truth.items():
        if v > 0:
            assert c in got, (addr, c)
            assert got[c].get('balanceStatus') == 'ok'
        else:
            assert c not in got, (addr, c)   # saldo 0 en cadena -> no aparece
    assert got[USDC]['listed'] is True
    assert s['tokensTotalNonZero'] == len(s['tokens'])


def test_token_fuera_de_lista_de_16(monkeypatch):
    otro = '0x' + 'be' * 20
    assert otro not in {t['contract'] for t in M._listed('base')}
    s, _ = run(monkeypatch, '0x' + '22' * 20, {otro: 42})
    got = by_contract(s)
    assert otro in got and got[otro]['listed'] is False and got[otro]['balanceStatus'] == 'ok'


def test_reintento_en_rpc_alternativo(monkeypatch):
    addr = '0x4446adc0b8136ffc55ddb7a488ba5509ace2a5ef'
    s, _ = run(monkeypatch, addr, CASES[addr], fail_primary_batch=True)
    got = by_contract(s)
    for c in (USDC, BRETT, DEGEN):
        assert c in got and got[c]['balanceStatus'] == 'ok'


def test_fallo_total_no_borra_tokens_del_indice(monkeypatch):
    addr = '0x18b0f4547a89fe4c5fe84f258bea3601fa281e9f'
    s, _ = run(monkeypatch, addr, CASES[addr], fail_primary_batch=True, fail_alt_batch=True)
    got = by_contract(s)
    for c in (BRETT, DEGEN):           # detectados por el indice
        assert c in got and got[c]['balanceStatus'] == 'unknown/retry'
    assert s['partial'] is True and s['status'] != 'complete'
    assert ('base', addr) not in M._cache


def test_presupuesto_devuelve_parcial_sin_503(monkeypatch):
    assert M.BUDGET_S < 20
    monkeypatch.setattr(M, 'BUDGET_S', 2.0)
    addr = '0x4446adc0b8136ffc55ddb7a488ba5509ace2a5ef'
    s, dt = run(monkeypatch, addr, CASES[addr], page_sleep=0.3, endless=True)
    assert dt < 2.0 + 1.5, dt
    assert s['partial'] is True
