"""#718 p.3: en Ethereum la comision es max(tramo, gas x1.5); minFee solo en el token de mayor valor."""
import types

import svc_scan as S
from test_service_policy import scan_env, _scan, USDC  # noqa: F401  (fixture reutilizado)

TKA = '0x00000000000000000000000000000000000000A1'
TKB = '0x00000000000000000000000000000000000000B2'


def _scan_multi(usds):
    addrs = [USDC, TKA, TKB]
    return {'tokens': [{'address': addrs[i], 'symbol': f'T{i}', 'decimals': 6, 'price_usd': 1, 'fee_on_transfer': False,
                        'balance': str(int(u * 10**6))} for i, u in enumerate(usds)], 'nfts': []}


def _eth_env(env):
    env.setattr(S, 'CHAIN_ID', 1)
    env.setattr(S, '_eth_usd', lambda: 3000.0)  # oraculo ETH/USD simulado (fail-closed en prod)
    env.setattr(S, 'assets', lambda: {'tokens': [{'address': x, 'decimals': 6, 'fee_on_transfer': False}
                                                 for x in (USDC, TKA, TKB)]})  # allowlist del test
    # gas 1.5M * 50 gwei * 3000 USD = 225 USD -> minimo M = 337.5 USD
    env.setattr(S, 'w3', types.SimpleNamespace(eth=types.SimpleNamespace(gas_price=50 * 10**9)))
    return 337.5


def test_min_fee_single_token_not_multiplied(scan_env):  # noqa: F811
    m = _eth_env(scan_env)
    q, _ = S.quote(_scan_multi([1_500, 1_000, 500]))   # 3.000 USD, tramo 10 % = 300 < M
    mins = [int(line['minFee']) for line in q['lines']]
    assert sum(1 for x in mins if x > 0) == 1 and mins[0] > 0   # solo el token de mayor valor
    assert mins[1] == 0 and mins[2] == 0
    tier_usd = 3_000 * q['maxFeeBps'] / 10_000
    expected = max(tier_usd, m)
    assert abs(q['fee_usd'] - expected) < 1e-4               # max(tramo, gas x1.5), no 3 x M
    assert q['fee_usd'] < 2 * m
    q1, _ = S.quote(_scan(3_000))                             # mismo valor en un solo token
    assert abs(q1['fee_usd'] - q['fee_usd']) < 1e-4
    for line in q['lines']:
        assert int(line['fee']) == max(int(line['amount']) * q['maxFeeBps'] // 10000, int(line['minFee']))
        assert int(line['net']) == int(line['amount']) - int(line['fee'])


def test_min_fee_zero_when_tier_dominates(scan_env):  # noqa: F811
    _eth_env(scan_env)
    q, _ = S.quote(_scan_multi([10_000, 6_000, 4_000]))     # 20.000 USD, tramo 5 % = 1.000 > M
    assert q['maxFeeBps'] == 500
    assert all('minFee' not in line for line in q['lines'])
    assert abs(q['fee_usd'] - 1_000) < 1e-4
