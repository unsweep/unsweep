"""#1011/#1012: tests en fork LOCAL de Arbitrum One (42161). Solo anvil local via proxy RPC de solo
lectura (fork_arb_common). Nunca se envia nada a mainnet. Sin proxy (CI) el modulo se salta."""
import json
import os
import pathlib
import time

import pytest
from eth_abi import encode
from eth_account import Account
from web3 import Web3

import fork_arb_common as F
import oracle as O
import policy as P
import relayer as R
import sequencer as SEQ
import test_e2e as E

pytestmark = pytest.mark.skipif(not F.proxy_ok(), reason='sin proxy RPC de Arbitrum (fork local no disponible)')

ASSETS = pathlib.Path(__file__).resolve().parent / 'data' / 'assets_42161.json'
USDC_E = '0xFF970A61A04b1cA14834A43f5dE4533eBDDB5CC8'  # USDC puenteado: NO debe estar
TEST_OWNER = Account.create()  # owner de pruebas, nunca la wallet fria
ERC20 = [{'name': 'balanceOf', 'type': 'function', 'stateMutability': 'view', 'inputs': [{'name': 'a', 'type': 'address'}],
          'outputs': [{'name': '', 'type': 'uint256'}]},
         {'name': 'transfer', 'type': 'function', 'stateMutability': 'nonpayable',
          'inputs': [{'name': 'to', 'type': 'address'}, {'name': 'v', 'type': 'uint256'}], 'outputs': [{'name': '', 'type': 'bool'}]}]
# bytecode minimo que responde a latestRoundData con 5 palabras
SEQ_DOWN = '0x600160205260a06000f3'        # answer=1 (secuenciador caido)
SEQ_GRACE = '0x600a420360405260a06000f3'   # answer=0, startedAt=block.timestamp-10
REVERTER = '0x60006000fd'                  # cualquier llamada revierte


@pytest.fixture(scope='module')
def fork():
    p, w3 = F.start_anvil()
    w3.provider.make_request('anvil_setBalance', [Account.from_key(E.SPONSOR).address, hex(10**20)])
    yield w3
    p.terminate()


def _deploy(w3, f, c, types, args):
    abi, bc = E.art(f, c)
    rc = E.send(w3, E.SPONSOR, {'data': bc + encode(list(types), list(args)).hex(), 'gas': 6_000_000})
    return w3.eth.contract(address=rc.contractAddress, abi=abi), rc


def _system(w3, bps, fee_to):
    cfg, rc1 = _deploy(w3, 'UnsweepConfig.sol', 'UnsweepConfig', ['address', 'address', 'uint16', 'address[]'],
                       [TEST_OWNER.address, fee_to, bps, []])
    impl, rc2 = _deploy(w3, 'UnsweepDelegate.sol', 'UnsweepDelegate', ['address'], [cfg.address])
    return cfg, impl, rc1, rc2


def _fund_victim(w3, amount):
    usdc = w3.eth.contract(address=F.USDC, abi=ERC20)
    victim, safe = Account.create(), Account.create()
    w3.provider.make_request('anvil_setBalance', [victim.address, hex(10**17)])
    how = F.set_usdc_balance(w3, victim.address, amount)  # sin eth_getLogs historico
    assert usdc.functions.balanceOf(victim.address).call() == amount, how
    return usdc, victim, safe


def _rescue(w3, impl, victim, safe, tokens, bps):
    dl = w3.eth.get_block('latest').timestamp + 3600
    r = E.X.rescue_tuple(safe.address, [], tokens, [], bps, [], int.from_bytes(os.urandom(32), 'big'), dl)
    sig = Account.unsafe_sign_hash(E.X.rescue_digest(r, w3.eth.chain_id, victim.address), victim.key)
    cd = impl.encode_abi('rescue', [r, sig.v, sig.r.to_bytes(32, 'big'), sig.s.to_bytes(32, 'big')])
    auth = R.sign_auth(victim.key, w3.eth.chain_id, impl.address, w3.eth.get_transaction_count(victim.address))
    return auth, cd


