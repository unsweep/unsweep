"""#1690 (3): frontend del campo manual en Step 2 y SRI."""
import base64, hashlib, os, re
W = os.path.join(os.path.dirname(__file__), '..', 'web')
IDX = open(os.path.join(W, 'index.html')).read()
JS = open(os.path.join(W, 'assets', 'app.js')).read()


def test_manualbox_oculto_y_checkbox_desmarcado():
    # #1736: details secundario fuera del recuadro, sin checkbox (autoinclusion)
    assert re.search(r'<details id="manualBox" class="manual" hidden>', IDX)
    assert 'manualCb' not in IDX
    assert IDX.index('id="step2Body"') < IDX.index('id="btnQuote"') < IDX.index('id="manualBox"')


def test_misma_advertencia_no_verificado():
    w = 'Unverified tokens, no guarantee, may include scam tokens'
    assert IDX.count(w) >= 2
    assert 'id="manualWarn"' in IDX


def test_js_visibilidad_y_endpoint():
    assert 'listedValueUsd(s) > 0' in JS and 'manualCb' not in JS
    assert "api('quote_manual'" in JS and 'renderManual(s);' in JS
    # manual no forma parte del mensaje EIP-712 firmado
    assert JS.index('unsweepTyped(E, rescue') < JS.index('{ manual: st.manual }')


def test_sri_coincide():
    for f in ('app.js', 'style.css'):
        h = 'sha384-' + base64.b64encode(hashlib.sha384(open(os.path.join(W, 'assets', f), 'rb').read()).digest()).decode()
        assert ('/assets/%s' % f) in IDX and h in IDX, f
