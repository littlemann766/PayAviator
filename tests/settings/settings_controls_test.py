#!/usr/bin/env python3
"""4.2.6 regression: every control that the 4.2.2 Settings dialogs had (App Colors incl. swatches + Hue/Saturation/Lightness wheels,
Calendar & Defaults, Bills & Reminders, Backup & App) must exist at runtime in the Android WebView simulation in IDLE, BUSY (page mutates
the DOM every 20ms) and THROTTLED (busy + CPU 6x slower) modes, and busy/throttled must equal idle.
Usage: python3 tests/settings/settings_controls_test.py [shotdir]"""
import os, sys, json
from collections import Counter
from playwright.sync_api import sync_playwright
ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..'))
OUT = sys.argv[1] if len(sys.argv) > 1 else '/workspace/shots/settings-fix'; os.makedirs(OUT, exist_ok=True)
html = open(os.path.join(ROOT, 'app/src/main/assets/index.html'), 'rb').read()
base = json.load(open(os.path.join(ROOT, 'tests/settings/baseline-4.2.2.json')))['dialogs']
BR = "(function(){window.AndroidBridge={getAppVersionName:()=>'4',getAppVersionCode:()=>1,isAppLockEnabled:()=>true,isDeviceSecure:()=>true,areRealAccountsConnected:()=>false,setRealAccountsConnected:()=>{},setAppLockEnabled:()=>{},lockNow:()=>{},loadBillsSnapshot:()=>'',saveBillsSnapshot:()=>true,notificationsAllowed:()=>true,takeFiredAlerts:()=>'[]',takeLaunchAlert:()=>'',getSecureDeviceId:()=>'x',authGetState:()=>'{}',scheduleNotifications:()=>{},showToast:()=>{},openSupportEmail:()=>true};})();"
UA = 'Mozilla/5.0 (Linux; Android 14; Pixel 8 Build/AP1A; wv) AppleWebKit/537.36 (KHTML, like Gecko) Version/4.0 Chrome/124.0.0.0 Mobile Safari/537.36'
O = 'https://appassets.androidplatform.net/assets/'
JS = """(()=>{const p=document.getElementById('mb123SettingsPanel');if(!p)return [];
return [...p.querySelectorAll('h1,h2,h3,h4,button,input,select,textarea,a,label,.settings-row,[data-pai-open],canvas,[role=slider]')].map(e=>{
 const t=e.tagName.toLowerCase();let id=e.id||e.getAttribute('data-pai-open')&&('pai:'+e.getAttribute('data-pai-open'))||e.getAttribute('data-mb123-settings')||'';
 return t+(e.type&&t=='input'?'['+e.type+']':'')+'#'+id+'|'+(t=='input'||t=='select'||t=='textarea'?(e.getAttribute('aria-label')||e.name||(e.closest('label,.settings-row')||{}).textContent||'').trim().slice(0,40):e.textContent.trim().replace(/\\s+/g,' ').slice(0,40))})})()"""
fails = []
def check(n, c, x=''):
    print('  ok  ' if c else '  FAIL', n, '' if c else x)
    if not c: fails.append(n)
