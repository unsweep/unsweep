#!/usr/bin/env python3
"""UI-1: auditoria LOCAL de accesibilidad (axe-core, WCAG 2 AA) de web/index.html.
Sirve web/ en 127.0.0.1:8797 con la CSP indicada en CSP_FILE (cabecera real de produccion).
No toca produccion, relayer, escaner ni contrato. Uso: CSP_FILE=/tmp/csp_before.txt AXE=/tmp/axe/node_modules/axe-core/axe.min.js python scripts/ui_a11y_check.py"""
import http.server, threading, os, sys, json, functools
from playwright.sync_api import sync_playwright

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'web')
AXE = os.environ.get('AXE', '/tmp/axe/node_modules/axe-core/axe.min.js')
CSP = ''
if os.environ.get('CSP_FILE'):
    line = open(os.environ['CSP_FILE']).read().strip()
    CSP = line.split(':', 1)[1].strip() if ':' in line else line
PORT = 8797


class H(http.server.SimpleHTTPRequestHandler):
    def end_headers(self):
        if CSP:
            self.send_header('Content-Security-Policy', CSP)
        super().end_headers()

    def log_message(self, *a):
        pass


LUM = """
(el) => {
  function rgb(s){const m=s.match(/rgba?\\(([^)]+)\\)/); if(!m) return null; const p=m[1].split(',').map(x=>parseFloat(x)); return p;}
  function lum(c){const a=c.slice(0,3).map(v=>{v/=255;return v<=0.03928?v/12.92:Math.pow((v+0.055)/1.055,2.4)});return 0.2126*a[0]+0.7152*a[1]+0.0722*a[2];}
  function bg(e){while(e){const c=rgb(getComputedStyle(e).backgroundColor); if(c && (c.length<4||c[3]>0)) return c; e=e.parentElement;} return [255,255,255];}
  const fg=rgb(getComputedStyle(el).color), b=bg(el); const L1=lum(fg), L2=lum(b);
  return {text:(el.innerText||'').slice(0,50), fg:getComputedStyle(el).color, bg:'rgb('+b.slice(0,3).join(',')+')',
          ratio:Math.round(((Math.max(L1,L2)+0.05)/(Math.min(L1,L2)+0.05))*100)/100,
          underline:getComputedStyle(el).textDecorationLine};
}
"""

PH = """
(el) => { const cs=getComputedStyle(el); const c=document.createElement('canvas').getContext('2d');
  c.font=cs.fontStyle+' '+cs.fontWeight+' '+cs.fontSize+' '+cs.fontFamily;
  const w=c.measureText(el.placeholder).width;
  const avail=el.clientWidth-parseFloat(cs.paddingLeft)-parseFloat(cs.paddingRight);
  return {id:el.id, text_px:Math.ceil(w), avail_px:Math.floor(avail), fits:w<=avail,
          page_overflow:document.documentElement.scrollWidth>window.innerWidth}; }
"""


def main():
    srv = http.server.ThreadingHTTPServer(('127.0.0.1', PORT), functools.partial(H, directory=ROOT))
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    res = {'csp_header_used': bool(CSP), 'csp_errors': [], 'axe': {}, 'manual_contrast': [], 'placeholder': {}}
    ok = True
    with sync_playwright() as p:
        br = p.chromium.launch()
        for name, vp in (('desktop', {'width': 1280, 'height': 900}), ('mobile', {'width': 360, 'height': 740})):
            # 1) pagina con la CSP real aplicada: solo recoge errores CSP de la propia pagina
            cpg = br.new_page(viewport=vp)
            cpg.on('console', lambda m: res['csp_errors'].append(m.text) if 'Content Security Policy' in m.text else None)
            cpg.goto(f'http://127.0.0.1:{PORT}/', wait_until='load'); cpg.wait_for_timeout(1500); cpg.close()
            # 2) contexto con bypass_csp SOLO para inyectar axe (herramienta de auditoria, no la web)
            ctx = br.new_context(viewport=vp, bypass_csp=True)
            pg = ctx.new_page()
            pg.goto(f'http://127.0.0.1:{PORT}/', wait_until='load')
            # mostrar pasos ocultos y abrir el details para auditar todo el contenido
            pg.evaluate("""document.querySelectorAll('section[hidden]').forEach(s=>s.hidden=false);
                           document.querySelectorAll('details').forEach(d=>d.open=true);""")
            pg.add_script_tag(path=AXE)
            r = pg.evaluate("""async()=>{const r=await axe.run(document,{runOnly:{type:'tag',values:['wcag2a','wcag2aa']}});
                return {violations:r.violations.map(v=>({id:v.id,impact:v.impact,n:v.nodes.length,targets:v.nodes.slice(0,5).map(n=>n.target.join(' '))})),
                        passes_color_contrast:(r.passes.find(x=>x.id==='color-contrast')||{nodes:[]}).nodes.length,
                        incomplete:r.incomplete.map(v=>({id:v.id,n:v.nodes.length}))};}""")
            res['axe'][name] = r
            if r['violations']:
                ok = False
            if name == 'desktop':
                for sel in ['#tabRescueMainnet', '#guides a', 'footer a', 'details.info summary', '.notice', '#victim']:
                    for h in pg.query_selector_all(sel):
                        m = h.evaluate(LUM); m['sel'] = sel; res['manual_contrast'].append(m)
                        if m['ratio'] < 4.5:
                            ok = False
                        if sel.endswith(' a') and 'underline' not in m['underline']:
                            ok = False
            for sel in ['#victim', '#safe', '#pk']:
                m = pg.eval_on_selector(sel, PH)
                res['placeholder'][f'{name}:{sel}'] = m
                if sel == '#victim' and (not m['fits'] or m['page_overflow']):
                    ok = False
            pg.screenshot(path=f'/tmp/ui1_{name}.png', full_page=True)
            ctx.close()
        br.close()
    srv.shutdown()
    if res['csp_errors']:
        ok = False
    res['OK'] = ok
    print(json.dumps(res, indent=1, ensure_ascii=False))
    return 0 if ok else 1


if __name__ == '__main__':
    sys.exit(main())
