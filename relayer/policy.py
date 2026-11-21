"""Politica M4 del relayer UNSWEEP (orden 'AJUSTES PREVIOS A MAINNET', nota #691).

- Tramos: 15 % (<1.000 USD), 10 % (1.000-10.000), 5 % (>10.000).
- Ethereum (chain 1): comision = max(tramo, gas estimado x 1.5).
- Limite por rescate: 10.000 USD hasta 3 rescates mainnet exitosos; despues 50.000;
  sin limite tras 10 rescates sin incidentes o auditoria externa.
- Excepcion manual: linea escrita por el HUMANO en HUMANO.md:
    UNSWEEP-EXCEPCION <ref> <max_usd> USD
- Simulacion eth_call obligatoria antes de enviar.
- Ethereum solo por Flashbots Protect y solo si se ha verificado que acepta tx tipo 4.
- No se exige saldo en la wallet segura (el relayer no lo comprueba).
- Registro INTERNO del gas perdido por reversion; si el total supera 5 USD, aviso en
  HUMANO.md (una vez). Nunca se cobra ese gas a nadie.
"""
import json
import os
import re
import time
from dataclasses import dataclass
from pathlib import Path

MAX_FEE_BPS = 1500  # igual que el techo inmutable del contrato
ETH_MAINNET = 1
MAINNETS = {1, 8453, 42161}
CAP_INITIAL_USD = 10_000.0
CAP_RAISED_USD = 50_000.0
RAISE_AFTER_OK = 3
UNCAP_AFTER_OK = 10
GAS_LOST_ALERT_USD = 5.0
ETH_GAS_MULT = 1.5

DATA_DIR = Path(os.environ.get("UNSWEEP_DATA_DIR", Path(__file__).parent / "data"))
HUMANO_MD = Path(os.environ.get("UNSWEEP_HUMANO_MD", "/opt/aire/HUMANO.md"))


class PolicyError(Exception):
    pass


def tier_bps(rescued_usd: float) -> int:
    if rescued_usd <= 0:
        raise PolicyError("nada que rescatar")
    if rescued_usd < 1_000:
        return 1500
    if rescued_usd <= 10_000:
        return 1000
    return 500


@dataclass
class FeePlan:
    max_fee_bps: int      # va firmado en el EIP-712 (<= 1500)
    fee_usd: float        # comision esperada en USD
    min_fee_usd: float    # 0 fuera de Ethereum; en Ethereum = gas x 1.5 (va firmado como minFees)


def fee_plan(chain_id: int, rescued_usd: float, gas_cost_usd: float) -> FeePlan:
    bps = tier_bps(rescued_usd)
    tier_usd = rescued_usd * bps / 10_000
    min_usd = gas_cost_usd * ETH_GAS_MULT if chain_id == ETH_MAINNET else 0.0
    fee = max(tier_usd, min_usd)
    # el contrato nunca cobra mas del 15 %: si el minimo lo supera, no es rentable -> rechazar
    if fee > rescued_usd * MAX_FEE_BPS / 10_000:
        raise PolicyError(f"minimo de gas {min_usd:.2f} USD supera el techo del 15 %")
    return FeePlan(max_fee_bps=bps, fee_usd=fee, min_fee_usd=min_usd)


@dataclass
class TrackRecord:
    mainnet_ok: int = 0
    incidents: int = 0
    external_audit: bool = False


def cap_usd(tr: TrackRecord):
    """None = sin limite."""
    if tr.external_audit or (tr.mainnet_ok >= UNCAP_AFTER_OK and tr.incidents == 0):
        return None
    return CAP_RAISED_USD if tr.mainnet_ok >= RAISE_AFTER_OK else CAP_INITIAL_USD


_EXC = re.compile(r"^\s*UNSWEEP-EXCEPCION\s+(\S+)\s+([0-9][0-9_.,]*)\s*USD\b", re.M)


def manual_exception_usd(ref: str, humano_md: Path | None = None):
    p = humano_md or HUMANO_MD
    try:
        txt = p.read_text(encoding="utf-8")
    except OSError:
        return None
    best = None
    for m in _EXC.finditer(txt):
        if m.group(1) == ref:
            v = float(m.group(2).replace("_", "").replace(",", ""))
            best = v if best is None else max(best, v)
    return best


def check_cap(chain_id: int, rescued_usd: float, tr: TrackRecord, ref: str = "", humano_md: Path | None = None):
    if chain_id not in MAINNETS:
        return
    cap = cap_usd(tr)
    if cap is None or rescued_usd <= cap:
        return
    exc = manual_exception_usd(ref, humano_md) if ref else None
    if exc is not None and rescued_usd <= exc:
        return
    raise PolicyError(f"supera el limite por rescate ({rescued_usd} > {cap} USD) sin excepcion manual")


def check_ethereum_route(chain_id: int, rpc_url: str):
    if chain_id != ETH_MAINNET:
        return
    if "rpc.flashbots.net" not in (rpc_url or ""):
        raise PolicyError("Ethereum solo por Flashbots Protect")
    if os.environ.get("UNSWEEP_FLASHBOTS_TYPE4_VERIFIED") != "1":
        raise PolicyError("no verificado que Flashbots Protect acepte tx tipo 4")


def simulate(w3, tx: dict):
    """eth_call obligatoria con la misma tx (incluida authorizationList). Cualquier fallo aborta."""
    call = {k: tx[k] for k in ("from", "to", "data", "value", "gas", "authorizationList") if k in tx}
    try:
        w3.eth.call(call, "pending")
    except Exception as e:  # noqa: BLE001
        raise PolicyError(f"simulacion eth_call fallida: {e}") from e


def _ledger() -> Path:
    return DATA_DIR / "gas_lost.jsonl"


def gas_lost_total() -> float:
    p = _ledger()
    if not p.exists():
        return 0.0
    return sum(json.loads(l)["cost_usd"] for l in p.read_text().splitlines() if l.strip())


def record_gas_lost(chain_id: int, tx_hash: str, gas_used: int, cost_usd: float) -> float:
    """Registro interno; devuelve el total. Avisa en HUMANO.md una sola vez al superar 5 USD."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    before = gas_lost_total()
    with _ledger().open("a") as f:
        f.write(json.dumps({"ts": int(time.time()), "chain_id": chain_id, "tx": tx_hash,
                            "gas_used": gas_used, "cost_usd": round(cost_usd, 6)}) + "\n")
    total = before + cost_usd
    flag = DATA_DIR / "gas_lost_alerted"
    if total > GAS_LOST_ALERT_USD and not flag.exists():
        with HUMANO_MD.open("a", encoding="utf-8") as h:
            h.write(f"\n- [UNSWEEP] Gas perdido por reversiones: {total:.2f} USD (> {GAS_LOST_ALERT_USD} USD). "
                    "Revisar relayer/data/gas_lost.jsonl. No se cobra nada a nadie.\n")
        flag.write_text(str(int(time.time())))
    return total
