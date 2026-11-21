"""UNSWEEP M2b escaner y simulacion (neto y comision). Solo lectura; nunca firma."""
import os
from web3 import Web3

from relayer import Quote, PolicyError, check_policy
from svc_core import w3, abi, assets, log, CHAIN_ID, DELEGATE, CONFIG, ETH_USD

APPROVAL_LOOKBACK = int(os.environ.get('UNSWEEP_APPROVAL_LOOKBACK', '9000'))
LOG_CHUNK = 2000

ERC20 = [{'name': 'balanceOf', 'type': 'function', 'stateMutability': 'view', 'inputs': [{'name': 'a', 'type': 'address'}], 'outputs': [{'type': 'uint256'}]},
         {'name': 'allowance', 'type': 'function', 'stateMutability': 'view', 'inputs': [{'name': 'o', 'type': 'address'}, {'name': 's', 'type': 'address'}], 'outputs': [{'type': 'uint256'}]}]
ERC721 = [{'name': 'ownerOf', 'type': 'function', 'stateMutability': 'view', 'inputs': [{'name': 'i', 'type': 'uint256'}], 'outputs': [{'type': 'address'}]},
          {'name': 'isApprovedForAll', 'type': 'function', 'stateMutability': 'view', 'inputs': [{'name': 'o', 'type': 'address'}, {'name': 'op', 'type': 'address'}], 'outputs': [{'type': 'bool'}]}]


def h0x(b):
    s = b.hex() if hasattr(b, 'hex') else str(b)
    return s if s.startswith('0x') else '0x' + s


T_APPROVAL = h0x(Web3.keccak(text='Approval(address,address,uint256)'))
T_APPROVAL_ALL = h0x(Web3.keccak(text='ApprovalForAll(address,address,bool)'))
config_c = w3.eth.contract(address=CONFIG, abi=abi('UnsweepConfig.sol', 'UnsweepConfig'))


def delegation_of(addr):
    code = bytes(w3.eth.get_code(addr))
    if len(code) == 23 and code[:3] == b'\xef\x01\x00':
        return Web3.to_checksum_address(code[3:])
    return None


def live_approvals(addr):
    out, seen = [], set()
    head = w3.eth.block_number
    owner_topic = '0x' + '0' * 24 + addr[2:].lower()
    start = max(0, head - APPROVAL_LOOKBACK)
    for topic in (T_APPROVAL, T_APPROVAL_ALL):
        frm = start
        while frm <= head:
            to = min(head, frm + LOG_CHUNK - 1)
            try:
                logs = w3.eth.get_logs({'fromBlock': frm, 'toBlock': to, 'topics': [topic, owner_topic]})
            except Exception as e:
                log.warning('get_logs %s: %s', topic[:10], type(e).__name__)
                logs = []
            for lg in logs:
                if len(lg['topics']) < 3:
                    continue
                spender = Web3.to_checksum_address('0x' + h0x(lg['topics'][2])[-40:])
                key = (lg['address'], spender, topic)
                if key in seen:
                    continue
                seen.add(key)
                try:
                    if topic == T_APPROVAL_ALL:
                        if w3.eth.contract(address=lg['address'], abi=ERC721).functions.isApprovedForAll(addr, spender).call():
                            out.append({'token': lg['address'], 'spender': spender, 'type': 'ApprovalForAll'})
                    else:
                        amt = w3.eth.contract(address=lg['address'], abi=ERC20).functions.allowance(addr, spender).call()
                        if amt > 0:
                            out.append({'token': lg['address'], 'spender': spender, 'type': 'ERC20', 'amount': str(amt)})
                except Exception:
                    pass  # ERC-721 Approval (3 topics indexados) u otros: se ignoran
            frm = to + 1
    return out


def scan(addr):
    addr = Web3.to_checksum_address(addr)
    a = assets()
    tokens, nfts = [], []
    for t in a['tokens']:
        bal = w3.eth.contract(address=Web3.to_checksum_address(t['address']), abi=ERC20).functions.balanceOf(addr).call()
        if bal > 0:
            tokens.append({**t, 'balance': str(bal)})
    for n in a['nfts']:
        c = w3.eth.contract(address=Web3.to_checksum_address(n['address']), abi=ERC721)
        for i in n.get('ids', []):
            try:
                if c.functions.ownerOf(int(i)).call() == addr:
                    nfts.append({'address': n['address'], 'symbol': n.get('symbol', ''), 'id': str(i)})
            except Exception:
                pass
    deleg = delegation_of(addr)
    return {'address': addr, 'chainId': CHAIN_ID, 'eth_wei': str(w3.eth.get_balance(addr)),
            'nonce': w3.eth.get_transaction_count(addr, 'pending'),
            'delegation7702': deleg, 'delegatedToUnsweep': deleg == DELEGATE,
            'tokens': tokens, 'nfts': nfts, 'approvals': live_approvals(addr),
            'rescuable': bool(tokens or nfts)}


def quote(s, gas=1_500_000):
    fee_bps = config_c.functions.feeBps().call()
    nft_fee = config_c.functions.nftFlatFee().call()
    nft_tok = config_c.functions.nftFeeToken().call()
    lines, rescued_usd, fee_usd = [], 0.0, 0.0
    for t in s['tokens']:
        bal = int(t['balance']); fee = bal * fee_bps // 10000
        dec = int(t.get('decimals', 18)); px = float(t.get('price_usd', 0))
        rescued_usd += bal / 10**dec * px; fee_usd += fee / 10**dec * px
        lines.append({'token': t['address'], 'symbol': t.get('symbol', ''), 'decimals': dec,
                      'amount': str(bal), 'fee': str(fee), 'net': str(bal - fee)})
    n_nft = len(s['nfts']); nft_total = nft_fee * n_nft
    tok_meta = next((t for t in assets()['tokens'] if t['address'].lower() == nft_tok.lower()), {})
    fee_usd += nft_total / 10**int(tok_meta.get('decimals', 6)) * float(tok_meta.get('price_usd', 0))
    rescued_usd += sum(float(n.get('value_usd', 0)) for n in s['nfts'])
    gas_cost_usd = gas * w3.eth.gas_price / 1e18 * ETH_USD
    q = Quote(rescued_usd=rescued_usd, fee_usd=fee_usd, gas_cost_usd=gas_cost_usd)
    try:
        check_policy(q); ok, why = True, None
    except PolicyError as e:
        ok, why = False, str(e)
    return {'feeBps': fee_bps, 'lines': lines, 'nfts': n_nft, 'nftFeeEach': str(nft_fee), 'nftFeeToken': nft_tok,
            'nftFeeTotal': str(nft_total), 'rescued_usd': round(rescued_usd, 4), 'fee_usd': round(fee_usd, 4),
            'gas_cost_usd_paid_by_unsweep': round(gas_cost_usd, 6), 'policy_ok': ok, 'policy_reason': why}, q
