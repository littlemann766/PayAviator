#!/usr/bin/env python3
"""4.2.1 Home header buttons: tap 💡 (tip), 🔔 (Alerts + unread count), ? (help); also with a stripped handler and an invisible overlay on top."""
import sys,json
from playwright.sync_api import sync_playwright
URL=sys.argv[1] if len(sys.argv)>1 else 'http://localhost:8842/index.html'; SH=sys.argv[2] if len(sys.argv)>2 else None
ok=True
def check(n,c,d=''):
    global ok; print(('PASS ' if c else 'FAIL ')+n+(' '+str(d) if d else '')); ok=ok and bool(c)
INIT="window.AndroidBridge={scheduleNotifications:()=>{},requestNotificationPermission:()=>{},takeFiredAlerts:()=>'[]',takeLaunchAlert:()=>''};"
CLEAN="document.querySelectorAll('dialog[open]').forEach(d=>d.close());document.getElementById('pa412Back')?.click();document.getElementById('pp925TipPopup')?.classList.remove('pp-show');document.querySelector('.mb119-nav[data-view=home]').click()"
def tap(pg,sel):
    bb=pg.locator(sel).bounding_box(); pg.touchscreen.tap(bb['x']+bb['width']/2,bb['y']+bb['height']/2); pg.wait_for_timeout(600)
STATE={'tip':"document.getElementById('pp925TipPopup')?.classList.contains('pp-show')",'alerts':"document.getElementById('pa412Alerts')?.classList.contains('show')",'help':"!!document.getElementById('ppHelpDlg')?.open"}
with sync_playwright() as p:
    b=p.chromium.launch(executable_path='/usr/bin/google-chrome',args=['--no-sandbox'])
    for vw,vh in [(390,844),(360,640)]:
        pg=b.new_page(viewport={'width':vw,'height':vh},has_touch=True,is_mobile=True,device_scale_factor=2); errs=[]
        pg.on('pageerror',lambda e:errs.append(str(e)))
        pg.add_init_script(INIT); pg.goto(URL)
        pg.evaluate("localStorage.clear();localStorage.setItem('payAviator_onboarding_v1_done','1');localStorage.setItem('payaviator_tip_popup_seen_v1','true');localStorage.setItem('payAviator_security_tip_launch_count_v1','99');localStorage.setItem('payaviator_onboarding_choice_v1','guest')")
        pg.reload(); pg.wait_for_timeout(3500)
        pg.evaluate("PayAviatorAlerts.add({id:'t1',type:'bill',title:'Rent due tomorrow',text:'Rent is due',ts:Date.now(),open:'bills'});PayAviatorAlerts.add({id:'t2',type:'bill',title:'Electric',text:'Electric due',ts:Date.now()-1000,open:'bills'})")
        pg.evaluate("document.querySelector('.mb119-nav[data-view=home]').click()"); pg.wait_for_timeout(300)
        # 1 plain taps
        for name,sel,key in [('bell','#pa412Bell','alerts'),('help ?','#mb119Home > .pp-help-btn','help')]:
            tap(pg,sel); check(f'{vw}: tapping {name} opens its screen',pg.evaluate(STATE[key]))
            if vw==390: pg.screenshot(path=(SH or 'shots/header-buttons-421')+'/'+{'alerts':'bell','help':'help'}[key]+f'-{vw}.png')
            if key=='help':
                check(f'{vw}: help screen is combined Help & Tips (tip card + sections)',pg.evaluate("!!document.querySelector('#ppHelpBody .pa421-tipcard') && document.querySelectorAll('#ppHelpBody .pp-help-section').length>0 && /Help & Tips/.test(document.getElementById('ppHelpTitle').textContent)"))
                if vw==390: pg.screenshot(path='shots/nav-width/help-tips-390.png')
            if key=='alerts':
                check(f'{vw}: Alerts screen lists the alerts',pg.evaluate("document.querySelectorAll('.pa412-item').length")>=2)
            pg.evaluate(CLEAN); pg.wait_for_timeout(300)
        check(f'{vw}: no floating lightbulb and no header lightbulb',pg.evaluate("[...document.querySelectorAll('#pp925TipLauncher,#pa412HomeTip')].every(e=>getComputedStyle(e).display==='none')"))
        check(f'{vw}: bell badge shows unread count',pg.evaluate("document.getElementById('pa412BellBadge').textContent")=='2' and not pg.evaluate("document.getElementById('pa412BellBadge').hidden"))
        # 2 button's own handlers stripped + invisible overlay on top of the header (worst case): delegated handler still opens each
        pg.evaluate("['pa412Bell'].forEach(i=>{document.getElementById(i).onclick=null});document.querySelector('#mb119Home > .pp-help-btn').onclick=null;const o=document.createElement('div');o.id='ovl';o.style.cssText='position:fixed;left:0;top:0;width:100%;height:90px;z-index:2147483000;background:transparent';document.body.appendChild(o)")
        for name,sel,key in [('bell','#pa412Bell','alerts'),('help ?','#mb119Home > .pp-help-btn','help')]:
            tap(pg,sel); check(f'{vw}: {name} still opens with stripped handler + overlay',pg.evaluate(STATE[key]))
            pg.evaluate(CLEAN); pg.wait_for_timeout(300)
        check(f'{vw}: exactly one screen per tap (no double open)',not pg.evaluate(STATE['tip']) and not pg.evaluate(STATE['alerts']))
        check(f'{vw}: no JS errors',not errs,errs[:2])
        pg.close()
    b.close()
print('ALL PASS' if ok else 'SOME FAIL'); sys.exit(0 if ok else 1)
