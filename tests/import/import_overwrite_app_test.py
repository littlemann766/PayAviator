#!/usr/bin/env python3
"""Android app (WebView page) spreadsheet import: Overwrite / Keep mine for rows matching an existing bill. Headless Chrome with the app's own index.html.
Usage: python3 tests/import/import_overwrite_app_test.py   (needs playwright, node, google-chrome or chromium). Seeded demo data only."""
import http.server, os, re, socketserver, subprocess, sys, threading, functools, datetime, tempfile
from playwright.sync_api import sync_playwright

HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.abspath(os.path.join(HERE, '..', '..'))
SEED = open(os.path.join(HERE, 'seed.js')).read()
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
check('assets/index.html is byte-identical to the root index.html', open(os.path.join(ROOT, 'app/src/main/assets/index.html'), 'rb').read() == html.encode('utf-8'))
check('shared core embedded in index.html equals tests/import/import-core.js', re.search(r'<script id="pa-import-core">\n(.*?)</script>', html, re.S).group(1) == open(os.path.join(HERE, 'import-core.js')).read())

today = datetime.date.today(); first = today.replace(day=1)
def dd(n): return (first + datetime.timedelta(days=n - 1)).isoformat()
tmp = tempfile.mkdtemp(); CSV = os.path.join(tmp, 'bills.csv'); CSV2 = os.path.join(tmp, 'bills_notes.csv')
open(CSV, 'w').write('\n'.join(['Bill,Amount,Due Date,Frequency', f'Rent,1495.50,{dd(1)},Monthly', f'Internet,79.99,{dd(15)},Monthly', f'Phone,85,{dd(18)},Monthly', f'Brand New Thing,12,{dd(20)},Monthly']) + '\n')
ROWNO = {'Rent': 2, 'Internet': 3, 'Phone': 4, 'New': 5}
SNAP = "()=>{const f=n=>bills.filter(b=>b.name===n);const st=JSON.parse(localStorage.getItem('payAviator_v1')||'[]');const r=bills.find(b=>b.id==='b-rent');return {n:bills.length,rent:f('Rent').map(b=>({id:b.id,amount:b.amount,color:b.color,cat:b.category,due:b.due,paid:billPaidAmounts[b.id+'|'+b.due],ov:billOverrides[b.id+'|'+b.due]})),net:f('Internet').map(b=>({id:b.id,amount:b.amount,notes:b.notes,autopay:b.autopay,notify:b.notify})),phone:f('Phone').length,newc:f('Brand New Thing').length,stRent:st.filter(b=>b.name==='Rent').map(b=>({id:b.id,amount:b.amount})),stN:st.length,rev:localStorage.getItem('payAviator_bills_rev_v1')}}"

