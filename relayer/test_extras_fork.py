"""#985 Tokens extra sin garantia, probados en un fork de Base (anvil --fork-url BASE_RPC_URL).
Si BASE_RPC_URL no existe (CI), corre sobre anvil local con la misma logica. La URL nunca se imprime.
El token que revierte se crea con anvil_setCode solo dentro del test: no se toca ningun contrato del repo."""
import os, pathlib, subprocess, time
import pytest
from eth_account import Account
from web3 import Web3
import relayer as R
import eip712 as X
import extras as EX
from test_e2e import SPONSOR, FEE_TO, GOOD, deploy, send, world

PORT = 8547
REVERT_CODE = '0x60006000fd'  # PUSH1 0 PUSH1 0 REVERT: revierte en cualquier llamada


def _base_rpc():
    v = os.environ.get('BASE_RPC_URL')
    if v:
        return v
    p = pathlib.Path('/opt/aire/product.env')
    try:
        for line in p.read_text().splitlines():
            if line.startswith('BASE_RPC_URL='):
                return line.split('=', 1)[1].strip().strip('"').strip("'") or None
    except OSError:
        return None
    return None


@pytest.fixture(scope='module')
def fork():
    url = _base_rpc()
    cmd = [os.path.expanduser('~/.foundry/bin/anvil'), '--port', str(PORT), '--silent']
    cmd += ['--fork-url', url] if url else ['--hardfork', 'prague']
    p = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    w3 = Web3(Web3.HTTPProvider(f'http://127.0.0.1:{PORT}', request_kwargs={'timeout': 60}))
    for _ in range(150):
        if w3.is_connected():
            break
        time.sleep(0.2)
    assert w3.is_connected()
    w3.forked = bool(url)
    yield w3
    p.terminate()


def _sim(w3):
    return (lambda tx: w3.eth.call(tx), lambda tx: w3.eth.estimate_gas(tx))


def _setup(w3):
    usdc, impl, victim, safe = world(w3)
    good = deploy(w3, 'Mocks.sol', 'MockToken', ['uint8'], [18])
    send(w3, SPONSOR, {'to': good.address, 'data': good.encode_abi('mint', [victim.address, 1000 * 10**18])})
    bad = Web3.to_checksum_address('0x' + os.urandom(20).hex())
    w3.provider.make_request('anvil_setCode', [bad, REVERT_CODE])
    extras = [{'address': bad, 'symbol': 'BAD', 'decimals': 18, 'balance': str(10**18), 'unverified': True},
              {'address': good.address, 'symbol': 'GOOD', 'decimals': 18, 'balance': str(1000 * 10**18), 'unverified': True}]
    return usdc, impl, victim, safe, good, bad, extras


def test_fork_is_base_when_available(fork):
    if fork.forked:
        assert fork.eth.chain_id == 8453


def test_reverting_extra_excluded(fork):
    w3 = fork
    usdc, impl, victim, safe, good, bad, extras = _setup(w3)
    assert EX.simulate_extra(_sim(w3), victim.address, safe.address, extras[0]) is None
    sel, why = EX.select_extras(_sim(w3), victim.address, safe.address, extras, 1, 60.0, 200_000,
                                w3.eth.gas_price, 3000.0)
    assert why is None
    assert [e['address'] for e in sel] == [good.address]
    lines = EX.extra_lines(sel, 1500)
    assert lines[0]['minFee'] == '0' and lines[0]['unverified'] is True


def test_no_listed_no_extras(fork):
    w3 = fork
    _, _, victim, safe, _, _, extras = _setup(w3)
    sel, why = EX.select_extras(_sim(w3), victim.address, safe.address, extras, 0, 60.0, 200_000, w3.eth.gas_price, 3000.0)
    assert sel == [] and why


def test_fee_not_covering_gas_drops_all_extras(fork):
    w3 = fork
    _, _, victim, safe, _, _, extras = _setup(w3)
    sel, why = EX.select_extras(_sim(w3), victim.address, safe.address, extras, 1, 0.0, 200_000, max(w3.eth.gas_price, 1), 3000.0)
    assert sel == [] and why


def test_rescue_listed_plus_selected_extras(fork):
    w3 = fork
    usdc, impl, victim, safe, good, bad, extras = _setup(w3)
    sel, _ = EX.select_extras(_sim(w3), victim.address, safe.address, extras, 1, 60.0, 200_000, w3.eth.gas_price, 3000.0)
    tokens = [usdc.address] + [e['address'] for e in sel]
    assert bad not in tokens
    nonce = int.from_bytes(os.urandom(32), 'big')
    dl = w3.eth.get_block('latest').timestamp + 3600
    r = X.rescue_tuple(safe.address, [], tokens, [], 1500, [0] * len(tokens), nonce, dl)
    sig = Account.unsafe_sign_hash(X.rescue_digest(r, w3.eth.chain_id, victim.address), victim.key)
    cd = bytes.fromhex(impl.encode_abi('rescue', [r, sig.v, sig.r.to_bytes(32, 'big'), sig.s.to_bytes(32, 'big')])[2:])
    # #84: la wallet OPS real nunca supera 0.005 ETH; se reproduce ese estado (no se relaja la politica)
    w3.provider.make_request('anvil_setBalance', [Account.from_key(SPONSOR).address, hex(4 * 10**15)])
    auth = R.sign_auth(victim.key, w3.eth.chain_id, impl.address, w3.eth.get_transaction_count(victim.address))
    rc = R.send_rescue(w3, SPONSOR, victim.address, auth, cd, GOOD)
    assert rc.status == 1
    assert usdc.functions.balanceOf(safe.address).call() == 340_000_000
    assert usdc.functions.balanceOf(FEE_TO).call() == 60_000_000
    net = int(EX.extra_lines(sel, 1500)[0]['net'])
    assert good.functions.balanceOf(safe.address).call() == net == 850 * 10**18
    assert good.functions.balanceOf(victim.address).call() == 0
