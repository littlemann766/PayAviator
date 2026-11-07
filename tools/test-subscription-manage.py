#!/usr/bin/env python3
"""Subscription manage/cancel routing. Mocked bridge only. BILLING_LIVE stays false.
Usage: python3 tools/test-subscription-manage.py http://127.0.0.1:PORT/index.html
"""
import sys
from playwright.sync_api import sync_playwright

URL = sys.argv[1]
MOCK = r"""(()=>{
const st=window.__mock={signedIn:true,uid:'u1',calls:[],routes:{}};
const deliver=(fn,obj)=>setTimeout(()=>window[fn]&&window[fn](JSON.stringify(obj)),15);
const state=()=>({available:true,googleAvailable:false,signedIn:st.signedIn,uid:st.signedIn?st.uid:'',email:'a@b.co',emailVerified:true,provider:'password'});
window.AndroidBridge={
 authGetState:()=>JSON.stringify(state()),
 apiRequest:(id,m,p,b)=>{st.calls.push([m,p,b||'']);const path=String(p).split('?')[0];const r=st.routes[path]||{status:500,body:{error:'missing route',code:'MISSING'}};deliver('PayAviatorNativeApiResult',{requestId:id,status:r.status,body:JSON.stringify(r.body)})},
 authDeleteAccount:(id)=>{st.calls.push(['NATIVE','authDeleteAccount']);deliver('PayAviatorAuthResult',{requestId:id,ok:false,code:'REQUIRES_RECENT_LOGIN',error:'sign in again',state:state()})},
 authSignOut:(id)=>{st.calls.push(['NATIVE','authSignOut']);deliver('PayAviatorAuthResult',{requestId:id,ok:true,state:state()})}
};
})()"""
BASE = """(()=>{localStorage.clear();localStorage.setItem('payAviator_onboarding_v1_done','1');localStorage.setItem('payaviator_tip_popup_seen_v1','1');localStorage.setItem('payAviator_security_tip_launch_count_v1','99');localStorage.setItem('payaviator_onboarding_choice_v1','account')})()"""
ok = True

def check(name, cond, detail=''):
    global ok
    print(('PASS ' if cond else 'FAIL ') + name + ((' ' + str(detail)) if detail else ''))
    ok = ok and bool(cond)

def status_of(pg):
    return pg.evaluate("document.getElementById('paSubStatus')?.textContent||''")

def detail_of(pg):
    return pg.evaluate("document.getElementById('paSubDetail')?.textContent||''")

def links(pg):
    return pg.evaluate("[...document.querySelectorAll('#paSubDlg [data-pa-sub-link]')].map(a=>a.getAttribute('data-pa-sub-link'))")

