"""#927: controles automaticos por encima de 10.000 USD (tope automatico 100.000)."""
import types
import pytest
import policy as P
import relayer as R

T1 = "0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913"
T2 = "0x4200000000000000000000000000000000000006"
SAFE = "0x000000000000000000000000000000000000dEaD"
FEE = "0x000000000000000000000000000000000000bEEF"


def _it(sym, usd, age=60, hb=86400, px=1.0, feeds=None):
    f = feeds if feeds is not None else [{"age_s": age, "heartbeat_s": hb}]
    return {"symbol": sym, "value_usd": usd, "price_usd": px, "price_feeds": f}


def test_below_10k_no_extra_checks():
    assert not P.needs_extra_checks(10_000)
    P.check_high_value(10_000, [_it("FOO", 10_000, age=None)])


def test_allowlisted_tokens_up_to_100k():
    assert P.needs_extra_checks(10_000.01)
    P.check_high_value(100_000, [_it(s, 100_000 / 9) for s in sorted(P.HIGH_VALUE_SYMBOLS)])


def test_non_allowlisted_capped_at_10k():
    P.check_high_value(60_000, [_it("USDC", 50_000), _it("AERO", 10_000)])
    with pytest.raises(P.PolicyError, match="10.000"):
        P.check_high_value(60_000, [_it("USDC", 49_999), _it("AERO", 6_000), _it("DEGEN", 5_000)])


# --- #98: antiguedad maxima = heartbeat de cada feed (tambien compuestos) ---
@pytest.mark.parametrize("age,hb", [(86401, 86400), (1201, 1200), (None, 86400), (-1, 86400), (10, None), (10, 0)])
def test_98_stale_vs_heartbeat_rejected(age, hb):
    with pytest.raises(P.PolicyError, match="desactualizado"):
        P.check_high_value(20_000, [_it("USDC", 20_000, age=age, hb=hb)])


def test_98_fresh_within_heartbeat_ok():
    P.check_high_value(20_000, [_it("USDC", 20_000, age=86400, hb=86400)])  # 86400 s: antes (<1 h) se rechazaba
    P.check_high_value(20_000, [_it("WETH", 20_000, age=1200, hb=1200, px=3000)])


def test_98_no_feeds_rejected():
    for f in ([], None):
        it = _it("USDC", 20_000); it["price_feeds"] = f
        with pytest.raises(P.PolicyError, match="sin feed"):
            P.check_high_value(20_000, [it])


def test_98_composite_each_feed_checked():
    ok = [{"age_s": 80000, "heartbeat_s": 86400}, {"age_s": 1000, "heartbeat_s": 1200}]
    P.check_high_value(20_000, [_it("wstETH", 20_000, px=4000, feeds=ok)])
    for bad in ([{"age_s": 86401, "heartbeat_s": 86400}, {"age_s": 10, "heartbeat_s": 1200}],
                [{"age_s": 10, "heartbeat_s": 86400}, {"age_s": 1201, "heartbeat_s": 1200}]):
        with pytest.raises(P.PolicyError, match="desactualizado"):
            P.check_high_value(20_000, [_it("wstETH", 20_000, px=4000, feeds=bad)])


def test_98_oracle_composite_feeds_use_each_heartbeat(monkeypatch):
    import oracle as O
    from web3 import Web3
    X = "0x0000000000000000000000000000000000000011"; E = "0x0000000000000000000000000000000000000022"
    cfg = {"eth_usd_feed": {"address": E, "heartbeat": 1200, "quote": "USD"},
           "tokens": [{"address": T2, "symbol": "wstETH", "feed": {"address": X, "heartbeat": 86400, "quote": "ETH"}}]}
    monkeypatch.setattr(O, "token_price_usd", lambda w3, c, t: 4000.0)
    O.clear_cache()
    O._cache[Web3.to_checksum_address(X)] = {"at": 0, "px": 1.2, "upd": 1000}
    O._cache[Web3.to_checksum_address(E)] = {"at": 0, "px": 3000.0, "upd": 5000}
    out = O.token_price_feeds(None, cfg, cfg["tokens"][0], now=6000)
    assert [(x["age_s"], x["heartbeat_s"]) for x in out] == [(5000, 86400), (1000, 1200)]
    O.clear_cache()
    with pytest.raises(O.OracleError):
        O.token_price_feeds(None, cfg, cfg["tokens"][0], now=6000)
    assert O.eur_usd(None, cfg) is None  # sin feed EUR/USD configurado


