#!/usr/bin/env python3
"""4.2.6 regression: load the APK's real index.html the way Android WebView does (appassets origin, wv user agent, AndroidBridge JS
interface present) and check the spreadsheet import entry points exist, even when the page is mutating constantly.
Usage: python3 tests/import/webview_env_test.py [shotdir]"""
import os, sys, re
from playwright.sync_api import sync_playwright
ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..'))
OUT = sys.argv[1] if len(sys.argv) > 1 else '/workspace/shots/import-check2'; os.makedirs(OUT, exist_ok=True)
html = open(os.path.join(ROOT, 'app/src/main/assets/index.html'), 'rb').read()
ver = open(os.path.join(ROOT, 'VERSION.txt')).read().strip()
BR = "(function(){window.AndroidBridge={getAppVersionName:()=>'%s',getAppVersionCode:()=>1,isAppLockEnabled:()=>true,isDeviceSecure:()=>true,areRealAccountsConnected:()=>false,setRealAccountsConnected:()=>{},setAppLockEnabled:()=>{},lockNow:()=>{},loadBillsSnapshot:()=>'',saveBillsSnapshot:()=>true,notificationsAllowed:()=>true,takeFiredAlerts:()=>'[]',takeLaunchAlert:()=>'',getSecureDeviceId:()=>'x',authGetState:()=>'{}',scheduleNotifications:()=>{},showToast:()=>{},openSupportEmail:()=>true};})();" % ver
UA = 'Mozilla/5.0 (Linux; Android 14; Pixel 8 Build/AP1A; wv) AppleWebKit/537.36 (KHTML, like Gecko) Version/4.0 Chrome/124.0.0.0 Mobile Safari/537.36'
O = 'https://appassets.androidplatform.net/assets/'
fails = []
def check(n, c, x=''):
    print('  ok  ' if c else '  FAIL', n, '' if c else x)
    if not c: fails.append(n)
check('assets/index.html identical to root index.html', html == open(os.path.join(ROOT, 'index.html'), 'rb').read())
check("BUNDLED_VERSION matches VERSION.txt", ("const BUNDLED_VERSION='%s';" % ver).encode() in html)
def run(busy):
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
        pg.goto(O + 'index.html'); pg.wait_for_timeout(3500)
        check('[%s] WebView env: bridge + wv UA + appassets origin' % busy, pg.evaluate("!!window.AndroidBridge && /wv/.test(navigator.userAgent) && location.origin==='https://appassets.androidplatform.net'"))
        pg.evaluate("document.querySelectorAll('dialog[open]').forEach(d=>d.close())")
        if busy == 'busy':   # a page that mutates every 20ms must not starve the import placement
            pg.evaluate("(function(){var d=document.createElement('div');d.id='pa-noise';d.style.display='none';document.body.appendChild(d);var n=0;setInterval(function(){d.textContent=String(n++)},20)})()")
        nav = lambda v: (pg.evaluate("document.querySelector('.mb119-nav[data-view=\"%s\"]').click()" % v), pg.wait_for_timeout(900))
        nav('bills'); pg.wait_for_timeout(1500)
        check('[%s] Bills tab has Import from spreadsheet' % busy, pg.evaluate("!!document.querySelector('[data-pai-open=bills]')"))
        pg.screenshot(path='%s/wv-%s-bills.png' % (OUT, busy))
        nav('settings')
        for i in range(2):
            pg.evaluate("document.querySelector('[data-mb123-settings=backup]').click()"); pg.wait_for_timeout(1600)
            heads = pg.evaluate("[...document.querySelectorAll('#mb123SettingsPanel h3')].map(h=>h.textContent.trim())")
            check('[%s] Backup & App (open #%d) lists Import from spreadsheet: %s' % (busy, i + 1, heads), 'Import from spreadsheet' in heads and 'Save & Backup' in heads)
            check('[%s] import button inside the visible panel is on screen' % busy, pg.evaluate("(function(){var b=document.querySelector('#mb123SettingsPanel [data-pai-open=settings]');if(!b)return false;var r=b.getBoundingClientRect();return r.width>50&&r.height>20})()"))
            if i == 0:
                pg.evaluate("document.querySelector('#mb123SettingsPanel [data-pai-open=settings]').scrollIntoView()"); pg.wait_for_timeout(300)
                pg.screenshot(path='%s/wv-%s-backup-app.png' % (OUT, busy))
                txt = pg.evaluate("(document.querySelector('#mb123SettingsPanel [data-web-layer]')||{}).textContent||''")
                check('[%s] version row shows Screens %s' % (busy, ver), ('Screens ' + ver) in txt, txt)
                pg.evaluate("document.querySelector('#mb123SettingsPanel [data-pai-open=settings]').click()"); pg.wait_for_timeout(800)
                check('[%s] tapping it opens the import dialog' % busy, pg.evaluate("!!document.querySelector('#paImportDlg[open], #paImportDlg.show') || (document.getElementById('paImportDlg')||{}).open===true"))
                pg.screenshot(path='%s/wv-%s-import-dialog.png' % (OUT, busy))
                pg.evaluate("(document.querySelector('#paImportDlg [data-pai-close],#paImportDlg .x')||{click(){}}).click();var d=document.getElementById('paImportDlg');if(d&&d.open)d.close()"); pg.wait_for_timeout(500)
                pg.evaluate("document.querySelector('#mb123SettingsPanel .x, #mb123SettingsPanel button.primary, #mb123SettingsPanel [id*=Done]').click()"); pg.wait_for_timeout(600)
                nav('settings')
        check('[%s] no page errors' % busy, not errs, errs)
        b.close()
run('idle'); run('busy')
css = open(os.path.join(ROOT, 'index.html'), encoding='utf-8').read()
check('hidden Show-more button stays hidden (CSS rule)', '[data-pai-more][hidden]{display:none!important}' in css)
check('no negative Show-more text', "if (left > 0) more.textContent" in css)
print('FAILED: %s' % fails if fails else 'ALL PASSED'); sys.exit(1 if fails else 0)