def _send_raw(w3, tx):  # como E.send pero sin exigir status=1
    a = Account.from_key(E.SPONSOR)
    tx = {'chainId': w3.eth.chain_id, 'nonce': w3.eth.get_transaction_count(a.address, 'pending'), 'gas': 3_000_000,
          'maxFeePerGas': w3.eth.gas_price * 2 + 1, 'maxPriorityFeePerGas': 1, 'value': 0, **tx}
    return w3.eth.wait_for_transaction_receipt(w3.eth.send_raw_transaction(a.sign_transaction(tx).raw_transaction))


def test_assets_42161_clean():
    a = json.loads(ASSETS.read_text())
    addrs = {Web3.to_checksum_address(t['address']) for t in a['tokens']}
    syms = {t['symbol'] for t in a['tokens']}
    assert Web3.to_checksum_address(F.USDC) in addrs and Web3.to_checksum_address(USDC_E) not in addrs
    assert not syms & {'EURC', 'USDC.e'}
    for t in a['tokens']:
        assert t['feed']['address'] and t['feed']['heartbeat'] > 0 and t['feed']['decimals'] in (8, 18)


@pytest.mark.parametrize('usd,bps', [(400, 1500), (2_000, 1000), (12_000, 500)])
def test_rescue_native_usdc_fee_tiers(fork, usd, bps):
    w3 = fork
    assert w3.eth.chain_id == 42161 and P.tier_bps(usd) == bps
    fee_to = Account.create().address
    cfg, impl, rc1, rc2 = _system(w3, bps, fee_to)
    assert cfg.functions.owner().call() == TEST_OWNER.address != Web3.to_checksum_address(F.COLD)
    amount = usd * 10**6
    usdc, victim, safe = _fund_victim(w3, amount)
    auth, cd = _rescue(w3, impl, victim, safe, [F.USDC], bps)
    rc = E.send(w3, E.SPONSOR, {'type': 4, 'to': victim.address, 'data': cd, 'authorizationList': [auth]})
    assert rc.status == 1 and rc.type == 4
    fee = amount * bps // 10_000
    assert usdc.functions.balanceOf(fee_to).call() == fee
    assert usdc.functions.balanceOf(safe.address).call() == amount - fee
    assert usdc.functions.balanceOf(victim.address).call() == 0
    F.rec_gas('deploy_config', rc1.gasUsed)
    F.rec_gas('deploy_delegate', rc2.gasUsed)
    F.rec_gas('rescue_usdc_%d' % bps, rc.gasUsed)
    F.rec_gas('fork_gas_price_wei', w3.eth.gas_price)


def test_cap_100k_and_controls_above_10k(tmp_path):
    tr, hm = P.TrackRecord(), tmp_path / 'H.md'
    P.check_cap(42161, 10_000, tr, humano_md=hm)
    P.check_cap(42161, 100_000, tr, humano_md=hm)
    with pytest.raises(P.PolicyError):
        P.check_cap(42161, 100_000.01, tr, humano_md=hm)
    assert not P.needs_extra_checks(10_000) and P.needs_extra_checks(10_000.01)
    hb = {t['symbol']: t['feed']['heartbeat'] for t in json.loads(ASSETS.read_text())['tokens']}['USDC']
    it = lambda age: {'symbol': 'USDC', 'value_usd': 20_000, 'price_usd': 1.0, 'price_feeds': [{'age_s': age, 'heartbeat_s': hb}]}
    P.check_high_value(20_000, [it(hb)])
    with pytest.raises(P.PolicyError, match='desactualizado'):
        P.check_high_value(20_000, [it(hb + 1)])


