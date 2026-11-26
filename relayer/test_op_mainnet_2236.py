"""ORDEN #2236 fase A: OP Mainnet (chainId 10) solo diagnostico read-only; rescate deshabilitado."""
import json
import svc_mainnet as M
import op_mainnet as OP
import policy

ADDR = '0x' + '22' * 20
DELEG = '0x' + 'ab' * 20


def fake(code='0x', bal=0):
    def _post(url, body, deadline, tries=5):
        if isinstance(body, list):
            return [{'jsonrpc': '2.0', 'id': c['id'], 'result': '0x0'} for c in body]
        m = body['method']
        if m == 'eth_blockNumber': r = '0x200'
        elif m == 'eth_getCode': r = code
        elif m == 'eth_getTransactionCount': r = '0x3'
        elif m == 'eth_getBalance': r = hex(bal)
        elif m == 'alchemy_getAssetTransfers': r = {'transfers': []}
        elif m == 'alchemy_getTokenBalances': r = {'tokenBalances': []}
        elif m == 'alchemy_getTokenMetadata': r = {'symbol': 'X', 'decimals': 18}
        else: r = '0x0'
        return {'jsonrpc': '2.0', 'id': 1, 'result': r}
    return _post


def run(monkeypatch, **kw):
    M._cache.clear()
    monkeypatch.setenv('OP_RPC_URL', 'http://fake.invalid/rpc')  # solo durante el test
    monkeypatch.setattr(M, '_post', fake(**kw))
    return M.scan_mainnet('optimism', ADDR)


def test_op_config_chain_10():
    c = M.CHAINS['optimism']
    assert c['chain_id'] == 10 == OP.CHAIN_ID
    assert c['env'] == 'OP_RPC_URL' == OP.RPC_ENV
    assert c['explorer'] == 'https://optimistic.etherscan.io/address/' == OP.EXPLORER
    assert c['native'] == 'ETH' and OP.CHAIN_HEX == '0xa'


def test_op_rescate_habilitado_162():
    assert OP.RESCUE_ENABLED is True and OP.UNSWEEP_DELEGATE == '0x38bcF425bC4d13624734e09376F2fafc799fA8c8'
    assert OP.rescue_enabled() is True
    assert 10 in policy.MAINNETS
    import ast
    src = open(__file__.replace('test_op_mainnet_2236.py', 'relayer.py')).read()
    line = [l for l in src.splitlines() if l.strip().startswith('ACTIVE_MAINNETS')][0]
    active = ast.literal_eval(line.split('=', 1)[1].split('#', 1)[0].strip())
    assert active == {8453, 10}  # #163-A: Base + OP; 1 y 42161 siguen fuera


def test_op_assets_coinciden_con_assets_10():
    # fase B: assets_10.json verificado por eth_call; _listed debe reflejarlo exactamente
    import os
    a = json.load(open(os.path.join(os.path.dirname(__file__), 'data', 'assets_10.json')))
    got = [(t['contract'], t['symbol'], t['decimals']) for t in M._listed('optimism')]
    exp = [(t['address'].lower(), t['symbol'], t['decimals']) for t in a['tokens']]
    assert got == exp and len(got) == 8


def test_op_diagnostico_delegacion_7702(monkeypatch):
    s = run(monkeypatch, code='0xef0100' + DELEG[2:], bal=10**15)
    assert s['chainId'] == 10 and s['chain'] == 'optimism'
    assert s['explorer'] == 'https://optimistic.etherscan.io/address/' + ADDR.lower()
    assert s['native']['balanceWei'] == str(10**15)
    assert DELEG in json.dumps(s).lower()


def test_op_diagnostico_sin_delegacion(monkeypatch):
    s = run(monkeypatch)
    assert s['chainId'] == 10
    assert DELEG not in json.dumps(s).lower()


def test_op_rpc_configured_sin_mostrar_valor(monkeypatch):
    monkeypatch.delenv('OP_RPC_URL', raising=False)
    assert OP.rpc_configured() is False
    monkeypatch.setenv('OP_RPC_URL', 'http://x.invalid')
    assert OP.rpc_configured() is True
