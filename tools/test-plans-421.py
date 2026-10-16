#!/usr/bin/env python3
"""4.2.1 plans: Aviator Elite (testers, backend plan/source 'comp') and Founder (owner, backend tier 'founder'),
mocked Android bridge + /api/billing/status. Checks badge by the heading + plan card, copy, no bank limit, Free/Plus unchanged.
Usage: test-plans-421.py http://localhost:PORT/index.html [shotdir]"""
import sys, json, os
from playwright.sync_api import sync_playwright
URL=sys.argv[1]; SHOTS=sys.argv[2] if len(sys.argv)>2 else None
MOCK="""(()=>{
const st=window.__mock={routes:{}};
const deliver=(fn,obj)=>setTimeout(()=>window[fn]&&window[fn](JSON.stringify(obj)),20);
const state=()=>({available:true,googleAvailable:false,signedIn:true,uid:'u1',email:'alex@example.com',emailVerified:true});
window.AndroidBridge={authGetState:()=>JSON.stringify(state()),
 apiRequest:(id,m,p,b)=>{const r=st.routes[p.split('?')[0]]||{status:200,body:{}};deliver('PayAviatorNativeApiResult',{requestId:id,status:r.status,body:JSON.stringify(r.body)})},
 billingGetPurchases:()=>'[]'};
})()"""
BASE="""(()=>{localStorage.clear();localStorage.setItem('payAviator_onboarding_v1_done','1');localStorage.setItem('payaviator_tip_popup_seen_v1','1');localStorage.setItem('payAviator_security_tip_launch_count_v1','99');localStorage.setItem('payaviator_onboarding_choice_v1','signin')})()"""
ok=True
def check(n,c,d=''):
    global ok; print(('PASS ' if c else 'FAIL ')+n+(' '+str(d) if d else '')); ok=ok and bool(c)
CASES=[('free',{'plan':'free','source':None,'linkedBanks':1,'limit':1},None),
 ('plus',{'plan':'premium','source':'play','linkedBanks':2,'limit':None},None),
 ('elite',{'plan':'comp','source':'comp','linkedBanks':3,'limit':None},'elite'),
 ('founder',{'plan':'comp','source':'comp','tier':'founder','linkedBanks':3,'limit':None},'founder')]
with sync_playwright() as p:
    b=p.chromium.launch(executable_path='/usr/bin/google-chrome',args=['--no-sandbox'])
    for vw,vh in [(390,844),(360,640)]:
        for name,body,kind in CASES:
            c=b.new_context(viewport={'width':vw,'height':vh},has_touch=True,is_mobile=True)
            c.route(lambda u:not u.startswith('http://localhost'),lambda r:r.abort())
            pg=c.new_page(); errs=[]; pg.on('pageerror',lambda e:errs.append(str(e)))
            pg.goto(URL); pg.evaluate(BASE)
            c.add_init_script(MOCK+";window.__mock.routes['/api/billing/status']={status:200,body:%s};"%json.dumps(body))
            pg.reload(); pg.wait_for_timeout(2500)
            pg.evaluate("window.PayAviatorAccountGate.refreshStatus()"); pg.wait_for_timeout(500)
            pg.evaluate("window.openPayAviatorConnectedAccounts920()"); pg.wait_for_timeout(1000)
            tag=f'{vw} {name}'
            hb=pg.locator('#pp920AccountsModal .pp920-head h2 [data-pa421-badge]'); cb=pg.locator('#pp920AccountsBody [data-pa421-plan] [data-pa421-badge]')
            if kind is None:
                check(f'{tag}: no badge, no special plan card',hb.count()==0 and pg.locator('[data-pa421-plan]').count()==0)
            else:
                t={'elite':('Aviator Elite - Complimentary','Thank you for helping us test PayAviator.','Unlimited while testing','pa421-seal'),'founder':('Founder - Free forever','Every feature included.','No limit','pa421-pill')}[kind]
                check(f'{tag}: badge beside the heading ({t[3]}) and on plan card',hb.count()==1 and cb.count()==1 and hb.get_attribute('class').find(t[3])>=0 and cb.get_attribute('class').find(t[3])>=0)
                check(f'{tag}: plan title/message/banks',pg.inner_text('[data-pa421-title]')==t[0] and t[1] in pg.inner_text('[data-pa421-plan]') and pg.inner_text('[data-pa421-banks]')==t[2])
                check(f'{tag}: full access, no bank limit',pg.evaluate("window.PayAviatorAccountGate.isPaid()") is True and pg.evaluate("window.PayAviatorAccountGate.bankLimit()") is None)
                other='founder' if kind=='elite' else 'elite'
                check(f'{tag}: only its own plan shown',pg.locator(f'[data-pa421-badge={other}]').count()==0)
            if SHOTS and kind: pg.screenshot(path=os.path.join(SHOTS,f'app_{name}_{vw}x{vh}.png'))
            check(f'{tag}: no page errors',not errs,errs[:2])
            c.close()
        # public pricing / upgrade screen never lists Founder or Elite
    html=open(os.path.join(os.path.dirname(__file__),'..','index.html')).read()
    import re
    up=re.search(r'data-onb="upgrade".*?</section>',html,re.S).group(0)
    check('upgrade/pricing screen has no Founder or Aviator Elite',('Founder' not in up) and ('Aviator Elite' not in up))
    check('no email hardcoded in plan code',re.search(r'PLAN_INFO=\{.*?\};',html,re.S).group(0).count('@')==0)
    b.close()
print('ALL PASS' if ok else 'SOME FAILED'); sys.exit(0 if ok else 1)
