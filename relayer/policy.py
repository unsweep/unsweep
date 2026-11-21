"""Politica M4 del relayer UNSWEEP (orden 'AJUSTES PREVIOS A MAINNET', nota #691).

- Tramos: 15 % (<1.000 USD), 10 % (1.000-10.000), 5 % (>10.000).
- Ethereum (chain 1): comision = max(tramo, gas estimado x 1.5).
- Limite por rescate (#827.2/3b): 10.000 USD; 50.000 USD solo con >=3 rescates reales.
  Sin excepciones por encima del limite.
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
from datetime import datetime, timezone
from pathlib import Path

MAX_FEE_BPS = 1500  # igual que el techo inmutable del contrato
ETH_MAINNET = 1
MAINNETS = {1, 8453, 42161}
CAP_INITIAL_USD = 100_000.0  # #927: tope automatico por rescate
FIXED_CAP_USD = 10_000.0  # umbral de controles extra (#927) y tope de tokens fuera de HIGH_VALUE
CAP_RAISED_USD = 100_000.0  # #927: sin tramos por historial; el tope automatico es 100k
HIGH_VALUE_USD = 10_000.0
MAX_PRICE_AGE_S = 3600  # #927(a): precio Chainlink < 1 h por encima de 10k
HIGH_VALUE_SYMBOLS = frozenset({"USDC", "USDT", "DAI", "EURC", "WETH", "wstETH", "weETH", "cbETH", "cbBTC"})
REPO_DIR = Path(__file__).resolve().parent.parent
CASOS_MD = Path(os.environ.get("UNSWEEP_CASOS_MD", REPO_DIR / "docs" / "CASOS.md"))
RAISE_AFTER_OK = 3
UNCAP_AFTER_OK = 10
GAS_LOST_ALERT_USD = 5.0
OPS_CAP_WEI = 5 * 10**15   # #84: tope 0.005 ETH en la wallet OPS
OPS_LOW_WEI = 15 * 10**14  # 30 % del tope: aviso en HUMANO.md
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


def cap_usd(tr: TrackRecord) -> float:
    """#927: tope automatico 100.000 USD por rescate, independiente del historial.
    Por encima de 10.000 USD se exigen los controles de check_high_value/check_split."""
    return CAP_INITIAL_USD


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
    """#827.2/3b: limite duro. Ninguna excepcion manual ni configuracion lo supera;
    una excepcion (p.ej. 25.000) tampoco reduce el limite: <=10.000 siempre se acepta."""
    if chain_id not in MAINNETS:
        return
    cap = cap_usd(tr)
    if rescued_usd <= cap:
        return
    raise PolicyError(f"supera el limite por rescate ({rescued_usd} > {cap} USD; {tr.mainnet_ok} rescates reales)")


def needs_extra_checks(rescued_usd: float) -> bool:
    return rescued_usd > HIGH_VALUE_USD


def check_high_value(rescued_usd: float, items: list):
    """#927 (a)+(b). items: [{'symbol','value_usd','price_age_s'}]. Solo aplica si rescued_usd > 10.000.
    (a) toda valoracion debe venir de un feed Chainlink con antiguedad < 1 h, o se rechaza.
    (b) los tokens fuera de HIGH_VALUE_SYMBOLS suman como maximo 10.000 USD."""
    if not needs_extra_checks(rescued_usd):
        return
    other = 0.0
    for it in items:
        age = it.get("price_age_s")
        if age is None or not (0 <= int(age) < MAX_PRICE_AGE_S):
            raise PolicyError(f"precio de {it.get('symbol','?')} con mas de 1 h (>{MAX_PRICE_AGE_S}s) en rescate >10.000 USD")
        if it.get("symbol") not in HIGH_VALUE_SYMBOLS:
            other += float(it.get("value_usd", 0))
    if other > HIGH_VALUE_USD:
        raise PolicyError(f"tokens fuera de la lista de alto valor superan 10.000 USD ({other:.2f})")


def check_split(expected: list, simulated: dict):
    """#927 (c): reparto exacto. expected: lines de la cotizacion {'token','amount','fee','net'}.
    simulated: {token_lower: {'safe': int, 'fee': int}} obtenido de la resimulacion justo antes de enviar."""
    sim = {str(k).lower(): v for k, v in (simulated or {}).items()}
    if len(sim) != len(expected):
        raise PolicyError("resimulacion: numero de tokens distinto al cotizado")
    for l in expected:
        got = sim.get(str(l["token"]).lower())
        if got is None:
            raise PolicyError(f"resimulacion: falta {l['token']}")
        if int(got.get("safe", -1)) != int(l["net"]) or int(got.get("fee", -1)) != int(l["fee"]):
            raise PolicyError(f"resimulacion: reparto SAFE/fee distinto al cotizado en {l['token']}")


def breakdown(lines: list, rescued_usd: float, fee_usd: float) -> list:
    """#927 (d): desglose que se muestra antes de firmar."""
    out = []
    for l in lines:
        dec = int(l.get("decimals", 18))
        out.append({"symbol": l.get("symbol", ""), "to_safe": int(l["net"]) / 10**dec, "fee": int(l["fee"]) / 10**dec})
    return [{"rescued_usd": round(rescued_usd, 2), "fee_usd": round(fee_usd, 2), "to_safe_usd": round(rescued_usd - fee_usd, 2)}] + out


