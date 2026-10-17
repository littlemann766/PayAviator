#!/usr/bin/env python3
"""Android app (WebView page) spreadsheet import, end to end in headless Chrome with the app's own index.html.
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

        print('[entry points]')
        nav('bills'); pg.wait_for_selector('[data-pai-open=bills]', timeout=8000)
        check('Bills tab has "Import from spreadsheet" next to Add Bill', pg.locator('#pa401BillsActions [data-pai-open=bills]').count() == 1)
        nav('settings'); pg.evaluate("[...document.querySelectorAll('button')].find(b=>b.dataset.mb123Settings==='backup'&&b.offsetParent).click()"); pg.wait_for_timeout(900)
        check('Settings > Backup & App has an Import section', pg.locator('[data-pai-section] [data-pai-open=settings]:visible').count() == 1)
        pg.evaluate("document.querySelector('[data-pai-open=settings]').click()"); pg.wait_for_selector('#paImportDlg[open]')
        check('settings entry opens the importer; privacy line shown', 'read on this phone only' in pg.inner_text('#paImportDlg'))
        pg.evaluate("document.getElementById('paImportDlg').close()")
        pg.evaluate("window.mb2034CloseSettings&&window.mb2034CloseSettings()"); nav('bills')

        print('[bad files]')
        pg.click('[data-pai-open=bills]'); pg.wait_for_selector('[data-pai-file]')
        for f, word in [('old_format.xls', '.xlsx'), ('empty.csv', 'empty'), ('truncated.xlsx', ''), ('garbage.csv', 'not a readable'), ('opendoc.ods', 'xlsx'), ('bomb.xlsx', 'too large')]:
            pg.set_input_files('[data-pai-file]', os.path.join(FX, f)); pg.wait_for_timeout(300)
            txt = pg.inner_text('[data-pai-error]') if pg.locator('[data-pai-error]').count() else ''
            check(f'{f}: plain-English message, stays on the pick step', len(txt) > 10 and word.lower() in txt.lower() and pg.locator('[data-pai-list]').count() == 0, txt)

        print('[preview and duplicates]')
        hosts.clear(); posts.clear()
        n_bills0 = pg.evaluate("bills.length"); n_checks0 = pg.evaluate("paychecks.length")
        pg.set_input_files('[data-pai-file]', live); pg.wait_for_selector('.pai-row')
        row = lambda n: pg.locator(f'.pai-row[data-row="{ROWNO[n]}"]')
        check('went straight to the list; every row shown', pg.locator('[data-pai-map]').count() == 0 and pg.locator('.pai-row').count() == 5)
        check('"Rent" (already in the app) flagged Possible duplicate and unticked', row('Rent').locator('[data-dup]').count() == 1 and not row('Rent').locator('[data-r=chk]').is_checked())
        check('new rows ticked; Total defaults to Skip; income row defaults to Income', row('Gym').locator('[data-r=chk]').is_checked() and row('Total').locator('[data-r=dest]').input_value() == 'skip' and row('Dog walking income').locator('[data-r=dest]').input_value() == 'income')
        check('nothing left the phone while reading the file', hosts <= {f'localhost:{PORT}'} and not posts, str((hosts, posts)))

        print('[edit, add]')
        row('Gym').locator('[data-r=name]').fill('Pool pass'); row('Gym').locator('[data-r=amount]').fill('29.99'); row('Gym').locator('[data-r=due]').fill(dd(11).isoformat())
        row('Old loan').locator('[data-r=chk]').uncheck()
        check('Add button reflects the selection', 'Add 1 bill and 1 income' in pg.inner_text('[data-pai-add]'), pg.inner_text('[data-pai-add]'))
        t = row('Total'); t.locator('[data-r=dest]').select_option('bills'); t.locator('[data-r=chk]').check()
        pg.click('[data-pai-add]'); check('a ticked row with no date blocks Add and says what to fix', pg.locator('[data-pai-msg]').is_visible() and t.locator('[data-needs]').count() == 1)
        t.locator('[data-r=chk]').uncheck(); t.locator('[data-r=dest]').select_option('skip')
        pg.click('[data-pai-add]'); pg.wait_for_selector('[data-pai-result]'); pg.wait_for_timeout(500)
        check('result screen says what was added', 'Added 1 bill and 1 income item' in pg.inner_text('[data-pai-result]'), pg.inner_text('[data-pai-result]'))
        st = pg.evaluate("""()=>{const g=bills.find(b=>b.name==='Pool pass'),pc=paychecks.find(p=>p.name==='Dog walking income');
          let stored=null;try{for(const k of Object.keys(localStorage)){const v=localStorage.getItem(k);if(v&&v.includes('Pool pass')&&v.startsWith('['))stored=k}}catch(e){}
          return {g:g&&{amount:g.amount,due:g.due,recurring:g.recurring,recurrence:g.recurrence,category:g.category,color:g.color,id:typeof g.id,notify:g.notify,paidAmt:billPaidAmounts[g.id+'|'+g.due],ov:billOverrides[g.id+'|'+g.due]},pc:pc&&{amount:pc.amount,date:pc.date,frequency:pc.frequency,incomeType:pc.incomeType},n:bills.length,np:paychecks.length,stored,
            onlyOnce:bills.filter(b=>/Rent/.test(b.name)).length,hasOld:bills.some(b=>b.name==='Old loan'||b.name==='Total'),pcStored:(localStorage.getItem('payAviator_paychecks_v1')||'').includes('Dog walking income')}}""")
        check('bill added through the normal bills list with the edited values', st['g'] and st['g']['amount'] == 29.99 and st['g']['due'] == dd(11).isoformat() and st['g']['recurring'] and st['g']['recurrence'] == 'monthly' and st['g']['category'] == 'Subscriptions' and st['n'] == n_bills0 + 1, str(st))
        check('paid=Yes recorded as a paid occurrence like the Payment dialog does', st['g'] and st['g']['paidAmt'] == 29.99 and st['g']['ov'] == {'paid': True}, str(st['g']))
        check('income added to the app paychecks (weekly, fixed amount)', st['pc'] and st['pc']['amount'] == 200 and st['pc']['date'] == dd(12).isoformat() and st['pc']['frequency'] == 'weekly' and st['pc']['incomeType'] == 'salary' and st['np'] == n_checks0 + 1, str(st))
        check('bills are saved in the watched local storage (what cloud sync diffs), paychecks too', st['stored'] is not None and st['pcStored'], str(st['stored']))
        check('duplicate / unticked / skipped rows were NOT added', st['onlyOnce'] == 1 and not st['hasOld'])
        check('still nothing sent anywhere by the import itself (no non-GET to other hosts)', not any('localhost' not in u for u in posts), str(posts))
        pg.click('[data-pai-done]'); pg.wait_for_timeout(900)
        check('Done returns to the Bills tab (the imported bill is paid, so it sits under Show paid bills)', pg.locator('#mb119Bills').is_visible() and 'Import from spreadsheet' in pg.locator('#pa401BillsActions').inner_text())
        pg.reload(); pg.wait_for_timeout(3000)
        check('imported bill survives an app restart (reload)', pg.evaluate("bills.some(b=>b.name==='Pool pass')") and pg.evaluate("paychecks.some(p=>p.name==='Dog walking income')"))
        pg.evaluate("document.querySelectorAll('dialog[open]').forEach(d=>d.close())")

        print('[mapping, sheets, huge]')
        nav('bills'); pg.click('[data-pai-open=bills]'); pg.wait_for_selector('[data-pai-file]'); pg.set_input_files('[data-pai-file]', os.path.join(FX, 'ambiguous.xlsx')); pg.wait_for_selector('[data-pai-map=name]')
        check('ambiguous file asks for column mapping first', pg.locator('[data-pai-map=amount]').count() == 1)
        pg.select_option('[data-pai-map=name]', ''); check('Continue disabled until name column chosen', pg.is_disabled('[data-pai-map-continue]'))
        pg.select_option('[data-pai-map=name]', '0'); pg.select_option('[data-pai-map=amount]', '2'); pg.click('[data-pai-map-continue]'); pg.wait_for_selector('.pai-row')
        check('mapping applied; undated rows flagged and unticked', pg.locator('.pai-row input[data-r=amount]').first.input_value() == '85' and pg.locator('.pai-row [data-needs]').count() == 2)
        pg.evaluate("document.getElementById('paImportDlg').close()")
        pg.click('[data-pai-open=bills]'); pg.set_input_files('[data-pai-file]', os.path.join(FX, 'multi_sheet.xlsx')); pg.wait_for_selector('.pai-row')
        check('multi-sheet workbook shows a sheet picker (hidden sheet skipped)', pg.locator('[data-pai-sheet] option').count() == 2)
        pg.evaluate("document.getElementById('paImportDlg').close()")
        import time; t0 = time.time()
        pg.click('[data-pai-open=bills]'); pg.set_input_files('[data-pai-file]', os.path.join(FX, 'huge_6000_rows.xlsx')); pg.wait_for_selector('.pai-row', timeout=30000); el = time.time() - t0
        check(f'6000-row file opens in {el:.1f}s, 5000 rows max with a notice, rendered in pages', 'first 5,000 rows' in pg.inner_text('#paImportDlg') and pg.locator('.pai-row').count() == 150 and pg.locator('[data-pai-more]').is_visible() and el < 15, str(el))
        pg.click('[data-pai-more]'); check('"Show more" adds the next page', pg.locator('.pai-row').count() == 300)
        pg.click('[data-pai-none]'); check('Select none disables Add', pg.is_disabled('[data-pai-add]'))
        over = pg.evaluate("(()=>{const f=document.querySelector('#paImportDlg .form');return f.scrollWidth>f.clientWidth+1||document.documentElement.scrollWidth>innerWidth+1})()")
        check('no horizontal overflow at 390px', not over)
        pg.evaluate("document.getElementById('paImportDlg').close()")
        errs = [l for l in logs if 'alert' not in l]
        check('no page errors', not errs, str(errs[:3])); check('no alert() popups', not [l for l in logs if l.startswith('alert')], str(logs[:3]))
        b.close()
run()
print(f'\n{passes} checks passed, {len(fails)} failed')
if fails: print('\n'.join(fails)); sys.exit(1)
