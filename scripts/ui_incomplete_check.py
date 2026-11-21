"""M2d-1: prueba LOCAL de la UI en modo incomplete. No toca produccion ni e2e_web.py.
Sirve web/ en 127.0.0.1:8798 y reenvia /api/* al relayer local 127.0.0.1:8799
(arrancado con UNSWEEP_LOCAL_TEST=1 UNSWEEP_TEST_FAIL=<modo>)."""
import http.server, threading, urllib.request, os, sys, json, functools
from playwright.sync_api import sync_playwright

ROOT = os.path.join(os.path.dirname(__file__), '..', 'web')
OUT = os.path.join(os.path.dirname(__file__), '..', 'evidence', 'm2d-1')
UP = 'http://127.0.0.1:8799'


class H(http.server.SimpleHTTPRequestHandler):
    def _proxy(self, method):
        n = int(self.headers.get('Content-Length') or 0)
        body = self.rfile.read(n) if n else None
        req = urllib.request.Request(UP + self.path, data=body, method=method,
                                     headers={'Content-Type': 'application/json',
                                              'User-Agent': 'unsweep-selftest/m2d-1-ui'})
        try:
            r = urllib.request.urlopen(req, timeout=90); code, data = r.status, r.read()
        except urllib.error.HTTPError as e:
            code, data = e.code, e.read()
        self.send_response(code); self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', str(len(data))); self.end_headers(); self.wfile.write(data)

    def do_GET(self):
        if self.path.startswith('/api/'):
            return self._proxy('GET')
        return super().do_GET()

    def do_POST(self):
        return self._proxy('POST')

    def log_message(self, *a):
        pass


def main(chain='base', addr='0x000000000000000000000000000000000000dEaD', tag='truncated'):
    srv = http.server.ThreadingHTTPServer(('127.0.0.1', 8798), functools.partial(H, directory=ROOT))
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    res = {}
    with sync_playwright() as p:
        b = p.chromium.launch(); pg = b.new_page()
        pg.goto('http://127.0.0.1:8798/', wait_until='load')
        pg.select_option('#chain', chain)
        pg.fill('#victim', addr)
        pg.click('#btnScan')
        pg.wait_for_function("() => { const t = document.getElementById('scanOut').textContent; return t && !/^Read-only check on/.test(t.trim()) || /Incomplete|Delegation|Approv/.test(t); }", timeout=90000)
        pg.wait_for_timeout(500)
        el = pg.locator('#scanOut')
        res = {'mode': tag, 'chain': chain, 'text': el.inner_text(), 'class': el.get_attribute('class'),
               'border': pg.eval_on_selector('#scanOut', 'e => getComputedStyle(e).borderTopColor')}
        pg.screenshot(path=os.path.join(OUT, 'ui_incomplete_%s.png' % tag), full_page=True)
        b.close()
    srv.shutdown()
    t = res['text']
    res['has_warning'] = 'Incomplete check' in t and 'NOT a clean result' in t
    res['claims_clean'] = any(s in t.lower() for s in ('no approvals found', 'nothing found', 'no delegation', 'looks clean', 'all clear'))
    res['PASS'] = res['has_warning'] and not res['claims_clean'] and 'err' in (res['class'] or '')
    json.dump(res, open(os.path.join(OUT, 'ui_incomplete_%s.json' % tag), 'w'), indent=1)
    print(json.dumps(res, indent=1))


if __name__ == '__main__':
    main(*sys.argv[1:])
