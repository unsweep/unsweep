#!/usr/bin/env python3
"""ORDEN #1690 (1)+(2): capturas de Step 1 a 375 y 1280 px con Chromium headless.
Sirve web/ localmente via page.route y simula /api/config y /api/scan con los JSON
guardados en esta carpeta (scan_holder.json, scan_vacia.json). No hace llamadas a produccion.
"""
import json, mimetypes, pathlib, sys
from playwright.sync_api import sync_playwright

HERE = pathlib.Path(__file__).resolve().parent
WEB = HERE.parents[2] / 'web'
ORIGIN = 'https://unsweep.local'
CASES = {
    'con_valor': ('scan_holder.json', None),
    'sin_valor': ('scan_vacia.json', None),
}
CONFIG = {'chainId': 8453}


def handler(scan_body):
    def h(route):
        url = route.request.url
        path = url[len(ORIGIN):].split('?')[0].split('#')[0]
        if path.startswith('/api/'):
            ep = path[len('/api/'):]
            if ep == 'config':
                return route.fulfill(status=200, content_type='application/json', body=json.dumps(CONFIG))
            if ep == 'scan':
                return route.fulfill(status=200, content_type='application/json', body=scan_body)
            return route.fulfill(status=404, body='{}', content_type='application/json')
        if not url.startswith(ORIGIN):
            return route.abort()  # sin recursos externos (Turnstile, etc.)
        if path in ('', '/'):
            path = '/index.html'
        f = WEB / path.lstrip('/')
        if not f.is_file():
            return route.fulfill(status=404, body='not found')
        ct = mimetypes.guess_type(str(f))[0] or 'application/octet-stream'
        return route.fulfill(status=200, content_type=ct, body=f.read_bytes())
    return h


def main():
    out = []
    with sync_playwright() as p:
        b = p.chromium.launch()
        for case, (fn, addr) in CASES.items():
            body = (HERE / fn).read_text()
            addr = json.loads(body)['address']  # direccion real del JSON guardado
            for w in (375, 1280):
                ctx = b.new_context(viewport={'width': w, 'height': 900})
                pg = ctx.new_page()
                pg.route('**/*', handler(body))
                pg.goto(ORIGIN + '/')
                pg.fill('#victim', addr)
                pg.click('#btnScan')
                pg.wait_for_selector('#btnToStep2:not([hidden]), #supportHint:not([hidden])', timeout=15000)
                pg.wait_for_timeout(300)
                st = pg.evaluate("""() => ({
                  extrasVisible: !document.getElementById('extrasBox').hidden,
                  extrasInScanOut: document.getElementById('scanOut').contains(document.getElementById('extrasBox')),
                  extrasCount: document.querySelectorAll('#extrasList .extraCb').length,
                  extrasTitle: document.getElementById('extrasTitle').innerText,
                  supportVisible: !document.getElementById('supportHint').hidden,
                  supportText: document.getElementById('supportHint').innerText,
                  step2Btn: !document.getElementById('btnToStep2').hidden })""")
                name = f'step1_{case}_{w}.png'
                pg.locator('#step1').screenshot(path=str(HERE / name))
                st.update(case=case, width=w, file=name)
                out.append(st)
                ctx.close()
        b.close()
    (HERE / 'capturas.json').write_text(json.dumps(out, indent=1, ensure_ascii=False))
    print(json.dumps(out, indent=1, ensure_ascii=False))
    ok = all((s['extrasVisible'] and s['extrasInScanOut'] and not s['supportVisible']) if s['case'] == 'con_valor'
             else (s['supportVisible'] and not s['extrasVisible']) for s in out)
    print('OK' if ok else 'FALLO')
    sys.exit(0 if ok else 1)


if __name__ == '__main__':
    main()
