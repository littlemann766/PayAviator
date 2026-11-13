#!/usr/bin/env python3
"""Restore queries Play, then POST /api/billing/google-play/verify. No purchase is started.
Usage: python3 tools/test-restore-purchase.py http://127.0.0.1:PORT/index.html
"""
import json
import sys
from playwright.sync_api import sync_playwright

URL = sys.argv[1]
MOCK = r"""(()=>{
const st=window.__mock={signedIn:true,uid:'u1',calls:[],routes:{},query:{ok:true,code:'',purchases:[]}};
const deliver=(fn,obj)=>setTimeout(()=>window[fn]&&window[fn](JSON.stringify(obj)),15);
const state=()=>({available:true,googleAvailable:false,signedIn:st.signedIn,uid:st.signedIn?st.uid:'',email:'a@b.co',emailVerified:true,provider:'password'});
window.AndroidBridge={
 authGetState:()=>JSON.stringify(state()),
 apiRequest:(id,m,p,b)=>{st.calls.push([m,p,b||'']);const path=String(p).split('?')[0];const r=st.routes[path]||{status:500,body:{error:'missing',code:'MISSING'}};deliver('PayAviatorNativeApiResult',{requestId:id,status:r.status,body:JSON.stringify(r.body)})},
 billingQueryPurchases:(id)=>{st.calls.push(['NATIVE','billingQueryPurchases']);const q=st.query;deliver('PayAviatorBillingPurchasesResult',{requestId:id,ok:!!q.ok,code:q.code||'',purchases:q.purchases||[]})},
 billingGetPurchases:()=>'[]',
 billingPurchase:()=>{st.calls.push(['NATIVE','billingPurchase'])}
};
})()"""
BASE = """(()=>{localStorage.clear();localStorage.setItem('payAviator_onboarding_v1_done','1');localStorage.setItem('payaviator_tip_popup_seen_v1','1');localStorage.setItem('payAviator_security_tip_launch_count_v1','99');localStorage.setItem('payaviator_onboarding_choice_v1','account')})()"""
ok = True

def check(name, cond, detail=''):
    global ok
    print(('PASS ' if cond else 'FAIL ') + name + ((' ' + str(detail)) if detail else ''))
    ok = ok and bool(cond)

def run(pg):
    pg.evaluate('__mock.calls=[]')
    return pg.evaluate('window.PayAviatorRestorePurchase.run()')

def bought(pg):
    return any(c[0]=='NATIVE' and c[1]=='billingPurchase' for c in pg.evaluate('__mock.calls'))

def verifies(pg):
    return [c for c in pg.evaluate('__mock.calls') if c[0]=='POST' and c[1]=='/api/billing/google-play/verify']

