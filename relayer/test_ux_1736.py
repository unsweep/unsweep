"""ORDEN #1736: titulo/aviso de Step 1, details manual en Step 2 y regla de autoinclusion (sin checkbox)."""
import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
INDEX = (ROOT / "web" / "index.html").read_text()
APPJS = (ROOT / "web" / "assets" / "app.js").read_text()
CSS = (ROOT / "web" / "assets" / "style.css").read_text()
NODE = shutil.which("node")
A = "0x" + "11" * 20
B = "0x" + "22" * 20
C = "0x" + "33" * 20
D = "0x" + "44" * 20


def _parse(text):
    body = APPJS[APPJS.index("// @@manual-begin"):APPJS.index("// @@manual-end")]
    prog = body + "\nconst norm = (a) => a.toLowerCase();\nprocess.stdout.write(JSON.stringify(parseManualInput(%s, norm)));" % json.dumps(text)
    r = subprocess.run([NODE, "-e", prog], capture_output=True, text=True, timeout=20, check=True)
    return json.loads(r.stdout)


needs_node = pytest.mark.skipif(NODE is None, reason="node no disponible")


@needs_node
@pytest.mark.parametrize("txt", ["", "   ", "\n , ;\n"])
def test_vacio_no_incluye_nada(txt):
    assert _parse(txt) == {"list": [], "error": None}


@needs_node
@pytest.mark.parametrize("txt,n", [(A, 1), (A + "\n" + B, 2), (A + ", " + B + "; " + C, 3)])
def test_una_a_tres_validas_se_incluyen(txt, n):
    r = _parse(txt)
    assert r["error"] is None and len(r["list"]) == n
    assert r["list"] == [x.lower() for x in re.split(r"[\s,;]+", txt) if x]


@needs_node
def test_mas_de_tres_es_error_y_no_incluye():
    r = _parse("\n".join([A, B, C, D]))
    assert r["list"] == [] and "At most 3" in r["error"]


@needs_node
@pytest.mark.parametrize("txt", ["0x123", A + "\nhello", "0x" + "zz" * 20, A + "0", A + "\n" + A])
def test_invalida_o_duplicada_es_error_y_no_incluye(txt):
    r = _parse(txt)
    assert r["list"] == [] and r["error"] and "Nothing was simulated" in r["error"]


def test_error_corta_la_simulacion_antes_de_la_api():
    i_err = APPJS.index("if (mp.error) { st.manual = []; return show($('quoteOut'), mp.error, 'err'); }")
    assert i_err < APPJS.index("api('quote_manual'") and i_err < APPJS.index("api('quote', {")
    assert "if (!b || b.hidden) return { list: [], error: null }" in APPJS
    assert "listedValueUsd(s) > 0" in APPJS


def test_sin_rastro_del_checkbox():
    for s in (INDEX, APPJS, CSS):
        assert "manualCb" not in s and "Include these unverified contracts" not in s


def test_step1_titulo_y_aviso_pequeno_debajo():
    assert "<strong>Additional tokens detected (optional)</strong>" in INDEX
    assert "Additional tokens detected - optional" not in INDEX
    assert INDEX.index('id="extrasList"') < INDEX.index('id="extrasWarn"')
    assert '<p class="extrasNote" id="extrasWarn">Unverified tokens, no guarantee, may include scam tokens</p>' in INDEX
    assert re.search(r"\.extrasNote\{[^}]*font-size:\.78rem", CSS)
    assert "cb.checked = false" in APPJS


def test_step2_recuadro_solo_destino_y_simulate_y_details_aparte():
    body = INDEX[INDEX.index('id="step2Body"'):]
    form = body[body.index('<div class="form">'):body.index('<button id="btnQuote"')]
    assert 'id="safe"' in form and "textarea" not in form and "manual" not in form
    i_det = INDEX.index('<details id="manualBox" class="manual" hidden>')
    assert INDEX.index('id="btnQuote"') < i_det < INDEX.index('id="quoteOut"')
    assert "<summary>Add token contracts manually (optional)</summary>" in INDEX[i_det:]


def test_textarea_tema_oscuro():
    rule = re.search(r"#manualContracts\{([^}]*)\}", CSS).group(1)
    assert "background:#0b0f14" in rule and "color:#e6edf3" in rule and "border:1px solid #4a5868" in rule
    assert re.search(r"#manualContracts::placeholder\{color:#93a3b3", CSS)
    assert "#fff" not in rule.lower() and "white" not in rule.lower()