def record_case(chain_id: int, rescued_usd: float, fee_usd: float, result: str, txh: str = "", path: Path | None = None):
    """#927 (e): registro de cada rescate >10.000 USD en docs/CASOS.md (sin direcciones de usuario)."""
    p = path or CASOS_MD
    p.parent.mkdir(parents=True, exist_ok=True)
    new = not p.exists()
    with p.open("a", encoding="utf-8") as f:
        if new:
            f.write("# Casos de rescate > 10.000 USD\n\n| fecha UTC | chain | rescatado USD | fee USD | resultado | tx |\n|---|---|---|---|---|---|\n")
        f.write(f"| {datetime.now(timezone.utc).isoformat(timespec='seconds')} | {chain_id} | {rescued_usd:.2f} | {fee_usd:.2f} | {result} | {txh} |\n")


def ops_status(balance_wei) -> str:
    if balance_wei is None or int(balance_wei) < 0:
        return "unknown"
    b = int(balance_wei)
    return "over" if b > OPS_CAP_WEI else ("low" if b < OPS_LOW_WEI else "ok")


def ops_guard(balance_wei, humano_md: Path | None = None) -> str:
    """Fail-closed: saldo ilegible o por encima del tope => no se patrocina. Bajo 30 % => aviso unico."""
    st = ops_status(balance_wei)
    if st in ("unknown", "over"):
        raise PolicyError(f"wallet OPS fuera de politica ({st}); tope {OPS_CAP_WEI / 1e18} ETH")
    if st == "low":
        flag = DATA_DIR / "ops_low_alerted"
        try:
            if not flag.exists():
                with (humano_md or HUMANO_MD).open("a", encoding="utf-8") as h:
                    h.write(f"\n- [UNSWEEP] Saldo OPS bajo: {int(balance_wei) / 1e18:.6f} ETH (< {OPS_LOW_WEI / 1e18} ETH). "
                            f"Recargar hasta como maximo {OPS_CAP_WEI / 1e18} ETH.\n")
                flag.write_text(str(int(time.time())))
        except OSError:
            pass  # contenedor read-only: el aviso lo publica /api/health (ops=low)
    return st


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


# --- #731: eleccion del token que lleva el minFee (solo Ethereum) -------------------------
# Orden: (a) USDC, WETH, DAI, USDT con saldo suficiente (por DIRECCION oficial, nunca por simbolo);
# (b) si no hay, el de mayor valor marcado explicitamente fee_on_transfer=False;
# (c) nunca un token con comision al transferir (o sin verificar: se trata como posible FOT).
# Si ninguno cubre el minFee -> NotViableOnEthereum (se sugiere Base o Arbitrum).
# Direcciones canonicas de Ethereum mainnet: VERIFICAR en etherscan/emisor antes de activar mainnet.
PREFERRED_MIN_FEE = {
    ETH_MAINNET: [
        ("USDC", "0xa0b86991c6218b36c1d19d4a2e9eb0ce3606eb48"),
        ("WETH", "0xc02aaa39b223fe8d0a0e5c4f27ead9083c756cc2"),
        ("DAI", "0x6b175474e89094c44da98b954eedeac495271d0f"),
        ("USDT", "0xdac17f958d2ee523a2206206994597c13d831ec7"),
    ],
}
NOT_VIABLE_ETH = "no viable en Ethereum: ningun token admisible cubre el minimo de gas; usa Base o Arbitrum"


class NotViableOnEthereum(PolicyError):
    pass


def pick_min_fee_token(chain_id: int, tokens: list, min_fee_usd: float, bps: int):
    """tokens: [{'address', 'value_usd', 'fee_on_transfer'(opcional)}].
    Devuelve (indice, regla 'a'|'b') del token que lleva el minFee.
    Saldo suficiente = su valor cubre lo que falta tras el tramo del resto de tokens."""
    total = sum(float(t["value_usd"]) for t in tokens)

    def covers(k):
        v = float(tokens[k]["value_usd"])
        return v >= min_fee_usd - (total - v) * bps / 10_000

    pref = [a for _s, a in PREFERRED_MIN_FEE.get(chain_id, [])]
    by_addr = {str(t["address"]).lower(): k for k, t in enumerate(tokens)}
    for addr in pref:  # (a)
        k = by_addr.get(addr)
        if k is not None and tokens[k].get("fee_on_transfer") is not True and covers(k):
            return k, "a"
    ok = [k for k, t in enumerate(tokens)  # (b); (c) excluye FOT y no verificados
          if t.get("fee_on_transfer") is False and str(t["address"]).lower() not in pref and covers(k)]
    if ok:
        return max(ok, key=lambda k: float(tokens[k]["value_usd"])), "b"
    raise NotViableOnEthereum(NOT_VIABLE_ETH)