# --- #98: stablecoins por encima de 10k (compatible con #927.2: siguen permitidas si estan en banda) ---
@pytest.mark.parametrize("sym", ["USDC", "USDT", "DAI", "GHO", "sUSDe"])
def test_98_stable_band(sym):
    for px in (0.98, 1.0, 1.02):
        P.check_high_value(10_001, [_it(sym, 10_001 if sym in P.HIGH_VALUE_SYMBOLS else 5_000, px=px)])
    for px in (0.979, 1.021, None):
        with pytest.raises(P.PolicyError, match="fuera de"):
            P.check_high_value(20_000, [_it(sym, 20_000, px=px)])


def test_98_stable_band_only_above_10k():
    P.check_high_value(10_000, [_it("USDT", 10_000, px=0.5)])


def test_98_usdc_usdt_dai_still_allowed_above_10k_927_2():
    P.check_high_value(90_000, [_it("USDC", 30_000), _it("USDT", 30_000), _it("DAI", 30_000)])


def test_98_eurc_vs_eur_usd():
    P.check_high_value(20_000, [_it("EURC", 20_000, px=1.10)])  # sin feed EUR/USD: no aplica
    P.check_high_value(20_000, [_it("EURC", 20_000, px=1.10)], eur_usd=1.08)
    with pytest.raises(P.PolicyError, match="EURC"):
        P.check_high_value(20_000, [_it("EURC", 20_000, px=1.11)], eur_usd=1.08)


LINES = [{"token": T1, "amount": "1000", "fee": "50", "net": "950", "symbol": "USDC", "decimals": 6},
         {"token": T2, "amount": "200", "fee": "10", "net": "190", "symbol": "WETH", "decimals": 18}]


def test_split_exact_ok_and_mismatch_rejected():
    P.check_split(LINES, {T1.lower(): {"safe": 950, "fee": 50}, T2: {"safe": 190, "fee": 10}})
    for bad in ({T1: {"safe": 949, "fee": 51}, T2: {"safe": 190, "fee": 10}},
                {T1: {"safe": 950, "fee": 50}},
                {T1: {"safe": 950, "fee": 50}, T2: {"safe": 190, "fee": 10}, SAFE: {"safe": 1, "fee": 0}}):
        with pytest.raises(P.PolicyError, match="resimulacion"):
            P.check_split(LINES, bad)


def _w3(results):
    return types.SimpleNamespace(provider=types.SimpleNamespace(
        make_request=lambda m, p: {"result": [{"calls": results}]}))


def _ok(v):
    return {"status": "0x1", "returnData": hex(v)}


TX = {"to": SAFE, "data": b"\x00", "gas": 1_500_000, "authorizationList": [object()]}


def test_measure_split_deltas_and_check(monkeypatch):
    monkeypatch.setattr(R, "_auth_json", lambda a: {})
    out = [_ok(5), _ok(7), _ok(0), _ok(3)] + [{"status": "0x1", "returnData": "0x"}] + [_ok(955), _ok(57), _ok(190), _ok(13)]
    m = R.measure_split(_w3(out), FEE, TX, [T1, T2], SAFE, FEE)
    assert m == {T1.lower(): {"safe": 950, "fee": 50}, T2.lower(): {"safe": 190, "fee": 10}}
    P.check_split(LINES, m)


def test_measure_split_fail_closed(monkeypatch):
    monkeypatch.setattr(R, "_auth_json", lambda a: {})
    rev = [_ok(0), _ok(0), {"status": "0x0", "returnData": "0x"}, _ok(0), _ok(0)]
    with pytest.raises(P.PolicyError):
        R.measure_split(_w3(rev), FEE, TX, [T1], SAFE, FEE)
    def boom(m, p):
        raise ValueError("method not found")
    w3 = types.SimpleNamespace(provider=types.SimpleNamespace(make_request=boom))
    with pytest.raises(P.PolicyError, match="no disponible"):
        R.measure_split(w3, FEE, TX, [T1], SAFE, FEE)


def test_breakdown_shown():
    b = P.breakdown(LINES, 20_000, 1_000)
    assert b[0] == {"rescued_usd": 20_000, "fee_usd": 1_000, "to_safe_usd": 19_000}
    assert b[1] == {"symbol": "USDC", "to_safe": 950 / 1e6, "fee": 50 / 1e6}


def test_record_case(tmp_path):
    p = tmp_path / "docs" / "CASOS.md"
    P.record_case(8453, 20_000, 1_000, "ok", "0xabc", path=p)
    P.record_case(8453, 30_000, 1_500, "rechazado", path=p)
    t = p.read_text()
    assert t.startswith("# Casos de rescate > 10.000 USD")
    assert "| 8453 | 20000.00 | 1000.00 | ok | 0xabc |" in t and "rechazado" in t


def test_casos_md_versioned():
    from pathlib import Path
    assert (Path(__file__).resolve().parent.parent / "docs" / "CASOS.md").is_file()
