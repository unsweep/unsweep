"""ORDEN #2236 fase B: configuracion OP (chainId 10) sin red. Solo direcciones con fuente en el repo + eth_call."""
import json
from pathlib import Path

import op_mainnet as OP
import policy

H = Path(__file__).parent
ROOT = H.parent
A = json.loads((H / 'data' / 'assets_10.json').read_text())
A42 = json.loads((H / 'data' / 'assets_42161.json').read_text())
LOG = json.loads((ROOT / 'artifacts' / 'm2236' / 'onchain_10.json').read_text())
TL = json.loads((ROOT / 'evidence' / 'chainlink' / 'superchain.tokenlist.json').read_text())
FD = json.loads((ROOT / 'evidence' / 'chainlink' / 'feeds-ethereum-mainnet-optimism-1.json').read_text())
TL10 = {t['address'].lower(): t for t in TL['tokens'] if t.get('chainId') == 10}
PROXIES = {f['proxyAddress'].lower(): f for f in FD if f.get('proxyAddress')}


def test_formato_igual_que_arbitrum():
    assert A['chainId'] == 10
    assert set(A.keys()) == set(A42.keys())
    assert set(A['eth_usd_feed'].keys()) == set(A42['eth_usd_feed'].keys())
    for t in A['tokens']:
        assert set(A42['tokens'][0].keys()) <= set(t.keys())
        assert set(t['feed'].keys()) >= {'address', 'pair', 'quote', 'heartbeat', 'decimals'}


def test_tokens_con_fuente_en_repo_y_evidencia():
    syms = [t['symbol'] for t in A['tokens']]
    assert syms == ['USDC', 'USDT', 'DAI', 'WETH', 'OP', 'WBTC', 'LINK', 'wstETH']
    for t in A['tokens']:
        src = TL10.get(t['address'].lower())
        assert src and src['symbol'] == t['symbol'] and src['decimals'] == t['decimals']
        assert 'eth_call' in t['_evidence']['token'] and 'eth_call' in t['_evidence']['feed']
        assert t['fee_on_transfer'] is False


def test_feeds_en_directorio_oficial_usd():
    feeds = [A['eth_usd_feed']] + [t['feed'] for t in A['tokens']]
    for f in feeds:
        rec = PROXIES.get(f['address'].lower())
        assert rec and rec['name'] == f['pair'] and f['pair'].endswith(' / USD')
        assert f['quote'] == 'USD' and int(rec['heartbeat']) == f['heartbeat'] and int(rec['decimals']) == f['decimals']
    assert A['eth_usd_feed']['pair'] == 'ETH / USD'


def test_evidencia_onchain_ok_mismo_bloque():
    assert LOG['chainId'] == 10 and LOG['block'] == A['_verified']['block']
    ok_feeds = {f['address'].lower() for f in LOG['feeds'] if f['ok'] and not f['problems']}
    for t in A['tokens']:
        assert t['feed']['address'].lower() in ok_feeds
        e = [x for x in LOG['tokens'] if x['address'].lower() == t['address'].lower()]
        assert len(e) == 1 and e[0]['symbol_onchain'] == t['symbol'] and e[0]['decimals_onchain'] == t['decimals']
        assert e[0]['code_bytes'] > 0
    assert A['eth_usd_feed']['address'].lower() in ok_feeds


def test_exclusiones():
    addrs = {t['address'].lower() for t in A['tokens']}
    assert '0x7f5c764cbc14f9669b88837ca1490cca17c31607' not in addrs  # USDC.e
    assert '0xdeaddeaddeaddeaddeaddeaddeaddeaddead0000' not in addrs  # ETH legacy OVM


def test_rescate_op_habilitado_162():
    assert OP.UNSWEEP_DELEGATE == '0x38bcF425bC4d13624734e09376F2fafc799fA8c8' and OP.rescue_enabled() is True
    assert 10 in policy.MAINNETS
