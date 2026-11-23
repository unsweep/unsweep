"""#1658b regresion: /api/scan mainnet perdia USDC/BRETT/DEGEN en wallets con spam
(1 sola pagina de alchemy_getTokenBalances, corte a 15 sin priorizar, sin balanceOf de la lista)."""
import os, json
import svc_mainnet as M

ADDR = '0x' + '11' * 20
USDC = '0x833589fcd6edb6e08f4c7c32d4f71b54bda02913'
DEGEN = '0x4ed4e862860bed51a9570b96d89af5e1b0efefed'
SPAM = ['0x' + ('%040x' % (0xabc000 + i)) for i in range(100)]
SPAM_SET = set(SPAM)


def fake(fail_discovery=False, fail_batch=False, usdc=5_000_000):
    def _post(url, body, deadline, tries=5):
        if isinstance(body, list):
            if fail_batch:
                raise M.ScanError('rpc http 503')
            out = []
            for c in body:
                to = c['params'][0]['to'].lower()
                # verdad en cadena coherente con el indice simulado
                v = usdc if to == USDC else 7 if to == DEGEN else 1 if to in SPAM_SET else 0
                out.append({'jsonrpc': '2.0', 'id': c['id'], 'result': hex(v)})
            return out
        m, p = body['method'], body['params']
        if m == 'eth_blockNumber': r = '0x100'
        elif m == 'eth_getCode': r = '0x'
        elif m in ('eth_getTransactionCount', 'eth_getBalance'): r = '0x0'
        elif m == 'alchemy_getAssetTransfers': r = {'transfers': []}
        elif m == 'alchemy_getTokenMetadata': r = {'symbol': 'X', 'decimals': 18}
        elif m == 'alchemy_getTokenBalances':
            if fail_discovery:
                return {'jsonrpc': '2.0', 'id': 1, 'error': {'code': -32000, 'message': 'x'}}
            if len(p) < 3:  # pagina 1: solo spam (USDC no aparece en el indice)
                r = {'tokenBalances': [{'contractAddress': a, 'tokenBalance': '0x1'} for a in SPAM],
                     'pageKey': 'k2'}
            else:
                r = {'tokenBalances': [{'contractAddress': DEGEN, 'tokenBalance': hex(7)},
                                       {'contractAddress': SPAM[0], 'tokenBalance': '0x0'}]}
        else:
            raise AssertionError(m)
        return {'jsonrpc': '2.0', 'id': 1, 'result': r}
    return _post


def run(monkeypatch, **kw):
    M._cache.clear()
    monkeypatch.setenv('BASE_RPC_URL', 'http://fake.invalid/rpc')  # solo durante el test
    monkeypatch.setattr(M, '_post', fake(**kw))
    return M.scan_mainnet('base', ADDR)


def contracts(s):
    return {t['contract'] for t in s['tokens']}


def test_paginacion_y_token_fuera_de_lista(monkeypatch):
    s = run(monkeypatch)
    c = contracts(s)
    assert USDC in c and DEGEN in c          # listado via balanceOf + fuera de lista en pagina 2
    assert s['tokensTotalNonZero'] == len(s['tokens']) == 102
    assert s['tokens'][0]['contract'] == USDC and s['tokens'][0]['listed'] is True
    assert s['status'] == 'complete', s['incompleteReasons']


def test_fallo_descubrimiento_no_pierde_lista(monkeypatch):
    s = run(monkeypatch, fail_discovery=True)
    assert USDC in contracts(s)
    assert s['status'] == 'incomplete'
    assert any('token balances failed' in r for r in s['incompleteReasons'])
    assert ('base', ADDR) not in M._cache


def test_fallo_balanceof_es_explicito(monkeypatch):
    s = run(monkeypatch, fail_batch=True)
    assert any('balanceOf' in r for r in s['incompleteReasons'])
    assert s['status'] == 'incomplete' and ('base', ADDR) not in M._cache
    assert DEGEN in contracts(s)  # el descubrimiento sigue funcionando