def test_sequencer_uptime_feed(fork):
    w3 = fork
    assert SEQ.FEEDS[42161] == F.SEQ_FEED
    st = SEQ.check(w3, 42161)  # feed real en el bloque del fork
    assert st['answer'] == 0 and st['now'] - st['startedAt'] >= SEQ.GRACE_PERIOD_S
    for code, msg in ((SEQ_DOWN, 'caido'), (SEQ_GRACE, 'gracia'), ('0x', 'no se pudo leer')):
        snap = w3.provider.make_request('evm_snapshot', [])['result']
        try:
            w3.provider.make_request('anvil_setCode', [F.SEQ_FEED, code])
            with pytest.raises(SEQ.SequencerError, match=msg):
                SEQ.check(w3, 42161)
        finally:
            w3.provider.make_request('evm_revert', [snap])
    assert SEQ.check(w3, 42161)['answer'] == 0
    now = int(time.time())
    with pytest.raises(SEQ.SequencerError, match='gracia'):
        SEQ.validate(0, now - SEQ.GRACE_PERIOD_S + 1, now)
    SEQ.validate(0, now - SEQ.GRACE_PERIOD_S, now)


def test_reverting_token_excluded(fork):
    w3 = fork
    bad = Web3.to_checksum_address('0x' + os.urandom(20).hex())
    w3.provider.make_request('anvil_setCode', [bad, REVERTER])
    allowed = O.allowlist(json.loads(ASSETS.read_text()))
    assert bad not in allowed and Web3.to_checksum_address(F.USDC) in allowed  # capa 1: fuera de la allowlist
    fee_to = Account.create().address
    cfg, impl, _, _ = _system(w3, 1500, fee_to)
    amount = 400 * 10**6
    usdc, victim, safe = _fund_victim(w3, amount)
    auth, cd = _rescue(w3, impl, victim, safe, [F.USDC, bad], 1500)
    rc = _send_raw(w3, {'type': 4, 'to': victim.address, 'data': cd, 'authorizationList': [auth]})
    assert rc.status == 0  # capa 2: en cadena el rescate entero revierte; no se mueve nada
    assert usdc.functions.balanceOf(victim.address).call() == amount
    assert usdc.functions.balanceOf(fee_to).call() == 0
    auth, cd = _rescue(w3, impl, victim, safe, [F.USDC], 1500)  # cesta sin el token: OK
    rc = E.send(w3, E.SPONSOR, {'type': 4, 'to': victim.address, 'data': cd, 'authorizationList': [auth]})
    assert rc.status == 1 and usdc.functions.balanceOf(safe.address).call() == amount - amount * 1500 // 10_000


def test_arbitrum_active_but_send_rescue_fail_closed(fork):
    # #125=A: 42161 activa en mainnet; Ethereum (1) sigue bloqueada (#81=B)
    w3 = fork
    assert 42161 in R.ACTIVE_MAINNETS and 1 not in R.ACTIVE_MAINNETS
    v = Account.create()
    auth = R.sign_auth(v.key, 42161, F.USDC, 0)
    sponsor = Account.from_key(E.SPONSOR).address
    n0 = w3.eth.get_transaction_count(sponsor, 'pending')
    # #234/#1130 endurecido: 42161 supera la puerta de cadena y la POLITICA bloquea antes de enviar (fail-closed)
    sent = []
    real_send = w3.eth.send_raw_transaction
    w3.eth.send_raw_transaction = lambda raw: sent.append(raw) or (_ for _ in ()).throw(
        AssertionError('send_raw_transaction no debe llamarse'))
    try:
        with pytest.raises(P.PolicyError) as ei:
            R.send_rescue(w3, E.SPONSOR, v.address, auth, b'', E.GOOD)
    finally:
        w3.eth.send_raw_transaction = real_send
    msg = str(ei.value)
    print('send_rescue_42161_bloqueo:', msg)
    assert type(ei.value) is P.PolicyError  # no RaceAbort ni error generico
    assert 'no habilitada' not in msg  # 42161 ya esta activa: el bloqueo es de politica, no de cadena
    assert sent == []  # nunca se intento enviar
    assert w3.eth.get_transaction_count(sponsor, 'pending') == n0  # 0 tx enviadas
