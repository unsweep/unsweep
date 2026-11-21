import pytest

import policy as P


def test_tiers():
    assert P.tier_bps(999.99) == 1500
    assert P.tier_bps(1_000) == 1000
    assert P.tier_bps(10_000) == 1000
    assert P.tier_bps(10_000.01) == 500
    with pytest.raises(P.PolicyError):
        P.tier_bps(0)


def test_ethereum_min_gas_x15():
    fp = P.fee_plan(1, 200, 10)  # tramo 30 vs gas 15 -> 30
    assert fp.fee_usd == 30 and fp.min_fee_usd == 15
    fp = P.fee_plan(1, 5_000, 400)  # tramo 500 vs gas 600 -> 600 (<=15 % = 750)
    assert fp.fee_usd == 600 and fp.max_fee_bps == 1000
    assert P.fee_plan(8453, 5_000, 400).min_fee_usd == 0  # solo Ethereum
    with pytest.raises(P.PolicyError):
        P.fee_plan(1, 100, 20)  # 30 > 15 USD de techo


def test_caps():
    """#927: tope automatico 100.000 USD, independiente del historial."""
    T = P.TrackRecord
    for t in (T(0), T(2), T(3), T(10), T(0, external_audit=True)):
        assert P.cap_usd(t) == 100_000


def test_exception_25k_does_not_block_10k(tmp_path, monkeypatch):
    """3b: una excepcion/config de 25.000 no impide aceptar 10.000."""
    h = tmp_path / "HUMANO.md"
    h.write_text("x\nUNSWEEP-EXCEPCION caso42 25_000 USD\n")
    monkeypatch.setenv("UNSWEEP_BETA_CAP_USD", "25000")
    for ref in ("", "caso42", "otro"):
        P.check_cap(8453, 10_000, P.TrackRecord(), ref, humano_md=h)


@pytest.mark.parametrize("ok", [0, 1, 3, 10])
def test_cap_100k_auto(tmp_path, ok):
    """#927: 100.000 aceptado; >100.000 rechazado, haya o no excepcion manual."""
    h = tmp_path / "HUMANO.md"
    h.write_text("UNSWEEP-EXCEPCION caso42 250_000 USD\n")
    P.check_cap(8453, 100_000, P.TrackRecord(ok))
    P.check_cap(8453, 20_000, P.TrackRecord(ok))
    for amt in (100_000.01, 250_000):
        for ref in ("", "caso42"):
            with pytest.raises(P.PolicyError, match="limite"):
                P.check_cap(8453, amt, P.TrackRecord(ok), ref, humano_md=h)


def test_testnet_no_cap():
    P.check_cap(84532, 10**9, P.TrackRecord())  # testnet: sin limite M4


def test_ethereum_route(monkeypatch):
    P.check_ethereum_route(8453, "")
    with pytest.raises(P.PolicyError):
        P.check_ethereum_route(1, "https://eth.example")
    monkeypatch.delenv("UNSWEEP_FLASHBOTS_TYPE4_VERIFIED", raising=False)
    with pytest.raises(P.PolicyError):
        P.check_ethereum_route(1, "https://rpc.flashbots.net/fast")
    monkeypatch.setenv("UNSWEEP_FLASHBOTS_TYPE4_VERIFIED", "1")
    P.check_ethereum_route(1, "https://rpc.flashbots.net/fast")


def test_simulate_aborts():
    class E:
        def call(self, *a):
            raise ValueError("execution reverted")

    class W:
        eth = E()

    with pytest.raises(P.PolicyError):
        P.simulate(W(), {"to": "0x0", "data": b""})


def test_gas_lost_alert_once(tmp_path, monkeypatch):
    monkeypatch.setattr(P, "DATA_DIR", tmp_path)
    h = tmp_path / "HUMANO.md"
    monkeypatch.setattr(P, "HUMANO_MD", h)
    assert P.record_gas_lost(8453, "0x1", 21000, 3.0) == 3.0
    assert not h.exists()
    assert P.record_gas_lost(8453, "0x2", 21000, 2.5) == 5.5
    assert h.read_text().count("Gas perdido") == 1
    P.record_gas_lost(8453, "0x3", 21000, 1.0)
    assert h.read_text().count("Gas perdido") == 1
