"""#1803 FASE 2c: regresion del copy sobre la clave privada.

Comprueba que las frases que pedian la clave sin explicar no vuelven y que
home, guias, llms.txt y README explican: (a) solo la clave de la wallet ya
comprometida, (b) nunca la seed ni la wallet segura, (c) firma local con
enlace al codigo de app.js, (d) como comprobarlo (DevTools/Network, contrato
en Basescan, UNSWEEP nunca escribe primero).
"""
import pathlib
import re

import pytest

ROOT = pathlib.Path(__file__).resolve().parent.parent
WEB = ROOT / "web"
CONTRACT = "0x38bcF425bC4d13624734e09376F2fafc799fA8c8"

OLD = [
    "never paste a private key",
    "ask for your seed phrase or private key",
    "never asks for a seed phrase or private key",
    "never ask for your private key",
    "Local signing:</strong> the rescue is signed",
    "Never share a seed phrase or private key",
    "The rescue transaction is signed 100% locally",
]


def _files():
    fs = [WEB / "index.html", WEB / "llms.txt", ROOT / "README.md"]
    fs += sorted(WEB.glob("guides/*.html")) + sorted(WEB.glob("guides/*/index.html"))
    return [f for f in fs if f.exists()]


def _keyfiles():
    """Ficheros que hablan de la clave privada (los que deben explicar a-d)."""
    return [f for f in _files() if re.search(r"private key", f.read_text(), re.I)]


@pytest.mark.parametrize("f", _files(), ids=lambda p: str(p.relative_to(ROOT)))
def test_sin_frases_antiguas(f):
    t = f.read_text().lower()
    for p in OLD:
        assert p.lower() not in t, f"{f}: reaparece '{p}'"


@pytest.mark.parametrize("f", _keyfiles(), ids=lambda p: str(p.relative_to(ROOT)))
def test_cuatro_elementos(f):
    t = f.read_text()
    low = t.lower()
    assert re.search(r"already[- ]compromised", low), f"{f}: falta (a) wallet ya comprometida"
    assert "seed phrase" in low and "safe wallet" in low, f"{f}: falta (b) seed / wallet segura"
    assert "browser" in low and "app.js" in t, f"{f}: falta (c) firma local + enlace app.js"
    assert "devtools" in low, f"{f}: falta (d) DevTools/Network"
    assert re.search(r"never (writes to you|dms? you|dms?) first", low), f"{f}: falta (d) anti-DM"


def test_home_step3_y_contrato():
    s = (WEB / "index.html").read_text()
    assert 'id="verifyLinks"' in s and 'id="devtoolsNote"' in s
    assert "github.com/unsweep/unsweep/blob/main/web/assets/app.js" in s
    assert f"basescan.org/address/{CONTRACT}#code" in s
    assert "Why a key:" in s