with sync_playwright() as p:
    browser = p.chromium.launch(executable_path='/usr/bin/google-chrome', args=['--no-sandbox'])
    ctx = browser.new_context(viewport={'width': 390, 'height': 844})
    ctx.route(lambda u: not u.startswith('http://127.0.0.1') and not u.startswith('http://localhost'), lambda r: r.abort())
    pg = ctx.new_page()
    errs = []
    pg.on('pageerror', lambda e: errs.append(str(e)))
    pg.goto(URL)
    pg.evaluate(BASE)
    ctx.add_init_script(MOCK)
    pg.reload()
    pg.wait_for_timeout(2500)
    check('no page errors', not errs, errs)
    check('purchases stay off', pg.evaluate('window.PayAviatorBillingLive()') is False)
    css = pg.evaluate("document.getElementById('pa-410-accounts-css')?.textContent||''")
    check('coming-soon style does not hide Restore', '[data-onb-act="restore"]{display:none' not in css, css[:180])

    pg.evaluate("""__mock.query={ok:true,code:'',purchases:[{productId:'plus_monthly',purchaseToken:'token-a',purchaseState:1}]}""")
    pg.evaluate("""__mock.routes['/api/billing/google-play/verify']={status:200,body:{plan:'premium',source:'play',subscriptionState:'SUBSCRIPTION_STATE_ACTIVE',expiresAt:'2027-01-01T00:00:00.000Z'}}""")
    r = run(pg)
    body = json.loads(verifies(pg)[-1][2])
    check('active purchase is verified with its product and token', body=={'productId':'plus_monthly','purchaseToken':'token-a'}, body)
    check('active server result is eligible and does not buy', r['ok'] is True and r['outcome']=='eligible' and r['purchasesStarted'] is False and not bought(pg), r)
    check('active message names the server window', '2027-01-01' in r['message'] and 'No new purchase was started' in r['message'], r.get('message'))

    pg.evaluate("""__mock.routes['/api/billing/google-play/verify']={status:200,body:{plan:'premium',source:'play',subscriptionState:'SUBSCRIPTION_STATE_CANCELED',expiresAt:'2026-12-01T00:00:00.000Z'}}""")
    r = run(pg)
    check('canceled-but-eligible stays a server match', r['ok'] is True and r['subscriptionState']=='SUBSCRIPTION_STATE_CANCELED' and 'SUBSCRIPTION_STATE_CANCELED' in r['message'] and not bought(pg), r.get('message'))

    pg.evaluate("""__mock.routes['/api/billing/google-play/verify']={status:402,body:{error:'subscription_inactive',code:'SUBSCRIPTION_INACTIVE',plan:'free'}}""")
    r = run(pg)
    check('inactive purchase grants nothing', r['ok'] is False and r['outcome']=='inactive' and 'not active' in r['message'] and not bought(pg), r)

    pg.evaluate("""__mock.routes['/api/billing/google-play/verify']={status:409,body:{error:'purchase_in_use',code:'PURCHASE_IN_USE'}}""")
    r = run(pg)
    paths = [c[1] for c in pg.evaluate('__mock.calls') if c[0] in ('POST','GET')]
    check('409 is a conflict and does not buy or call another route', r['outcome']=='conflict' and r['ok'] is False and paths==['/api/billing/google-play/verify'] and not bought(pg), paths)
    check('409 says recovery is not available yet', 'not available yet' in r['message'] and 'not moved' in r['message'], r.get('message'))

    pg.evaluate("""__mock.routes['/api/billing/google-play/verify']={status:400,body:{error:'invalid_purchase',code:'INVALID_PURCHASE'}}""")
    r = run(pg)
    check('rejected purchase grants nothing', r['outcome']=='rejected' and r['ok'] is False and not bought(pg), r)

    pg.evaluate("""__mock.query={ok:true,code:'',purchases:[]}""")
    r = run(pg)
    check('no Play purchase is not success and does not claim Stripe', r['outcome']=='none' and r['ok'] is False and 'Stripe' in r['message'] and verifies(pg)==[] and not bought(pg), r.get('message'))

    pg.evaluate("""__mock.query={ok:true,code:'',purchases:[{productId:'plus_monthly',purchaseToken:'token-pending',purchaseState:2}]}""")
    r = run(pg)
    check('pending Play state is not sent to verify', r['outcome']=='none' and verifies(pg)==[], r)

    pg.evaluate("""__mock.query={ok:false,code:'BILLING_UNAVAILABLE',purchases:[]}""")
    r = run(pg)
    check('Play query failure grants nothing', r['ok'] is False and r['outcome']=='BILLING_UNAVAILABLE' and not bought(pg), r)

    pg.evaluate("window.openPayAviatorConnectedAccounts920()")
    pg.wait_for_timeout(300)
    pg.evaluate("document.querySelector('#pp920AccountsBody [data-ppauth-delete]').click()")
    pg.wait_for_timeout(200)
    copy = pg.evaluate("document.querySelector('#ppConfirm902 .pp902-confirm-copy')?.textContent||''")
    check('delete still says billing is not cancelled', 'does not cancel Google Play or Stripe billing' in copy, copy)
    check('no page errors at end', not errs, errs)
    browser.close()

print('RESTORE ' + ('PASS' if ok else 'FAIL'))
sys.exit(0 if ok else 1)
