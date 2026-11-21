"""EIP-712 de UNSWEEP: unica fuente en Python del typehash y del digest de Rescue.

Debe coincidir byte a byte con UnsweepDelegate.rescueDigest (commit ca62697). Ojo: el contrato
hashea los arrays con keccak256(abi.encode(array)) (incluye offset y longitud), no con el
encoding estandar de arrays de EIP-712. test_typehash_parity.py compara Solidity, Python y JS.
"""
from eth_abi import encode
from eth_utils import keccak, to_checksum_address

RESCUE_TYPE = ("Rescue(address safe,bytes32 callsHash,bytes32 tokensHash,bytes32 nftsHash,"
               "uint16 maxFeeBps,bytes32 minFeesHash,uint256 nonce,uint256 deadline)")
DOMAIN_TYPE = "EIP712Domain(string name,string version,uint256 chainId,address verifyingContract)"
RESCUE_TYPEHASH = keccak(text=RESCUE_TYPE)
DOMAIN_TYPEHASH = keccak(text=DOMAIN_TYPE)
NAME, VERSION = "Unsweep", "1"
MAX_FEE_BPS = 1500


def domain_separator(chain_id: int, verifying_contract: str) -> bytes:
    return keccak(encode(["bytes32", "bytes32", "bytes32", "uint256", "address"],
                         [DOMAIN_TYPEHASH, keccak(text=NAME), keccak(text=VERSION), int(chain_id),
                          to_checksum_address(verifying_contract)]))


def calls_hash(calls) -> bytes:
    return keccak(encode(["(address,uint256,bytes)[]"],
                         [[(to_checksum_address(t), int(v), bytes(d)) for t, v, d in calls]]))


def tokens_hash(tokens) -> bytes:
    return keccak(encode(["address[]"], [[to_checksum_address(t) for t in tokens]]))


def nfts_hash(nfts) -> bytes:
    return keccak(encode(["(address,uint256)[]"], [[(to_checksum_address(t), int(i)) for t, i in nfts]]))


def min_fees_hash(min_fees) -> bytes:
    return keccak(encode(["uint256[]"], [[int(x) for x in min_fees]]))


def rescue_tuple(safe, calls, tokens, nfts, max_fee_bps, min_fees, nonce, deadline):
    """Tupla en el orden del struct Rescue del contrato (para encode_abi('rescue', ...))."""
    if not 0 < int(max_fee_bps) <= MAX_FEE_BPS:
        raise ValueError("maxFeeBps fuera de (0, 1500]")
    if min_fees and len(min_fees) != len(tokens):
        raise ValueError("minFees debe estar vacio o tener la misma longitud que tokens")
    return (to_checksum_address(safe),
            [(to_checksum_address(t), int(v), bytes(d)) for t, v, d in calls],
            [to_checksum_address(t) for t in tokens],
            [(to_checksum_address(t), int(i)) for t, i in nfts],
            int(max_fee_bps), [int(x) for x in min_fees], int(nonce), int(deadline))


def struct_hash(r) -> bytes:
    safe, calls, tokens, nfts, max_fee_bps, min_fees, nonce, deadline = r
    return keccak(encode(
        ["bytes32", "address", "bytes32", "bytes32", "bytes32", "uint16", "bytes32", "uint256", "uint256"],
        [RESCUE_TYPEHASH, to_checksum_address(safe), calls_hash(calls), tokens_hash(tokens), nfts_hash(nfts),
         int(max_fee_bps), min_fees_hash(min_fees), int(nonce), int(deadline)]))


def rescue_digest(r, chain_id: int, verifying_contract: str) -> bytes:
    return keccak(b"\x19\x01" + domain_separator(chain_id, verifying_contract) + struct_hash(r))
