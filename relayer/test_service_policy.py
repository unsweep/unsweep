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
    scan_env.setattr(S, 'ETH_USD', 3000.0)
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
    def __init__(self, sim_fail=False, status=1):
        self.chain_id = 84532; self.gas_price = 10**9; self.sim_fail = sim_fail; self.status = status
        self.sent = []; self.calls = []
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


def test_mainnet_disabled_by_default(relay_env):
    auth, victim, q, _ = relay_env
    eth = _Eth(); eth.chain_id = 8453
    with pytest.raises(P.PolicyError):
        R.send_rescue(types.SimpleNamespace(eth=eth), SPONSOR_KEY, victim, auth, b'\x00', q)
    assert eth.sent == []


def test_quote_ethereum_min_above_cap_rejected(scan_env):
    scan_env.setattr(S, 'CHAIN_ID', 1)
    scan_env.setattr(S, 'ETH_USD', 3000.0)
    scan_env.setattr(S, 'w3', types.SimpleNamespace(eth=types.SimpleNamespace(gas_price=50 * 10**9)))
    with pytest.raises(P.PolicyError, match='techo'):
        P.fee_plan(1, 1000.0, 225.0)
