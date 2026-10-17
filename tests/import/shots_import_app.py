#!/usr/bin/env python3
"""SHOTS for Android app (WebView page) spreadsheet import, end to end in headless Chrome with the app's own index.html.
Usage: python3 tests/import/import_app_test.py   (needs playwright, openpyxl, node, google-chrome or chromium)
Seeds demo data (tests/import/seed.js), so no real data is touched."""
import http.server, os, re, shutil, socketserver, subprocess, sys, threading, functools, datetime, tempfile
from playwright.sync_api import sync_playwright
import openpyxl

HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.abspath(os.path.join(HERE, '..', '..'))
FX = os.path.join(HERE, 'import_fixtures'); SEED = open(os.path.join(HERE, 'seed.js')).read()
class Q(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *a): pass
class TS(socketserver.ThreadingTCPServer): allow_reuse_address = True; daemon_threads = True
srv = TS(('127.0.0.1', 0), functools.partial(Q, directory=ROOT)); PORT = srv.server_address[1]
threading.Thread(target=srv.serve_forever, daemon=True).start()
U = f'http://localhost:{PORT}/index.html'
fails, passes = [], 0
def check(name, cond, extra=''):
    global passes
    if cond: passes += 1; print('  ok  ', name)
    else: fails.append(name); print('  FAIL', name, extra)

html = open(os.path.join(ROOT, 'index.html'), encoding='utf-8').read()
core_inline = re.search(r'<script id="pa-import-core">\n(.*?)</script>', html, re.S).group(1)
tmp = tempfile.mkdtemp(); open(os.path.join(tmp, 'import-core.js'), 'w').write(core_inline)
print('[core embedded in index.html]')
r = subprocess.run(['node', os.path.join(HERE, 'import_core_test.mjs')], env={**os.environ, 'PA_IMPORT_CORE': os.path.join(tmp, 'import-core.js')}, capture_output=True, text=True)
print('   ', r.stdout.strip().splitlines()[-1] if r.stdout.strip() else r.stderr[-300:])
check('the parsing core inside index.html passes all node core tests', r.returncode == 0)
check('assets/index.html is byte-identical to the root index.html', open(os.path.join(ROOT, 'app/src/main/assets/index.html'), 'rb').read() == open(os.path.join(ROOT, 'index.html'), 'rb').read())

today = datetime.date.today()
def dd(n): return (today.replace(day=1) + datetime.timedelta(days=n - 1))
live = os.path.join(tmp, 'this_month.xlsx')
wb = openpyxl.Workbook(); ws = wb.active; ws.append(['Bill', 'Amount', 'Due Date', 'Frequency', 'Category', 'Paid?'])
for r_ in [('Rent', 1450, dd(1), 'Monthly', 'Housing', 'No'), ('Gym', 24.99, dd(10), 'Monthly', 'Subscriptions', 'Yes'), ('Dog walking income', 200, dd(12), 'Weekly', '', ''), ('Old loan', 55, dd(20), 'Never', 'Other', ''), ('Total', 400, None, None, None, None)]: ws.append(list(r_))
wb.save(live)
ROWNO = {'Rent': 2, 'Gym': 3, 'Dog walking income': 4, 'Old loan': 5, 'Total': 6}

def run():
    exe = '/usr/bin/google-chrome' if os.path.exists('/usr/bin/google-chrome') else None
    with sync_playwright() as p:
        b = p.chromium.launch(executable_path=exe, args=['--no-sandbox'])
        ctx = b.new_context(viewport={'width': 390, 'height': 844}, device_scale_factor=2, is_mobile=True, has_touch=True, timezone_id='America/New_York')
        pg = ctx.new_page(); logs = []; hosts = set(); posts = []
        pg.on('pageerror', lambda e: logs.append(str(e).split('\n')[0]))
        pg.on('dialog', lambda d: (logs.append('alert: ' + d.message[:80]), d.dismiss()))
        def on_req(rq):
            hosts.add(rq.url.split('/')[2])
            if rq.method != 'GET': posts.append(rq.url)
        pg.on('request', on_req)
        pg.goto(U); pg.wait_for_timeout(800)
        pg.evaluate("localStorage.clear(); indexedDB.deleteDatabase('PayAviatorPersonalDB')"); pg.reload(); pg.wait_for_timeout(2500)
        pg.evaluate(SEED); pg.reload(); pg.wait_for_timeout(3000)
        pg.evaluate("document.querySelectorAll('dialog[open]').forEach(d=>d.close())")
        nav = lambda v: (pg.evaluate(f"document.querySelector('.mb119-nav[data-view=\"{v}\"]').click()"), pg.wait_for_timeout(700))

        OUT = sys.argv[1] if len(sys.argv) > 1 else '/workspace/shots/import'; os.makedirs(OUT, exist_ok=True)
        def shot(n): pg.wait_for_timeout(300); pg.screenshot(path=f'{OUT}/app-mobile-{n}.png')
        nav('bills'); pg.wait_for_selector('[data-pai-open=bills]'); shot('0-bills-entry')
        pg.click('[data-pai-open=bills]'); pg.wait_for_selector('[data-pai-file]'); shot('1-file-pick')
        pg.set_input_files('[data-pai-file]', live); pg.wait_for_selector('.pai-row'); shot('2-preview-list')
        pg.locator('.pai-row').nth(4).scroll_into_view_if_needed(); shot('3-preview-skip-and-duplicate')
        pg.click('[data-pai-add]')
        pg.wait_for_selector('[data-pai-result]'); shot('4-result')
        pg.click('[data-pai-done]'); pg.wait_for_timeout(700); shot('5-bills-after-import')
        pg.click('[data-pai-open=bills]'); pg.set_input_files('[data-pai-file]', os.path.join(FX, 'ambiguous.xlsx')); pg.wait_for_selector('[data-pai-map]'); shot('6-column-mapping')
        pg.keyboard.press('Escape'); pg.evaluate("document.querySelectorAll('dialog[open]').forEach(d=>d.close())")
        pg.click('[data-pai-open=bills]'); pg.set_input_files('[data-pai-file]', os.path.join(FX, 'old_format.xls')); pg.wait_for_selector('[data-pai-error]'); shot('7-old-xls-message')
        pg.evaluate("document.querySelectorAll('dialog[open]').forEach(d=>d.close())")
        nav('settings'); pg.evaluate("[...document.querySelectorAll('button')].find(b=>b.dataset.mb123Settings==='backup'&&b.offsetParent).click()"); pg.wait_for_timeout(900)
        pg.evaluate("document.querySelector('[data-pai-section]:not([hidden])') && [...document.querySelectorAll('[data-pai-section]')].find(e=>e.offsetParent).scrollIntoView()"); shot('8-settings-entry')
        b.close()
run(); print(sorted(os.listdir("/workspace/shots/import")))