def run():
    exe = '/usr/bin/google-chrome' if os.path.exists('/usr/bin/google-chrome') else None
    with sync_playwright() as p:
        b = p.chromium.launch(executable_path=exe, args=['--no-sandbox'])
        def fresh(w=390, h=844, mutate=''):
            ctx = b.new_context(viewport={'width': w, 'height': h}, device_scale_factor=2, is_mobile=w < 600, has_touch=w < 600, timezone_id='America/New_York')
            pg = ctx.new_page(); logs = []
            pg.on('pageerror', lambda e: logs.append(str(e).split('\n')[0])); pg.on('dialog', lambda d: (logs.append('alert: ' + d.message[:80]), d.dismiss()))
            pg.goto(U); pg.wait_for_timeout(800)
            pg.evaluate("localStorage.clear(); indexedDB.deleteDatabase('PayAviatorPersonalDB')"); pg.reload(); pg.wait_for_timeout(2500)
            pg.evaluate(SEED); pg.reload(); pg.wait_for_timeout(3000)
            pg.evaluate("document.querySelectorAll('dialog[open]').forEach(d=>d.close())")
            if mutate: pg.evaluate(mutate)
            pg.evaluate("document.querySelector('.mb119-nav[data-view=\"bills\"]').click()"); pg.wait_for_timeout(700)
            pg.click('[data-pai-open=bills]'); pg.wait_for_selector('[data-pai-file]'); pg.set_input_files('[data-pai-file]', CSV); pg.wait_for_selector('.pai-row')
            return pg, logs
        row = lambda pg, n: pg.locator(f'.pai-row[data-row="{ROWNO[n]}"]')
        def add(pg):
            pg.click('[data-pai-add]'); pg.wait_for_selector('[data-pai-result]'); pg.wait_for_timeout(600); return pg.inner_text('[data-pai-result]')

        print('[defaults: Keep mine]')
        pg, logs = fresh(); s0 = pg.evaluate(SNAP)
        check('3 matched rows offer Keep mine / Overwrite, default Keep mine, unticked', pg.locator('.pai-act').count() == 3 and all(row(pg, n).locator('[data-r=act-keep]').get_attribute('aria-pressed') == 'true' and not row(pg, n).locator('[data-r=chk]').is_checked() for n in ('Rent', 'Internet', 'Phone')))
        d = row(pg, 'Rent').locator('[data-r=diff]').inner_text()
        check('existing vs new shown (Amount $1,450.00 -> $1,495.50)', '$1,450.00' in d and '$1,495.50' in d, d)
        check('identical row says nothing would change', 'Nothing would change' in row(pg, 'Phone').locator('[data-r=diff]').inner_text())
        check('Add counts only the new row', pg.inner_text('[data-pai-add]').strip() == 'Add 1 bill', pg.inner_text('[data-pai-add]'))
        pg.click('[data-pai-all]'); check('Select all does not flip matched rows to Overwrite', row(pg, 'Rent').locator('[data-r=act-keep]').get_attribute('aria-pressed') == 'true')
        res = add(pg); s1 = pg.evaluate(SNAP)
        check('Keep mine: Rent/Internet untouched, one new bill, no copies', s1['rent'][0]['amount'] == 1450 and len(s1['rent']) == 1 and s1['net'][0]['amount'] == 74.99 and s1['newc'] == 1 and s1['n'] == s0['n'] + 1, str(s1))
        check('result says 3 of your bills kept', '3 of your bills kept' in res, res)
        check('no page errors / alerts', not logs, str(logs))

        print('[Overwrite one: in place, history kept, saved for sync]')
        pg, logs = fresh(mutate="(()=>{const x=bills.find(b=>b.id==='b-net');x.notes='my own note';x.autopay=true;persistBills()})()")
        s0 = pg.evaluate(SNAP)
        row(pg, 'Rent').locator('[data-r=act-overwrite]').click()
        check('Overwrite ticks the row; button reads "Add 1 bill, Overwrite 1"', row(pg, 'Rent').locator('[data-r=chk]').is_checked() and pg.inner_text('[data-pai-add]').strip() == 'Add 1 bill, Overwrite 1', pg.inner_text('[data-pai-add]'))
        res = add(pg); s1 = pg.evaluate(SNAP); r = s1['rent']
        check('one Rent, same id b-rent, new amount', len(r) == 1 and r[0]['id'] == 'b-rent' and r[0]['amount'] == 1495.5, str(r))
        check('colour, category, paid history kept', r[0]['color'] == '#3b82f6' and r[0]['cat'] == 'Housing' and r[0]['paid'] == 1450 and r[0]['ov'] == {'paid': True}, str(r))
        check('only the new row added (no accidental duplicate)', s1['n'] == s0['n'] + 1 and s1['newc'] == 1)
        check('saved to the watched local storage under the same id, revision bumped (what cloud sync diffs)', s1['stRent'] == [{'id': 'b-rent', 'amount': 1495.5}] and s1['rev'] != s0['rev'], str((s1['stRent'], s0['rev'], s1['rev'])))
        check('result says one existing bill updated', 'pdated 1 existing bill' in res, res)
        pg.reload(); pg.wait_for_timeout(3000); s2 = pg.evaluate(SNAP)
        check('overwrite survives an app restart', s2['rent'][0]['amount'] == 1495.5 and s2['rent'][0]['id'] == 'b-rent' and s2['rent'][0]['paid'] == 1450 and len(s2['rent']) == 1, str(s2['rent']))
        check('no page errors / alerts', not logs, str(logs))

        print('[Mixed + notes preserved]')
        pg, logs = fresh(mutate="(()=>{const x=bills.find(b=>b.id==='b-net');x.notes='my own note';x.autopay=true;persistBills()})()")
        row(pg, 'Rent').locator('[data-r=act-overwrite]').click(); row(pg, 'Internet').locator('[data-r=act-keep]').click(); row(pg, 'Phone').locator('[data-r=act-overwrite]').click()
        check('button reads "Add 1 bill, Overwrite 2"', pg.inner_text('[data-pai-add]').strip() == 'Add 1 bill, Overwrite 2', pg.inner_text('[data-pai-add]'))
        res = add(pg); s1 = pg.evaluate(SNAP)
        check('Rent overwritten, Internet kept, Phone no-op reported, new added', s1['rent'][0]['amount'] == 1495.5 and s1['net'][0]['amount'] == 74.99 and '1 already matched' in res and s1['phone'] == 1 and s1['newc'] == 1, res)
        pg.click('[data-pai-done]'); pg.wait_for_timeout(600)
        pg.click('[data-pai-open=bills]'); pg.wait_for_selector('[data-pai-file]'); pg.set_input_files('[data-pai-file]', CSV); pg.wait_for_selector('.pai-row')
        row(pg, 'Internet').locator('[data-r=act-overwrite]').click(); add(pg); s2 = pg.evaluate(SNAP)
        check('overwriting Internet updates the amount but keeps the notes and autopay (file has no such columns)', s2['net'][0]['amount'] == 79.99 and s2['net'][0]['notes'] == 'my own note' and s2['net'][0]['autopay'] is True and len(s2['net']) == 1, str(s2['net']))
        check('no page errors / alerts', not logs, str(logs))

        print('[shortcuts + checkbox]')
        pg, logs = fresh(); s0 = pg.evaluate(SNAP)
        check('shortcut buttons offered', pg.locator('[data-pai-overwrite-all]').count() == 1 and pg.locator('[data-pai-keep-all]').count() == 1)
        pg.click('[data-pai-overwrite-all]')
        check('Overwrite all duplicates flips every matched row; new row stays ticked', all(row(pg, n).locator('[data-r=act-overwrite]').get_attribute('aria-pressed') == 'true' for n in ('Rent', 'Internet', 'Phone')) and 'Overwrite 3' in pg.inner_text('[data-pai-add]') and row(pg, 'New').locator('[data-r=chk]').is_checked(), pg.inner_text('[data-pai-add]'))
        pg.click('[data-pai-keep-all]')
        check('Keep all mine flips them back', all(row(pg, n).locator('[data-r=act-keep]').get_attribute('aria-pressed') == 'true' and not row(pg, n).locator('[data-r=chk]').is_checked() for n in ('Rent', 'Internet', 'Phone')) and pg.inner_text('[data-pai-add]').strip() == 'Add 1 bill')
        pg.click('[data-pai-overwrite-all]'); pg.click('[data-pai-none]')
        check('Select none resets to Keep mine and disables Add', row(pg, 'Rent').locator('[data-r=act-keep]').get_attribute('aria-pressed') == 'true' and pg.is_disabled('[data-pai-add]'))
        pg.click('[data-pai-overwrite-all]'); row(pg, 'New').locator('[data-r=chk]').uncheck(); add(pg); s1 = pg.evaluate(SNAP)
        check('Overwrite all: Rent+Internet updated in place, nothing added, no copies', s1['rent'][0]['amount'] == 1495.5 and len(s1['rent']) == 1 and s1['net'][0]['amount'] == 79.99 and s1['n'] == s0['n'], str(s1))
        pg, logs = fresh()
        row(pg, 'Rent').locator('[data-r=chk]').check()
        check('ticking a matched row means Overwrite, never a copy', row(pg, 'Rent').locator('[data-r=act-overwrite]').get_attribute('aria-pressed') == 'true')
        row(pg, 'Rent').locator('[data-r=name]').fill('Zebra Habitat'); pg.wait_for_timeout(100)
        check('renamed so it no longer matches: plain new row, unticked (not silently added)', row(pg, 'Rent').locator('.pai-act').count() == 0 and not row(pg, 'Rent').locator('[data-r=chk]').is_checked())
        row(pg, 'Rent').locator('[data-r=name]').fill('Rent'); pg.wait_for_timeout(100)
        check('name back: controls return defaulting to Keep mine', row(pg, 'Rent').locator('[data-r=act-keep]').get_attribute('aria-pressed') == 'true')
        check('no page errors / alerts', not logs, str(logs))

        print('[screens]')
        os.makedirs('/workspace/shots/import-overwrite', exist_ok=True)
        pg, logs = fresh(); row(pg, 'Rent').locator('[data-r=act-overwrite]').click()
        over = pg.evaluate("(()=>{const f=document.querySelector('#paImportDlg .form');return f.scrollWidth>f.clientWidth+1||document.documentElement.scrollWidth>innerWidth+1})()")
        check('no horizontal overflow at 390px', not over)
        pg.screenshot(path='/workspace/shots/import-overwrite/app-mobile390-preview.png')
        pg.click('[data-pai-overwrite-all]'); pg.screenshot(path='/workspace/shots/import-overwrite/app-mobile390-overwrite-all.png')
        add(pg); pg.screenshot(path='/workspace/shots/import-overwrite/app-mobile390-result.png')
        pg, logs = fresh(w=1280, h=900); row(pg, 'Rent').locator('[data-r=act-overwrite]').click(); pg.screenshot(path='/workspace/shots/import-overwrite/app-desktop-preview.png')
        b.close()
run()
print(f'\n{passes} checks passed, {len(fails)} failed')
if fails: print('\n'.join(fails)); sys.exit(1)
