"""Tests M4b de integracion policy <-> relayer/svc_scan (sin red: dobles de w3)."""
import types
import pytest
from eth_account import Account

import policy as P
import relayer as R
import svc_scan as S

# Claves efimeras derivadas en tiempo de ejecucion (sin literales; politica #624)
VICTIM_KEY = '0x' + bytes(Account.create().key).hex()
SPONSOR_KEY = '0x' + bytes(Account.create().key).hex()
IMPL = '0x00000000000000000000000000000000000000d1'
USDC = '0x00000000000000000000000000000000000000C0'


class _Fn:
    def __init__(self, v): self.v = v
    def call(self): return self.v


class _Cfg:
    class functions:  # noqa: N801
        pass


@pytest.fixture
def scan_env(monkeypatch):
    monkeypatch.setattr(S, 'config_c', _Cfg)
    monkeypatch.setattr(S, 'w3', types.SimpleNamespace(eth=types.SimpleNamespace(gas_price=10**9)))
    monkeypatch.setattr(S, 'assets', lambda: {'tokens': [{'address': USDC, 'decimals': 6, 'price_usd': 1, 'fee_on_transfer': False}]})
    monkeypatch.setattr(S, 'check_policy', lambda q: None)
    return monkeypatch


def _scan(usd):
    return {'tokens': [{'address': USDC, 'symbol': 'USDC', 'decimals': 6, 'price_usd': 1, 'fee_on_transfer': False, 'balance': str(int(usd * 10**6))}],
            'nfts': []}


@pytest.mark.parametrize('usd,bps', [(500, 1500), (5_000, 1000), (20_000, 500)])
def test_quote_tiers(scan_env, usd, bps):
    scan_env.setattr(S, 'CHAIN_ID', 84532)
    q, _ = S.quote(_scan(usd))
    assert q['maxFeeBps'] == bps and q['feeBps'] == bps
    line = q['lines'][0]
    assert int(line['fee']) == int(line['amount']) * bps // 10000
    assert 'minFee' not in line


def test_quote_never_exposes_gas(scan_env):
    scan_env.setattr(S, 'CHAIN_ID', 84532)
    q, _ = S.quote(_scan(500))
    assert not any('gas' in k.lower() for k in q)


def test_quote_ethereum_min_fee_gas_x15(scan_env):
    scan_env.setattr(S, 'CHAIN_ID', 1)
    scan_env.setattr(S, '_eth_usd', lambda: 3000.0)
    # gas 1.5M * 50 gwei * 3000 = 225 USD -> minimo 337.5 USD; 3.000 USD: tramo 10 % = 300 < 337.5 < techo 450
    scan_env.setattr(S, 'w3', types.SimpleNamespace(eth=types.SimpleNamespace(gas_price=50 * 10**9)))
    q, _ = S.quote(_scan(3_000))
    line = q['lines'][0]
    assert int(line['minFee']) >= int(337.5 * 10**6)
    assert int(line['fee']) == int(line['minFee'])
    assert q['maxFeeBps'] == 1000


def test_policy_error_single_class():
    assert R.PolicyError is P.PolicyError


class _Eth:
    def __init__(self, sim_fail=False, status=1, balance=4 * 10**15):
        self.chain_id = 84532; self.gas_price = 10**9; self.sim_fail = sim_fail; self.status = status
        self.sent = []; self.calls = []; self.balance = balance
    def get_balance(self, a, b='latest'):
        if self.balance is None: raise ConnectionError('rpc caido')
        return self.balance
    def get_transaction_count(self, a, b='latest'): return 0
    def call(self, tx, block='latest'):
        self.calls.append(tx)
        if self.sim_fail: raise ValueError('execution reverted')
        return b''
    def send_raw_transaction(self, raw):
        assert self.calls, 'send sin simulacion previa'
        self.sent.append(raw); return b'\x11' * 32
    def wait_for_transaction_receipt(self, h, timeout=60):
        return {'status': self.status, 'gasUsed': 1_000_000, 'effectiveGasPrice': 2 * 10**9, 'transactionHash': h}


@pytest.fixture
def relay_env(monkeypatch, tmp_path):
    monkeypatch.setattr(P, 'DATA_DIR', tmp_path)
    monkeypatch.setattr(P, 'HUMANO_MD', tmp_path / 'HUMANO.md')
    monkeypatch.setattr(R, 'auth_nonce_still_valid', lambda w3, v, n: True)
    auth = R.sign_auth(VICTIM_KEY, 84532, IMPL, 0)
    victim = Account.from_key(VICTIM_KEY).address
    q = R.Quote(rescued_usd=100.0, fee_usd=15.0, gas_cost_usd=0.01)
    return auth, victim, q, tmp_path


def test_simulation_failure_blocks_send(relay_env):
    auth, victim, q, _ = relay_env
    eth = _Eth(sim_fail=True)
    with pytest.raises(P.PolicyError, match='simulacion'):
        R.send_rescue(types.SimpleNamespace(eth=eth), SPONSOR_KEY, victim, auth, b'\x00', q)
    assert eth.sent == []


def test_simulation_ok_then_send(relay_env):
    auth, victim, q, _ = relay_env
    eth = _Eth()
    rc = R.send_rescue(types.SimpleNamespace(eth=eth), SPONSOR_KEY, victim, auth, b'\x00', q)
    assert rc['status'] == 1 and len(eth.calls) == 1 and len(eth.sent) == 1
    assert 'authorizationList' in eth.calls[0]


