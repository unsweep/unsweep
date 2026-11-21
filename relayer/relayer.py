"""UNSWEEP relayer M1.1 (off-chain). Politica de beta y envio seguro de la tx tipo 4.

Reglas fuera de la cadena (no hay oraculo on-chain):
  - limite de beta: valor rescatado <= UNSWEEP_BETA_CAP_USD (500 por defecto)
  - rentabilidad: comision_usd >= 3 * coste_gas_usd
  - la autorizacion 7702 exige chain_id concreto (nunca 0)
  - justo antes de enviar se comprueba que el nonce de la EOA sigue igual al de la autorizacion;
    si el atacante envio una tx desde la EOA, la autorizacion es invalida y NO se envia.
"""
import os
from dataclasses import dataclass

from eth_account import Account
from web3 import Web3

TESTNETS = {31337, 84532, 421614, 11155111}


class PolicyError(Exception):
    pass


class RaceAbort(Exception):
    """La EOA cambio de nonce entre la firma y el envio: autorizacion invalida."""


@dataclass
class Quote:
    rescued_usd: float  # valor total rescatado estimado (precios off-chain)
    fee_usd: float      # comision 15 % en especie + tarifa NFT, valorada off-chain
    gas_cost_usd: float # coste estimado de la tx tipo 4


def beta_cap_usd() -> float:
    return float(os.environ.get("UNSWEEP_BETA_CAP_USD", "500"))


def check_policy(q: Quote, cap_usd: float | None = None) -> None:
    cap = beta_cap_usd() if cap_usd is None else cap_usd
    if q.rescued_usd <= 0:
        raise PolicyError("nada que rescatar")
    if q.rescued_usd > cap:
        raise PolicyError(f"supera el limite de beta ({q.rescued_usd} > {cap} USD)")
    if q.fee_usd < 3 * q.gas_cost_usd:
        raise PolicyError(f"comision {q.fee_usd} < 3 x gas {q.gas_cost_usd}")


def sign_auth(victim_key, chain_id: int, impl: str, nonce: int):
    if not isinstance(chain_id, int) or chain_id == 0:
        raise PolicyError("chain_id 0 prohibido: la autorizacion debe ser de una sola cadena")
    return Account.sign_authorization(
        {"chainId": chain_id, "address": Web3.to_checksum_address(impl), "nonce": nonce}, victim_key
    )


def auth_nonce_still_valid(w3: Web3, victim: str, auth_nonce: int) -> bool:
    return w3.eth.get_transaction_count(Web3.to_checksum_address(victim), "pending") == auth_nonce


def send_rescue(w3: Web3, sponsor_key, victim: str, signed_auth, calldata: bytes, q: Quote,
                gas: int = 1_500_000, allow_mainnet: bool = False, cap_usd: float | None = None):
    chain_id = w3.eth.chain_id
    if chain_id not in TESTNETS and not allow_mainnet:
        raise PolicyError(f"chain {chain_id} no es testnet; mainnet desactivado en M1.1")
    if signed_auth.chain_id != chain_id or signed_auth.chain_id == 0:
        raise PolicyError("la autorizacion no es para esta cadena")
    check_policy(q, cap_usd)
    sponsor = Account.from_key(sponsor_key)
    tx = {
        "type": 4, "chainId": chain_id, "to": Web3.to_checksum_address(victim), "value": 0,
        "data": calldata, "gas": gas,
        "maxFeePerGas": w3.eth.gas_price * 2 + 1, "maxPriorityFeePerGas": 1,
        "nonce": w3.eth.get_transaction_count(sponsor.address, "pending"),
        "authorizationList": [signed_auth],
    }
    raw = sponsor.sign_transaction(tx).raw_transaction
    # comprobacion de carrera JUSTO antes de enviar
    if not auth_nonce_still_valid(w3, victim, signed_auth.nonce):
        raise RaceAbort("el nonce de la EOA cambio: autorizacion invalida, no se envia")
    h = w3.eth.send_raw_transaction(raw)
    return w3.eth.wait_for_transaction_receipt(h, timeout=60)
