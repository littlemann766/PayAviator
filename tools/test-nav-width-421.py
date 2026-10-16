#!/usr/bin/env python3
"""4.2.1b: bottom nav exactly screen width, equal tabs, no horizontal page scroll on any screen/width."""
import sys
from playwright.sync_api import sync_playwright
URL=sys.argv[1] if len(sys.argv)>1 else 'http://localhost:8842/index.html'; SH=sys.argv[2] if len(sys.argv)>2 else None
ok=True
def check(n,c,d=''):
    global ok; print(('PASS ' if c else 'FAIL ')+n+(' '+str(d) if d else '')); ok=ok and bool(c)
INIT="window.AndroidBridge={scheduleNotifications:()=>{},requestNotificationPermission:()=>{},takeFiredAlerts:()=>'[]',takeLaunchAlert:()=>''};"
VIEWS=['home','calendar','bills','income','budget','settings']
M="""()=>{const d=document.documentElement,n=document.getElementById('mb119BottomNav'),r=n.getBoundingClientRect();
const t=[...n.children].map(c=>c.getBoundingClientRect());
return {sw:d.scrollWidth,cw:d.clientWidth,bsw:document.body.scrollWidth,l:r.left,r:r.right,w:r.width,tabs:t.length,tw:t.map(x=>Math.round(x.width*10)/10),tl:t[0].left,tr:t[t.length-1].right,iw:innerWidth}}"""
with sync_playwright() as p:
    b=p.chromium.launch(executable_path='/usr/bin/google-chrome',args=['--no-sandbox'])
    for vw in [320,360,390,412,430,768]:
        pg=b.new_page(viewport={'width':vw,'height':800},has_touch=True,is_mobile=True,device_scale_factor=2)
        pg.add_init_script(INIT); pg.goto(URL)
        pg.evaluate("localStorage.clear();localStorage.setItem('payAviator_onboarding_v1_done','1');localStorage.setItem('payaviator_tip_popup_seen_v1','true');localStorage.setItem('payAviator_security_tip_launch_count_v1','99');localStorage.setItem('payaviator_onboarding_choice_v1','guest')")
        pg.reload(); pg.wait_for_timeout(3000)
        views=[v for v in VIEWS if pg.evaluate(f"!!document.querySelector('.mb119-nav[data-view={v}]')")]
        navs=pg.evaluate("[...document.querySelectorAll('#mb119BottomNav .mb119-nav')].map(x=>x.dataset.view)")
        for v in navs+['alerts']:
            if v=='alerts': pg.evaluate("document.getElementById('pa412Bell')?.click()")
            else: pg.evaluate(f"document.querySelector('.mb119-nav[data-view={v}]').click()")
            pg.wait_for_timeout(400); m=pg.evaluate(M)
            check(f'{vw} {v}: no horizontal scroll',m['sw']<=m['cw'] and m['bsw']<=m['iw'],(m['sw'],m['cw'],m['bsw']))
            if v!='alerts':
                check(f'{vw} {v}: nav == screen width',abs(m['l'])<=.5 and abs(m['r']-m['iw'])<=.5,(m['l'],m['r'],m['iw']))
                check(f'{vw} {v}: tabs equal',max(m['tw'])-min(m['tw'])<=1.0 and m['tl']<=8 and m['iw']-m['tr']<=8 and abs(m['tl']-(m['iw']-m['tr']))<=1,(m['tabs'],m['tw']))
            if v!='alerts':
                h=pg.evaluate("(v)=>{const view=document.getElementById({home:'mb119Home',calendar:'mb119Calendar',bills:'mb119Bills',spending:'mb119Spending',budget:'mb119Budget',settings:'mb119Settings'}[v]);const q=view.querySelector(':scope > .pp-help-btn'),t=view.querySelector('.mb119-title');const a=q.getBoundingClientRect(),tr=document.createRange();tr.selectNodeContents(t);const b=tr.getBoundingClientRect();const n=document.getElementById('mb119BottomNav').getBoundingClientRect();return {ql:a.left,qr:a.right,qt:a.top,qb:a.bottom,tr:b.right,tb:b.bottom,iw:innerWidth,navh:n.height,disp:getComputedStyle(q).display,fl:getComputedStyle(document.getElementById('pp925TipLauncher')||document.body).display}}",v)
                check(f'{vw} {v}: ? button inside screen, no title overlap, nav slim',h['qr']<=h['iw'] and h['ql']>=0 and h['tr']<=h['ql']+1 and h['navh']<=72 and (h['qb']-h['qt'])>=44,h)
            if v=='alerts': pg.evaluate("document.getElementById('pa412Back')?.click()")
            if SH and v=='home' and vw in(390,360): pg.screenshot(path=f'{SH}/nav-{vw}.png')
        if SH and vw in(390,360):
            pg.evaluate("document.querySelector('.mb119-nav[data-view=budget]').click()");pg.wait_for_timeout(300);pg.screenshot(path=f'{SH}/nav-budget-{vw}.png')
        pg.close()
    b.close()
print('ALL PASS' if ok else 'SOME FAIL'); sys.exit(0 if ok else 1)