check('assets/index.html identical to root index.html', html == open(os.path.join(ROOT, 'index.html'), 'rb').read())
def run(mode):
    with sync_playwright() as p:
        b = p.chromium.launch(executable_path='/usr/bin/google-chrome' if os.path.exists('/usr/bin/google-chrome') else None, args=['--no-sandbox'])
        ctx = b.new_context(viewport={'width': 412, 'height': 880}, device_scale_factor=2, is_mobile=True, has_touch=True, user_agent=UA)
        ctx.add_init_script(BR)
        def h(route):
            u = route.request.url
            if u == O + 'index.html': route.fulfill(status=200, body=html, content_type='text/html')
            elif u.startswith(O): route.fulfill(status=404, body='')
            else: route.abort()
        ctx.route('**/*', h)
        pg = ctx.new_page(); errs = []
        pg.on('pageerror', lambda e: errs.append(str(e)[:160]))
        if mode == 'throttled': ctx.new_cdp_session(pg).send('Emulation.setCPUThrottlingRate', {'rate': 6})
        pg.goto(O + 'index.html'); pg.wait_for_timeout(9000 if mode == 'throttled' else 3500)
        pg.evaluate("document.querySelectorAll('dialog[open]').forEach(d=>d.close())")
        if mode == 'stale':   # older code re-pointed the buttons at a partial dialog after our wire() timers: the safety net must still show the real dialog
            pg.evaluate("document.querySelector('.mb119-nav[data-view=\"settings\"]').click()"); pg.wait_for_timeout(800)
            pg.evaluate("['calendar','reminders','backup'].forEach(function(n){var b=document.querySelector('[data-mb123-settings='+n+']');b.onclick=function(e){e.preventDefault();var p=document.getElementById('mb123SettingsPanel');p.innerHTML='<h3>'+b.textContent+'</h3><div class=\"settings-section\"><h3>Partial</h3></div>';mb2034OpenSettingsShell()}})")
        if mode != 'idle':
            pg.evaluate("(function(){var d=document.createElement('div');d.id='pa-noise';d.style.display='none';document.body.appendChild(d);var n=0;setInterval(function(){d.textContent=String(n++)},20)})()")
        res = {}
        for sec in ['appearance', 'calendar', 'reminders', 'backup']:
            # open each dialog twice: the second open must be identical to the first
            for i in range(2):
                pg.evaluate("document.querySelector('.mb119-nav[data-view=\"settings\"]').click()"); pg.wait_for_timeout(1000)
                pg.evaluate("document.querySelector('[data-mb123-settings=%s]').click()" % sec); pg.wait_for_timeout(3500 if mode == 'throttled' else 2600 if mode == 'stale' else 1800)
                res[sec if i == 0 else sec + '#2'] = pg.evaluate(JS)
                if i == 0: pg.screenshot(path='%s/%s-%s.png' % (OUT, mode, sec))
                if i == 0 and sec == 'appearance':
                    pg.evaluate("document.querySelector('#mb137Navy').closest('.mb137-color-row').querySelector('label').click()"); pg.wait_for_timeout(500)
                    pg.evaluate("var d=document.querySelector('#mb137NavyCustom414');d&&(d.open=true)"); pg.wait_for_timeout(500)
                    pg.evaluate("document.querySelector('#mb137Navy').closest('.mb137-color-row').scrollIntoView()"); pg.wait_for_timeout(300)
                    pg.screenshot(path='%s/%s-appearance-wheel.png' % (OUT, mode))
                pg.evaluate("var x=document.querySelector('#mb2034SettingsClose');x&&x.click()"); pg.wait_for_timeout(400)
        res['_errs'] = errs; b.close(); return res
MODES = os.environ.get('MODES', 'idle,busy,throttled,stale').split(',')
runs = {m: run(m) for m in MODES}
json.dump(runs, open(os.path.join(OUT, 'last-run.json'), 'w'))
for m, r in runs.items():
    check('[%s] no page errors' % m, not r['_errs'], r['_errs'])
    for sec, want in base.items():
        have = Counter(r[sec]); need = Counter(want)
        miss = [k for k in need if have[k] < need[k]]
        check('[%s] %s: all %d baseline controls present' % (m, sec, len(want)), not miss, miss[:10])
    check('[%s] App Colors has 5 color rows with swatches + Hue/Saturation/Lightness wheels' % m,
          sum(1 for k in r['appearance'] if k.startswith('input[range]#|Hue')) == 5 and sum(1 for k in r['appearance'] if k.startswith('input[range]#|Lightness')) == 5)
for m in [x for x in MODES if x != 'idle']:
    for sec in base:
        check('[%s] %s identical to idle' % (m, sec), (not (Counter(runs['idle'][sec]) - Counter(runs[m][sec]))) and (m=='stale' or Counter(runs[m][sec]) == Counter(runs['idle'][sec])), (set(runs['idle'][sec]) ^ set(runs[m][sec])))
for m in runs:
    for sec in base:
        check('[%s] %s: second open identical to first' % (m, sec), Counter(runs[m][sec]) == Counter(runs[m][sec + '#2']))
print('FAILED: %s' % fails if fails else 'ALL PASSED'); sys.exit(1 if fails else 0)