def open_manage(pg):
    pg.evaluate("__mock.calls=[]")
    pg.evaluate("window.PayAviatorManageSubscription.open()")
    pg.wait_for_timeout(350)

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
    check('package is the app id', pg.evaluate('window.PayAviatorManageSubscription.PLAY_PACKAGE')=='com.payaviator.app')
    check('settings row is present', pg.evaluate("!!document.querySelector('[data-pa-sub-manage]')"))

    pg.evaluate("""__mock.routes['/api/billing/status']={status:200,body:{plan:'premium',source:'play',productId:'payaviator_plus_monthly',state:'SUBSCRIPTION_STATE_ACTIVE',cancelAtPeriodEnd:false,expiresAt:'2027-01-01T00:00:00.000Z'}}""")
    open_manage(pg)
    play_links = links(pg)
    check('Play route uses package and status product id', play_links==['https://play.google.com/store/account/subscriptions?package=com.payaviator.app&sku=payaviator_plus_monthly'], play_links)
    check('Play screen does not claim it cancelled the subscription', 'will not mark this cancelled' in detail_of(pg).lower(), detail_of(pg))
    check('Play route does not call Stripe', not any('stripe' in c[1] for c in pg.evaluate('__mock.calls')))

    pg.evaluate("document.querySelector('#paSubDlg .close').click()")
    pg.evaluate("""__mock.routes['/api/billing/status']={status:500,body:{error:'Could not load plan.',code:'BILLING_STATUS_FAILED'}}""")
    open_manage(pg)
    check('failed refresh does not reuse the previous Play link', links(pg)==[] and 'Could not check' in status_of(pg), status_of(pg))
    check('failed refresh says nothing was cancelled', 'Nothing was cancelled' in detail_of(pg), detail_of(pg))

    pg.evaluate("""__mock.routes['/api/billing/status']={status:401,body:{error:'Invalid or expired session. Please sign in again.',code:'UNAUTHENTICATED'}}""")
    open_manage(pg)
    check('auth failure keeps the subscription in place', 'Sign in again' in detail_of(pg) and 'Nothing was cancelled' in detail_of(pg), detail_of(pg))

    pg.evaluate("""__mock.routes['/api/billing/status']={status:200,body:{plan:'premium',source:'stripe',productId:'price_123',state:'SUBSCRIPTION_STATE_ACTIVE',cancelAtPeriodEnd:false,periodEnd:null}}""")
    pg.evaluate("""__mock.routes['/api/billing/stripe/portal']={status:200,body:{url:'https://billing.stripe.com/p/session_test'}}""")
    open_manage(pg)
    check('Stripe screen does not invent a portal link before the call', links(pg)==[])
    pg.evaluate("[...document.querySelectorAll('#paSubDlg button')].find(b=>b.textContent.includes('Stripe')).click()")
    pg.wait_for_timeout(350)
    posts = [c for c in pg.evaluate('__mock.calls') if c[0]=='POST']
    check('portal call is the ownership-checked route with no customer id', posts and posts[-1][1]=='/api/billing/stripe/portal' and 'cus_' not in posts[-1][2] and 'customer' not in posts[-1][2].lower(), posts)
    check('portal link is the server url', links(pg)==['https://billing.stripe.com/p/session_test'], links(pg))
    check('portal success is not labeled cancelled', 'will not show this subscription as cancelled until' in detail_of(pg).lower() or 'not show this subscription as cancelled' in detail_of(pg).lower(), detail_of(pg))

    pg.evaluate("""__mock.routes['/api/billing/stripe/portal']={status:200,body:{url:'https://evil.example/portal'}}""")
    open_manage(pg)
    pg.evaluate("[...document.querySelectorAll('#paSubDlg button')].find(b=>b.textContent.includes('Stripe')).click()")
    pg.wait_for_timeout(350)
    check('non-Stripe portal url is not opened', links(pg)==[] and 'did not return a Stripe billing portal' in detail_of(pg), detail_of(pg))

    pg.evaluate("""__mock.routes['/api/billing/status']={status:200,body:{plan:'premium',source:'apple',productId:'sku',state:'SUBSCRIPTION_STATE_ACTIVE'}}""")
    open_manage(pg)
    check('unknown provider is not sent to Play or Stripe', links(pg)==[] and 'did not say Google Play or Stripe' in status_of(pg) and 'Nothing was cancelled' in detail_of(pg), status_of(pg))

    pg.evaluate("""__mock.routes['/api/billing/status']={status:200,body:{plan:'free',source:null,productId:null,state:null}}""")
    open_manage(pg)
    check('no subscription explains there is nothing active', 'No active Plus' in status_of(pg) and 'Nothing was cancelled' in detail_of(pg), status_of(pg))
    check('no-subscription Play link has package and no invented sku', links(pg)==['https://play.google.com/store/account/subscriptions?package=com.payaviator.app'], links(pg))

    pg.evaluate("""__mock.routes['/api/billing/status']={status:200,body:{plan:'premium',source:'play',productId:'payaviator_plus_monthly',state:'SUBSCRIPTION_STATE_ACTIVE',expiresAt:'2027-01-01T00:00:00.000Z'}}""")
    pg.evaluate("window.openPayAviatorConnectedAccounts920()")
    pg.wait_for_timeout(400)
    check('manage control is next to account actions', pg.evaluate("!!document.querySelector('#pp920AccountsBody [data-pp-manage-sub]')"))
    pg.evaluate("document.querySelector('#pp920AccountsBody [data-ppauth-delete]').click()")
    pg.wait_for_timeout(200)
    copy = pg.evaluate("document.querySelector('#ppConfirm902 .pp902-confirm-copy')?.textContent||''")
    check('delete warning says billing is not cancelled', 'does not cancel Google Play or Stripe billing' in copy and 'You can delete without cancelling' in copy, copy)
    check('delete does not demand a reason or a survey', 'do not need to give a reason' in copy.lower() and 'survey' not in copy.lower() and 'must cancel' not in copy.lower(), copy)
    pg.evaluate("document.querySelector('#ppConfirm902 .pp902-remove').click()")
    pg.wait_for_timeout(300)
    native = pg.evaluate("__mock.calls.filter(c=>c[0]==='NATIVE').map(c=>c[1])")
    check('delete still proceeds while Plus is active', 'authDeleteAccount' in native and 'authSignOut' not in native, native)
    check('no page errors at end', not errs, errs)
    browser.close()

print('SUBSCRIPTION MANAGE ' + ('PASS' if ok else 'FAIL'))
sys.exit(0 if ok else 1)