def test_revert_records_gas_lost_and_alerts(relay_env):
    auth, victim, q, tmp = relay_env
    eth = _Eth(status=0)
    # 1M gas * 2 gwei = 0.002 ETH * 3000 = 6 USD > 5 USD -> aviso interno
    R.send_rescue(types.SimpleNamespace(eth=eth), SPONSOR_KEY, victim, auth, b'\x00', q, eth_usd=3000.0)
    assert P.gas_lost_total() == pytest.approx(6.0)
    assert 'Gas perdido' in (tmp / 'HUMANO.md').read_text()


def _send(chain_id, q, balance=4 * 10**15):
    eth = _Eth(balance=balance); eth.chain_id = chain_id
    auth = R.sign_auth(VICTIM_KEY, chain_id, IMPL, 0)
    victim = Account.from_key(VICTIM_KEY).address
    rc = R.send_rescue(types.SimpleNamespace(eth=eth), SPONSOR_KEY, victim, auth, b'\x00', q)
    return eth, rc


@pytest.mark.parametrize('chain_id', [8453, 10])
def test_mainnet_base_y_op_enabled(relay_env, chain_id):
    """#81=B: 8453; #163-A: 10 (OP). 1, 42161 y cualquier otra mainnet siguen rechazadas."""
    _, _, q, _ = relay_env
    eth, rc = _send(chain_id, q)
    assert rc['status'] == 1 and len(eth.sent) == 1
    assert R.ACTIVE_MAINNETS == {8453, 10}


@pytest.mark.parametrize('chain_id', [1, 42161, 137, 56])
def test_other_mainnets_rejected(relay_env, chain_id):
    _, _, q, _ = relay_env
    eth = _Eth(); eth.chain_id = chain_id
    auth = R.sign_auth(VICTIM_KEY, chain_id, IMPL, 0)
    with pytest.raises(P.PolicyError, match='no habilitada'):
        R.send_rescue(types.SimpleNamespace(eth=eth), SPONSOR_KEY, Account.from_key(VICTIM_KEY).address, auth, b'\x00', q)
    assert eth.sent == [] and eth.calls == []


@pytest.mark.parametrize('ok', [0, 2, 3, 10])
def test_base_cap_100k(relay_env, ok):
    """#927: 100.000 aceptado, >100.000 rechazado."""
    P.check_cap(8453, 100_000, P.TrackRecord(ok))
    with pytest.raises(P.PolicyError, match='limite'):
        P.check_cap(8453, 100_001, P.TrackRecord(ok))


def test_base_send_over_cap_blocked(relay_env):
    _, _, _, _ = relay_env
    q = R.Quote(rescued_usd=100_001.0, fee_usd=5_000.0, gas_cost_usd=0.01)
    with pytest.raises(P.PolicyError, match='limite'):
        _send(8453, q)


@pytest.mark.parametrize('bal', [5 * 10**15 + 1, None])
def test_base_ops_guard_fail_closed(relay_env, bal):
    """3d: OPS por encima de 0.005 ETH o saldo ilegible => no se patrocina."""
    _, _, q, _ = relay_env
    eth = _Eth(balance=bal); eth.chain_id = 8453
    auth = R.sign_auth(VICTIM_KEY, 8453, IMPL, 0)
    with pytest.raises((P.PolicyError, ConnectionError)):
        R.send_rescue(types.SimpleNamespace(eth=eth), SPONSOR_KEY, Account.from_key(VICTIM_KEY).address, auth, b'\x00', q)
    assert eth.sent == []


def test_ops_low_alerts_once(relay_env):
    _, _, _, tmp = relay_env
    assert P.ops_guard(10**15) == 'low' and P.ops_guard(10**15) == 'low'
    assert (tmp / 'HUMANO.md').read_text().count('Saldo OPS bajo') == 1
    assert P.ops_guard(15 * 10**14) == 'ok' and P.ops_guard(5 * 10**15) == 'ok'
    assert P.ops_status(None) == 'unknown'


def test_ofac_fail_closed(monkeypatch, tmp_path):
    """3c: lista OFAC ausente/vacia/caducada => excepcion (screen no deja pasar)."""
    import json, svc_core as C
    monkeypatch.setattr(C, 'OFAC_FILE', str(tmp_path / 'no_existe.json'))
    with pytest.raises(P.PolicyError, match='OFAC'):
        C.ofac_set()
    f = tmp_path / 'o.json'
    f.write_text(json.dumps({'fetched_at': '2020-01-01T00:00:00+00:00', 'addresses': ['0x' + '1' * 40]}))
    monkeypatch.setattr(C, 'OFAC_FILE', str(f))
    with pytest.raises(P.PolicyError, match='OFAC'):
        C.ofac_set()


def test_quote_ethereum_min_above_cap_rejected(scan_env):
    scan_env.setattr(S, 'CHAIN_ID', 1)
    scan_env.setattr(S, '_eth_usd', lambda: 3000.0)
    scan_env.setattr(S, 'w3', types.SimpleNamespace(eth=types.SimpleNamespace(gas_price=50 * 10**9)))
    with pytest.raises(P.PolicyError, match='techo'):
        P.fee_plan(1, 1000.0, 225.0)
