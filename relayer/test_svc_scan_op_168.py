"""#168: OP Mainnet (chainId 10) en svc_scan: host Alchemy para extras y approvals por logs
alineados con Base (publicnode con filtro address). Arbitrum sin cambios."""
import pytest
import svc_scan as S

KEYURL = 'https://base-mainnet.g.alchemy.com/v2/TESTKEY'


@pytest.fixture
def env(monkeypatch):
    monkeypatch.setenv('BASE_RPC_URL', KEYURL)
    monkeypatch.delenv('UNSWEEP_EXTRAS_RPC', raising=False)
    return monkeypatch


def test_alchemy_host_op():
    assert S._ALCHEMY_HOSTS[10] == 'opt-mainnet.g.alchemy.com'
    assert S._ALCHEMY_HOSTS[8453] == 'base-mainnet.g.alchemy.com'
    assert S._ALCHEMY_HOSTS[42161] == 'arb-mainnet.g.alchemy.com'


def test_extras_url_op_usa_host_op(env):
    env.setattr(S, 'CHAIN_ID', 10)
    assert S._extras_url() == 'https://opt-mainnet.g.alchemy.com/v2/TESTKEY'


def test_extras_url_op_sin_clave_alchemy_none(env):
    env.setattr(S, 'CHAIN_ID', 10)
    env.setenv('BASE_RPC_URL', 'https://mainnet.optimism.io')
    assert S._extras_url() is None


def test_approvals_logs_op_alineado_con_base():
    assert 10 in S.APPROVAL_LOGS_ENABLED and 8453 in S.APPROVAL_LOGS_ENABLED
    assert 42161 not in S.APPROVAL_LOGS_ENABLED  # Arbitrum sin cambios
    assert S.APPROVAL_LOGS_RPC[10] == 'https://optimism-rpc.publicnode.com'
    assert S.APPROVAL_LOGS_RPC[8453] == 'https://base-rpc.publicnode.com'


def test_logs_w3_op_activo_y_arb_inactivo():
    lp = S._logs_w3(10)
    assert lp is not None
    uri = getattr(lp.provider, 'endpoint_uri', '')
    assert 'optimism-rpc.publicnode.com' in str(uri)
    assert S._logs_w3(42161) is None
