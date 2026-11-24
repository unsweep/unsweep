"""Tests ORDEN #1690 (UX UNSWEEP partes 1 y 2): extras dentro del recuadro de escaneo y aviso de soporte."""
import json
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
INDEX = (ROOT / "web" / "index.html").read_text()
APPJS = (ROOT / "web" / "assets" / "app.js").read_text()
CSS = (ROOT / "web" / "assets" / "style.css").read_text()
NODE = shutil.which("node")
HINT = "Don't see your token? Email"


def test_index_extras_titulo_advertencia_y_hint():
    i_box = INDEX.index('id="extrasBox" hidden')
    i_title = INDEX.index("Additional tokens detected (optional)")
    i_warn = INDEX.index('id="extrasWarn"')
    i_list = INDEX.index('id="extrasList"')
    assert i_box < i_title < i_list < i_warn  # #1736: aviso debajo de la lista
    assert "Unverified tokens, no guarantee, may include scam tokens" in INDEX
    assert INDEX.count(HINT) == 1
    assert 'id="supportHint" class="small" hidden' in INDEX
    assert '<p id="supportHint" class="small" hidden>Don\'t see your token? Email support@unsweep.com</p>' in INDEX
    # invariante test_portada: un solo mailto (pie)
    assert INDEX.count('href="mailto:support@unsweep.com"') == 1


def test_appjs_reglas_extras_intactas():
    assert "cb.checked = false" in APPJS
    assert "list.slice(0, 20)" in APPJS
    # attach antes de render: renderExtras necesita #extrasList en el DOM
    a = APPJS.index("attachResultExtras(s);")
    r = APPJS.index("renderExtras(s.extras || []);")
    s = APPJS.index("show($('scanOut'), out, 'ok');")
    assert s < a < r


def test_css_estilo_dentro_de_scanout():
    assert "#scanOut #extrasBox" in CSS and "#scanOut #supportHint" in CSS


HARNESS = r"""
function mkEl(tag, id){ const e = {tag, id, hidden:false, checked:false, type:'', value:'', className:'', parent:null, children:[], text:'',
  appendChild(c){ if(c.parent){ const p=c.parent.children; p.splice(p.indexOf(c),1);} c.parent=this; this.children.push(c); return c; },
  get childNodes(){ return this.children; },
  set textContent(v){ this.children.forEach(c=>c.parent=null); this.children=[]; this.text=String(v); },
  get textContent(){ return this.text + this.children.map(c=>c.textContent).join(''); } }; return e; }
const root = mkEl('body','root');
const els = {};
function reg(e){ els[e.id]=e; return e; }
const scanOut = root.appendChild(reg(mkEl('div','scanOut')));
const box = root.appendChild(reg(mkEl('div','extrasBox'))); box.hidden = true;
box.appendChild(reg(mkEl('div','extrasList')));
const hint = root.appendChild(reg(mkEl('p','supportHint'))); hint.hidden = true;
const $ = (id) => els[id];
const document = { createElement: (t) => mkEl(t, null), createTextNode: (t) => { const n = mkEl('#text', null); n.text = t; return n; } };
const addr = (a) => (/^0x[0-9a-fA-F]{40}$/.test(a) ? a : null);
const fmt = (b, d) => String(b);
function show(el, lines){ el.textContent=''; [].concat(lines).forEach(l=>{ const p=mkEl('div',null); p.text=l; el.appendChild(p); }); }
__CODE__
const out = {};
const A1 = '0x' + '11'.repeat(20), A2 = '0x' + '22'.repeat(20);
out.sv = [
  supportVisible({tokens:[], extras:[], rescuable:false}),
  supportVisible({tokens:[{balance:'0'}], rescuable:false}),
  supportVisible({tokens:[{balance:'5'}], rescuable:false}),
  supportVisible({tokens:[], rescuable:true}),
  supportVisible({tokens:[], extras:[{address:A1, balance:'9'}], rescuable:false}),
  supportVisible(null)
];
// escaneo con valor: extras dentro de scanOut, hint oculto
let s = {tokens:[{symbol:'USDC', balance:'1000', decimals:6}], extras:[{address:A1, symbol:'BRETT', balance:'7', decimals:18},{address:'bad', symbol:'X'}], rescuable:true};
show(scanOut, ['Address: x']); attachResultExtras(s); renderExtras(s.extras);
out.withValue = { boxParent: box.parent && box.parent.id, hintParent: hint.parent && hint.parent.id, boxHidden: box.hidden, hintHidden: hint.hidden,
  n: els.extrasList.children.length, cbs: els.extrasList.children.map(d=>d.children[0].children[0].checked) };
// segundo escaneo sin saldo: show() vacia scanOut y los nodos se reinsertan
s = {tokens:[], extras:[], rescuable:false};
show(scanOut, ['Address: y']); attachResultExtras(s); renderExtras(s.extras);
out.empty = { boxParent: box.parent && box.parent.id, hintParent: hint.parent && hint.parent.id, boxHidden: box.hidden, hintHidden: hint.hidden, last: scanOut.children[scanOut.children.length-1].id };
console.log(JSON.stringify(out));
"""


@pytest.mark.skipif(NODE is None, reason="node no disponible")
def test_logica_visibilidad_node(tmp_path):
    i = APPJS.index("  const EXTRAS_BOX")
    j = APPJS.index("  function checkedExtras")
    code = APPJS[i:j]
    f = tmp_path / "h.js"
    f.write_text(HARNESS.replace("__CODE__", code))
    r = subprocess.run([NODE, str(f)], capture_output=True, text=True, timeout=30)
    assert r.returncode == 0, r.stderr
    o = json.loads(r.stdout.strip().splitlines()[-1])
    assert o["sv"] == [True, True, False, False, True, False]
    w = o["withValue"]
    assert w["boxParent"] == "scanOut" and w["hintParent"] == "scanOut"
    assert w["boxHidden"] is False and w["hintHidden"] is True
    assert w["n"] == 1 and w["cbs"] == [False]
    e = o["empty"]
    assert e["boxParent"] == "scanOut" and e["hintParent"] == "scanOut"
    assert e["boxHidden"] is True and e["hintHidden"] is False
    assert e["last"] == "supportHint"
