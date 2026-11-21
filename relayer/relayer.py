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

try:
    from . import policy as P  # noqa
except ImportError:
    import policy as P  # noqa

TESTNETS = {31337, 84532, 421614, 11155111}
ACTIVE_MAINNETS = {8453}  # #81=B: solo Base; 1 (Ethereum) y 42161 (Arbitrum) siguen bloqueadas


PolicyError = P.PolicyError  # una sola clase para relayer y policy


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
                gas: int = 1_500_000, allow_mainnet: bool = False, cap_usd: float | None = None,
                track: "P.TrackRecord | None" = None, exception_ref: str = "", rpc_url: str = "",
                eth_usd: float | None = None):
    chain_id = w3.eth.chain_id
    if chain_id not in TESTNETS and chain_id not in ACTIVE_MAINNETS:
        raise PolicyError(f"chain {chain_id} no habilitada (mainnets activas: {sorted(ACTIVE_MAINNETS)})")
    if signed_auth.chain_id != chain_id or signed_auth.chain_id == 0:
        raise PolicyError("la autorizacion no es para esta cadena")
    if chain_id in P.MAINNETS:
        # M4: limites 10k/50k/sin limite + excepcion manual; Ethereum solo Flashbots Protect
        P.check_cap(chain_id, q.rescued_usd, track or P.TrackRecord(), exception_ref)
        P.check_ethereum_route(chain_id, rpc_url)
        P.fee_plan(chain_id, q.rescued_usd, q.gas_cost_usd)
    else:
        check_policy(q, cap_usd)
    sponsor = Account.from_key(sponsor_key)
    if chain_id in ACTIVE_MAINNETS:
        P.ops_guard(w3.eth.get_balance(sponsor.address))  # #84: tope 0.005 ETH, fail-closed
    tx = {
        "type": 4, "chainId": chain_id, "to": Web3.to_checksum_address(victim), "value": 0,
        "data": calldata, "gas": gas,
        "maxFeePerGas": w3.eth.gas_price * 2 + 1, "maxPriorityFeePerGas": 1,
        "nonce": w3.eth.get_transaction_count(sponsor.address, "pending"),
        "authorizationList": [signed_auth],
    }
    P.simulate(w3, {**tx, "from": sponsor.address})  # eth_call obligatoria
    raw = sponsor.sign_transaction(tx).raw_transaction
    # comprobacion de carrera JUSTO antes de enviar
    if not auth_nonce_still_valid(w3, victim, signed_auth.nonce):
        raise RaceAbort("el nonce de la EOA cambio: autorizacion invalida, no se envia")
    h = w3.eth.send_raw_transaction(raw)
    rc = w3.eth.wait_for_transaction_receipt(h, timeout=60)
    if rc["status"] == 0:
        wei = rc["gasUsed"] * rc.get("effectiveGasPrice", 0)
        P.record_gas_lost(chain_id, h.hex(), rc["gasUsed"], wei / 1e18 * (eth_usd or 0.0))
    return rc
