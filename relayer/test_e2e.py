import json, os, subprocess, time, pathlib
import pytest
from eth_abi import encode
from eth_account import Account
from web3 import Web3
import relayer as R
import eip712 as X

ROOT = pathlib.Path(__file__).resolve().parents[1]
PORT = 8546
SPONSOR = '0xac0974bec39a17e36ba4a6b4d238ff944bacb478cbed5efcae784d7bf4f2ff80'
ATTACKER = '0x59c6995e998f97a5a0044966f0945389dc9e86dae88c7a8412f4603b6b78690d'
FEE_TO = '0x0000000000000000000000000000000000000FEE'
RT = X.RESCUE_TYPEHASH
DT = Web3.keccak(text='EIP712Domain(string name,string version,uint256 chainId,address verifyingContract)')
GOOD = R.Quote(rescued_usd=400, fee_usd=60, gas_cost_usd=0.05)


def art(f, c):
    j = json.load(open(ROOT / 'out' / f / f'{c}.json'))
    return j['abi'], j['bytecode']['object']


@pytest.fixture(scope='module')
def env():
    p = subprocess.Popen([os.path.expanduser('~/.foundry/bin/anvil'), '--hardfork', 'prague', '--port', str(PORT), '--silent'])
    w3 = Web3(Web3.HTTPProvider(f'http://127.0.0.1:{PORT}'))
    for _ in range(50):
        if w3.is_connected(): break
        time.sleep(0.2)
    yield w3
    p.terminate()


def send(w3, key, tx):
    a = Account.from_key(key)
    tx = {'chainId': w3.eth.chain_id, 'nonce': w3.eth.get_transaction_count(a.address, 'pending'), 'gas': 3_000_000,
          'maxFeePerGas': w3.eth.gas_price * 2 + 1, 'maxPriorityFeePerGas': 1, 'value': 0, **tx}
    rc = w3.eth.wait_for_transaction_receipt(w3.eth.send_raw_transaction(a.sign_transaction(tx).raw_transaction))
    assert rc.status == 1
    return rc


def deploy(w3, f, c, types=(), args=()):
    abi, bc = art(f, c)
    rc = send(w3, SPONSOR, {'data': bc + encode(list(types), list(args)).hex()})
    return w3.eth.contract(address=rc.contractAddress, abi=abi)


def world(w3):
    usdc = deploy(w3, 'Mocks.sol', 'MockToken', ['uint8'], [6])
    cfg = deploy(w3, 'UnsweepConfig.sol', 'UnsweepConfig', ['address', 'address', 'uint16', 'address[]'], ['0x0000000000000000000000000000000000000Ab1', FEE_TO, 1500, []])
    impl = deploy(w3, 'UnsweepDelegate.sol', 'UnsweepDelegate', ['address'], [cfg.address])
    victim, safe = Account.create(), Account.create()
    w3.provider.make_request('anvil_setBalance', [victim.address, hex(10**17)])
    send(w3, SPONSOR, {'to': usdc.address, 'data': usdc.encode_abi('mint', [victim.address, 400_000_000])})
    return usdc, impl, victim, safe


def rescue_calldata(w3, impl, victim, safe, usdc):
    nonce = int.from_bytes(os.urandom(32), 'big')
    dl = w3.eth.get_block('latest').timestamp + 3600
    r = X.rescue_tuple(safe.address, [], [usdc.address], [], 1500, [], nonce, dl)
    sig = Account.unsafe_sign_hash(X.rescue_digest(r, w3.eth.chain_id, victim.address), victim.key)
    return bytes.fromhex(impl.encode_abi('rescue', [r, sig.v, sig.r.to_bytes(32, 'big'), sig.s.to_bytes(32, 'big')])[2:])


def test_policy_cap_and_gas():
    R.check_policy(GOOD)
    with pytest.raises(R.PolicyError): R.check_policy(R.Quote(501, 75, 0.05))
    R.check_policy(R.Quote(900, 135, 0.05), cap_usd=1000)  # cap configurable
    with pytest.raises(R.PolicyError): R.check_policy(R.Quote(10, 1.5, 1.0))  # fee < 3x gas
    with pytest.raises(R.PolicyError): R.check_policy(R.Quote(0, 0, 0.01))


def test_chain_id_zero_rejected(env):
    w3 = env
    usdc, impl, victim, safe = world(w3)
    with pytest.raises(R.PolicyError): R.sign_auth(victim.key, 0, impl.address, 0)
    other = R.sign_auth(victim.key, 84532, impl.address, w3.eth.get_transaction_count(victim.address))
    with pytest.raises(R.PolicyError):
        R.send_rescue(w3, SPONSOR, victim.address, other, rescue_calldata(w3, impl, victim, safe, usdc), GOOD)
    ok = R.sign_auth(victim.key, w3.eth.chain_id, impl.address, w3.eth.get_transaction_count(victim.address))
    assert ok.chain_id == w3.eth.chain_id != 0


def test_race_attacker_tx_first_aborts(env):
    w3 = env
    usdc, impl, victim, safe = world(w3)
    auth = R.sign_auth(victim.key, w3.eth.chain_id, impl.address, w3.eth.get_transaction_count(victim.address))
    cd = rescue_calldata(w3, impl, victim, safe, usdc)
    send(w3, victim.key, {'to': Account.from_key(ATTACKER).address, 'value': 10**15})  # atacante usa la EOA
    sp = Account.from_key(SPONSOR).address
    n0 = w3.eth.get_transaction_count(sp)
    with pytest.raises(R.RaceAbort):
        R.send_rescue(w3, SPONSOR, victim.address, auth, cd, GOOD)
    assert w3.eth.get_transaction_count(sp, 'pending') == n0  # el patrocinador no envio nada
    assert usdc.functions.balanceOf(victim.address).call() == 400_000_000


def test_redelegation_from_attacker_sweeper(env):
    w3 = env
    usdc, impl, victim, safe = world(w3)
    sweeper = deploy(w3, 'Mocks.sol', 'AttackerSweeper')
    a_auth = Account.sign_authorization({'chainId': w3.eth.chain_id, 'address': sweeper.address,
                                         'nonce': w3.eth.get_transaction_count(victim.address)}, victim.key)
    send(w3, ATTACKER, {'type': 4, 'to': Account.from_key(ATTACKER).address, 'authorizationList': [a_auth]})
    assert bytes(w3.eth.get_code(victim.address)) == b'\xef\x01\x00' + bytes.fromhex(sweeper.address[2:])
    auth = R.sign_auth(victim.key, w3.eth.chain_id, impl.address, w3.eth.get_transaction_count(victim.address))
    rc = R.send_rescue(w3, SPONSOR, victim.address, auth, rescue_calldata(w3, impl, victim, safe, usdc), GOOD)
    assert rc.status == 1 and rc.type == 4
    assert bytes(w3.eth.get_code(victim.address)) == b'\xef\x01\x00' + bytes.fromhex(impl.address[2:])
    assert usdc.functions.balanceOf(safe.address).call() == 340_000_000
    assert usdc.functions.balanceOf(FEE_TO).call() == 60_000_000
    assert usdc.functions.balanceOf(victim.address).call() == 0
