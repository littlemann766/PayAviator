#!/usr/bin/env python3
"""4.2.1b: Settings switches for the top-right bell and ? buttons (default on, remembered, hide on every tab, no empty gap)."""
import sys
from playwright.sync_api import sync_playwright
URL=sys.argv[1] if len(sys.argv)>1 else 'http://localhost:8842/index.html'; SH=sys.argv[2] if len(sys.argv)>2 else None
ok=True
def check(n,c,d=''):
    global ok; print(('PASS ' if c else 'FAIL ')+n+(' '+str(d) if d else '')); ok=ok and bool(c)
INIT="window.AndroidBridge={scheduleNotifications:()=>{},requestNotificationPermission:()=>{},takeFiredAlerts:()=>'[]',takeLaunchAlert:()=>''};"
VIS="""(id)=>{const e=document.querySelector(id);if(!e)return false;const r=e.getBoundingClientRect();return getComputedStyle(e).display!=='none'&&r.width>0}"""
def state(pg):
    out={}
    for v,i in [('home','mb119Home'),('calendar','mb119Calendar'),('bills','mb119Bills'),('spending','mb119Spending'),('budget','mb119Budget'),('settings','mb119Settings')]:
        pg.evaluate(f"document.querySelector('.mb119-nav[data-view={v}]').click()"); pg.wait_for_timeout(250)
        out[v]=(pg.evaluate(VIS,f'#{i} > .pp-help-btn'),pg.evaluate(VIS,'#pa412Bell') if v=='home' else None,
                pg.evaluate("(i)=>parseFloat(getComputedStyle(document.querySelector('#'+i+' .mb119-title')).paddingRight)",i))
    return out
with sync_playwright() as p:
    b=p.chromium.launch(executable_path='/usr/bin/google-chrome',args=['--no-sandbox'])
    pg=b.new_page(viewport={'width':390,'height':844},has_touch=True,is_mobile=True,device_scale_factor=2)
    pg.add_init_script(INIT); pg.goto(URL)
    pg.evaluate("localStorage.clear();localStorage.setItem('payAviator_onboarding_v1_done','1');localStorage.setItem('payaviator_tip_popup_seen_v1','true');localStorage.setItem('payAviator_security_tip_launch_count_v1','99');localStorage.setItem('payaviator_onboarding_choice_v1','guest')")
    pg.reload(); pg.wait_for_timeout(3000)
    pg.evaluate("document.querySelector('.mb119-nav[data-view=settings]').click()"); pg.wait_for_timeout(600)
    check('old Tips & Tricks switch/lightbulb wording removed',pg.evaluate("!/lightbulb|💡 tips button/i.test(document.getElementById('pp20516TipSettings').textContent) && !/Tips & Tricks/.test(document.getElementById('pp20516TipSettings').textContent)"))
    check('both switches exist and default ON',pg.evaluate("ppBellToggle.checked&&ppTipsToggle.checked"))
    if SH: pg.evaluate("document.getElementById('pp20516TipSettings').scrollIntoView({block:'center'})"); pg.wait_for_timeout(300); pg.screenshot(path=SH+'/settings-switches-390.png') if SH else None
    s=state(pg); check('default: ? on all 6 tabs and bell on Home',all(v[0] for v in s.values()) and s['home'][1],s)
    pg.evaluate("document.querySelector('.mb119-nav[data-view=settings]').click()"); pg.wait_for_timeout(300)
    pg.evaluate("ppBellToggle.click()"); pg.wait_for_timeout(200)
    s=state(pg); check('bell off: bell hidden, ? still on every tab',not s['home'][1] and all(v[0] for v in s.values()),s)
    check('bell off: Home title padding shrinks to one button',s['home'][2]<=60,s['home'][2])
    pg.reload(); pg.wait_for_timeout(3000)
    s=state(pg); check('bell-off remembered after reload',not s['home'][1] and all(v[0] for v in s.values()))
    pg.evaluate("document.querySelector('.mb119-nav[data-view=settings]').click()"); pg.wait_for_timeout(300)
    pg.evaluate("ppTipsToggle.click()"); pg.wait_for_timeout(200)
    s=state(pg); check('both off: no buttons anywhere and no empty gap (padding 0)',all(not v[0] for v in s.values()) and not s['home'][1] and all(v[2]==0 for v in s.values()),s)
    pg.evaluate("document.querySelector('.mb119-nav[data-view=settings]').click()"); pg.wait_for_timeout(300)
    pg.evaluate("ppBellToggle.click()"); pg.wait_for_timeout(200)
    s=state(pg); check('help off, bell on: bell on Home only, ? hidden everywhere',s['home'][1] and all(not v[0] for v in s.values()),s)
    pg.evaluate("document.querySelector('.mb119-nav[data-view=home]').click()"); pg.wait_for_timeout(300)
    check('bell right edge near screen edge',pg.evaluate("innerWidth-document.getElementById('pa412Bell').getBoundingClientRect().right")<=12)
    # notes + links in the pop-ups
    pg.evaluate("localStorage.setItem('payaviator_show_help_btn_v1','true');localStorage.setItem('payaviator_show_bell_btn_v1','true')"); pg.reload(); pg.wait_for_timeout(3000)
    pg.evaluate("document.querySelector('.mb119-nav[data-view=bills]').click()"); pg.wait_for_timeout(300)
    pg.evaluate("document.querySelector('#mb119Bills > .pp-help-btn').click()"); pg.wait_for_timeout(500)
    check('Help & Tips pop-up has the Settings note',pg.evaluate("/turn this button on or off in Settings/.test(document.getElementById('ppHelpBody').textContent)"))
    if SH: pg.screenshot(path=SH+'/help-tips-note-390.png')
    pg.evaluate("document.querySelector('#ppHelpBody .pa421-setnote button').click()"); pg.wait_for_timeout(900)
    check('link closes pop-up and opens Settings at the ? switch',pg.evaluate("!document.getElementById('ppHelpDlg').open && document.getElementById('mb119Settings').classList.contains('active')") and pg.evaluate("(()=>{const r=ppTipsToggle.closest('.settings-row').getBoundingClientRect();return r.top>=0&&r.bottom<=innerHeight})()"))
    pg.evaluate("document.querySelector('.mb119-nav[data-view=home]').click()"); pg.wait_for_timeout(300)
    pg.evaluate("PayAviatorAlerts.add({id:'n1',type:'bill',title:'Rent due',text:'x',ts:Date.now(),open:'bills'});document.getElementById('pa412Bell').click()"); pg.wait_for_timeout(600)
    check('Alerts pop-up has the Settings note',pg.evaluate("/turn this button on or off in Settings/.test(document.getElementById('pa412Body').textContent)"))
    if SH: pg.screenshot(path=SH+'/alerts-note-390.png')
    pg.evaluate("document.querySelector('#pa412Body .pa421-setnote button').click()"); pg.wait_for_timeout(900)
    check('link closes Alerts and opens Settings at the bell switch',pg.evaluate("!document.getElementById('pa412Alerts').classList.contains('show') && document.getElementById('mb119Settings').classList.contains('active')") and pg.evaluate("(()=>{const r=ppBellToggle.closest('.settings-row').getBoundingClientRect();return r.top>=0&&r.bottom<=innerHeight})()"))
    b.close()
print('ALL PASS' if ok else 'SOME FAIL'); sys.exit(0 if ok else 1)
