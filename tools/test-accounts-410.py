#!/usr/bin/env python3
"""4.1.0 accounts regression (backend PR #8 contract), with a mocked Android bridge.
Checks: start-up welcome (create / sign in / guest), guest -> sign-up before linking a bank,
403 email_not_verified -> Verify dialog + reload/refresh, 402 subscription_required reasons ->
distinct upgrade messages, hosted-status skipped body, billing status/verify incl. 503, no native dialogs.
Usage: test-accounts-410.py http://localhost:PORT/index.html [shotdir]"""
import sys, json, os
from playwright.sync_api import sync_playwright
URL=sys.argv[1]; SHOTS=sys.argv[2] if len(sys.argv)>2 else None
MOCK="""(()=>{
const st=window.__mock={signedIn:%s,emailVerified:false,calls:[],routes:{},purchases:[]};
const deliver=(fn,obj)=>setTimeout(()=>window[fn]&&window[fn](JSON.stringify(obj)),20);
const state=()=>({available:true,googleAvailable:false,signedIn:st.signedIn,uid:st.signedIn?'u1':undefined,email:'a@b.co',emailVerified:st.emailVerified});
window.AndroidBridge={
 authGetState:()=>JSON.stringify(state()),
 apiRequest:(id,m,p,b)=>{st.calls.push([m,p,b]);const r=st.routes[p.split('?')[0]]||{status:200,body:{}};deliver('PayAviatorNativeApiResult',{requestId:id,status:r.status,body:JSON.stringify(r.body)})},
 authSendEmailVerification:(id)=>{st.calls.push(['NATIVE','sendVerify']);deliver('PayAviatorAuthResult',{requestId:id,ok:true,state:state()})},
 authReloadUser:(id)=>{st.calls.push(['NATIVE','reload']);deliver('PayAviatorAuthResult',{requestId:id,ok:true,state:state()})},
 authCreateAccount:(id,e,p)=>{st.signedIn=true;deliver('PayAviatorAuthResult',{requestId:id,ok:true,state:state()})},
 authSignInWithEmail:(id,e,p)=>{st.signedIn=true;deliver('PayAviatorAuthResult',{requestId:id,ok:true,state:state()})},
 billingGetPurchases:()=>JSON.stringify(st.purchases)
};
window.alert=window.confirm=window.prompt=function(){window.__native=(window.__native||0)+1};
})()"""
BASE="""(()=>{localStorage.clear();localStorage.setItem('payAviator_onboarding_v1_done','1');localStorage.setItem('payaviator_tip_popup_seen_v1','1');localStorage.setItem('payAviator_security_tip_launch_count_v1','99')})()"""
ok=True
def check(n,c,d=''):
    global ok; print(('PASS ' if c else 'FAIL ')+n+(' '+str(d) if d else '')); ok=ok and bool(c)
def onb(pg): return pg.evaluate("document.getElementById('ppOnb').classList.contains('show')?[...document.querySelectorAll('#ppOnb section[data-onb]')].find(s=>!s.hidden)?.dataset.onb:null")
def isopen(pg,i): return pg.evaluate(f"!!document.getElementById('{i}')?.open")
with sync_playwright() as p:
    b=p.chromium.launch(executable_path='/usr/bin/google-chrome',args=['--no-sandbox'])
    for vw,vh in [(390,844),(360,640)]:
        print('== viewport',vw,vh)
        def page(signed):
            c=b.new_context(viewport={'width':vw,'height':vh},has_touch=True,is_mobile=True,timezone_id='America/New_York')
            c.route(lambda u:not u.startswith('http://localhost'),lambda r:r.abort())
            pg=c.new_page(); pg.errs=[]; pg.on('pageerror',lambda e:pg.errs.append(str(e)))
            pg.goto(URL); pg.evaluate(BASE)
            c.add_init_script(MOCK%('true' if signed else 'false'))
            pg.reload(); pg.wait_for_timeout(2500); return c,pg
        def shot(pg,name):
            if SHOTS: pg.screenshot(path=os.path.join(SHOTS,f'a410-{vw}x{vh}-{name}.png'))
        # 1. Signed out first start: welcome
        c,pg=page(False)
        check('Beth welcome shows at start-up when signed out',onb(pg)=='welcome'); shot(pg,'welcome')
        pg.locator('#ppOnb [data-onb-act="guest"]').tap(); pg.wait_for_timeout(300)
        check('guest closes welcome and stores only the choice',onb(pg) is None and pg.evaluate("localStorage.getItem('payaviator_onboarding_choice_v1')")=='guest')
        pg.reload(); pg.wait_for_timeout(1500)
        check('welcome not shown again for guest',onb(pg) is None)
        check('guest makes no billing calls',not any('/api/billing' in x[1] for x in pg.evaluate("__mock.calls")))
        # guest taps Connect bank -> Beth's guest prompt -> Sign up with email -> create form
        pg.evaluate("window.openPayAviatorConnectedAccounts920&&window.openPayAviatorConnectedAccounts920()"); pg.wait_for_timeout(1200)
        pg.evaluate("document.getElementById('pp920ConnectBank').click()"); pg.wait_for_timeout(500)
        check('guest Connect bank shows guest sign-up prompt',onb(pg)=='guest',onb(pg))
        check('no link-token call as guest',not any('link-token' in x[1] for x in pg.evaluate("__mock.calls"))); shot(pg,'guest-link')
        pg.locator('#ppOnb section[data-onb="guest"] [data-onb-go="create"]').tap(); pg.wait_for_timeout(300)
        check('Sign up with email opens create',onb(pg)=='create'); shot(pg,'create')
        pg.fill('#ppOnbNewEmail','a@b.co'); pg.fill('#ppOnbNewPw','secret123'); pg.fill('#ppOnbNewPw2','secret123')
        pg.evaluate("document.getElementById('ppOnbCreateForm').requestSubmit()"); pg.wait_for_timeout(800)
        check('create -> native authCreateAccount, signed in, biometrics offer',pg.evaluate("__mock.signedIn") and onb(pg)=='bio',onb(pg)); shot(pg,'bio')
        pg.locator('#ppOnb [data-onb-act="bioOn"]').tap(); pg.wait_for_timeout(300)
        check('biometrics honestly not available yet',onb(pg)=='bio' and 'later update' in pg.inner_text('#ppOnb section[data-onb="bio"]'))
        pg.locator('#ppOnb [data-onb-act="bioSkip"]').tap(); pg.wait_for_timeout(300)
        check('Not now closes',onb(pg) is None)
        check('status + restore called after sign-in',any(x[1]=='/api/billing/status' for x in pg.evaluate("__mock.calls")))
        check('no page errors (guest)',not pg.errs,pg.errs); c.close()
        # welcome -> create
        c,pg=page(False)
        pg.locator('#ppOnb section[data-onb="welcome"] [data-onb-go="signin"]').tap(); pg.wait_for_timeout(300)
        pg.fill('#ppOnbEmail','a@b.co'); pg.fill('#ppOnbPw','secret123'); pg.evaluate("document.getElementById('ppOnbSignForm').requestSubmit()"); pg.wait_for_timeout(800)
        check('welcome Sign in -> native sign-in',pg.evaluate("__mock.signedIn")==True,onb(pg)); c.close()
        # 2. Signed in
        c,pg=page(True)
        check('no welcome when signed in',onb(pg) is None)
        pg.evaluate("__mock.routes['/api/plaid/create-link-token']={status:403,body:{error:'email_not_verified',code:'EMAIL_NOT_VERIFIED'}}")
        e=pg.evaluate("window.PayAviatorBankApi('/api/plaid/create-link-token',{method:'POST',body:'{}'}).then(()=>null,e=>[e.code,e.message])"); pg.wait_for_timeout(200)
        check('403 -> friendly message + Verify dialog',e and e[0]=='EMAIL_NOT_VERIFIED' and isopen(pg,'pa410VerifyDlg'),e); shot(pg,'verify')
        pg.locator('[data-pa410-verify="send"]').tap(); pg.wait_for_timeout(300)
        check('Send verification calls native',['NATIVE','sendVerify'] in pg.evaluate("__mock.calls") and 'newest email' in pg.inner_text('#pa410VerifyStatus'))
        pg.locator('[data-pa410-verify="done"]').tap(); pg.wait_for_timeout(300)
        check('not verified yet keeps dialog open',isopen(pg,'pa410VerifyDlg') and 'isn' in pg.inner_text('#pa410VerifyStatus'))
        pg.evaluate("__mock.emailVerified=true"); pg.locator('[data-pa410-verify="done"]').tap(); pg.wait_for_timeout(300); vmsg=pg.inner_text('#pa410VerifyStatus'); pg.wait_for_timeout(1600)
        check('verified -> reload/refresh token natively, confirms, dialog closes','verified.' in vmsg and pg.evaluate("__mock.calls.filter(x=>x[1]==='reload').length")==3 and not isopen(pg,'pa410VerifyDlg'))
        ok_btn=pg.get_by_role('button',name='OK')
        if ok_btn.count() and ok_btn.first.is_visible(): ok_btn.first.click(); pg.wait_for_timeout(300)
        msgs={}
        for reason,path in [('device_already_used_free','/api/plaid/create-link-token'),('account_already_used_free','/api/plaid/exchange-public-token'),('','/api/plaid/create-link-token')]:
            body={'error':'subscription_required','code':'SUBSCRIPTION_REQUIRED','limit':1,'linked':1}
            if reason: body['reason']=reason
            pg.evaluate("([p,b])=>{__mock.routes[p]={status:402,body:b}}",[path,body])
            pg.evaluate("__mock.routes['/api/billing/status']={status:503,body:{error:'billing_not_configured',code:'BILLING_NOT_CONFIGURED'}}")
            e=pg.evaluate("p=>window.PayAviatorBankApi(p,{method:'POST',body:'{}'}).then(()=>null,e=>[e.code,e.reason])",path); pg.wait_for_timeout(400)
            msgs[reason]=pg.inner_text('#ppOnb [data-pa410-reason]')
            check(f'402 reason={reason or "none"} opens upgrade',e and e[0]=='SUBSCRIPTION_REQUIRED' and onb(pg)=='upgrade',e)
            shot(pg,'upgrade-'+(reason or 'limit'))
            vis=pg.evaluate("()=>{const q=s=>{const e=document.querySelector(s);return !!e&&e.getClientRects().length>0};return {plans:q('#ppOnb .onb-plans'),price:q('#ppOnbPrice'),fine:q('#ppOnbPriceFine'),trial:q('#ppOnb .onb-trial')}}")
            txt=pg.inner_text('#ppOnb section[data-onb="upgrade"]')
            # 4.1.3 (boss-approved): prices always show, no trial, "Plus is coming soon." once, button "Upgrade" disabled
            check(f'prices shown, no trial ({reason or "none"})',vis['plans'] and '$3.99' in txt and '$29.99' in txt and not vis['trial'] and 'trial' not in txt.lower(),[vis,txt[:200]])
            check('Plus is coming soon (once), Upgrade button disabled','Plus is coming soon.' in txt and txt.lower().count('coming soon')==1 and pg.evaluate("(b=>b.disabled&&b.innerText.trim()=='Upgrade')(document.querySelector('#ppOnb [data-onb-act=subscribe]'))"),txt[-200:])
            pg.evaluate("window.payAviatorHandleAndroidBack()"); pg.wait_for_timeout(300)
            check('Back closes upgrade',not onb(pg)=='upgrade')
        check('three distinct reason messages',len(set(msgs.values()))==3,msgs)
        for code,status,expect,upg in [('INTEGRITY_FAILED',403,'Google Play or subscribe',True),('INTEGRITY_NOT_CONFIGURED',503,'try again later',False),('DEVICE_ID_INVALID',400,'update PayAviator',False)]:
            pg.evaluate("([c,s])=>{__mock.routes['/api/plaid/create-link-token']={status:s,body:{error:c.toLowerCase(),code:c,reason:'device_integrity_failed'}}}",[code,status])
            e=pg.evaluate("window.PayAviatorBankApi('/api/plaid/create-link-token',{method:'POST',body:'{}'}).then(()=>null,e=>e.message)"); pg.wait_for_timeout(400)
            check(f'{status} {code} message',e and expect in e,e)
            check(f'{code} upgrade screen {"opens" if upg else "not opened"}',(onb(pg)=='upgrade')==upg)
            if upg: check('integrity message on upgrade','Google Play' in pg.inner_text('#ppOnb [data-pa410-reason]')); pg.evaluate("window.payAviatorHandleAndroidBack()"); pg.wait_for_timeout(300)
        pg.evaluate("__mock.routes['/api/plaid/hosted-status']={status:200,body:{connected:true,skipped:{error:'subscription_required',code:'SUBSCRIPTION_REQUIRED',reason:'device_already_used_free'}}}")
        pg.evaluate("window.PayAviatorBankApi('/api/plaid/hosted-status');0"); pg.wait_for_timeout(300)
        check('hosted-status partial skipped -> upgrade',onb(pg)=='upgrade' and 'phone' in pg.inner_text('#ppOnb [data-pa410-reason]')); pg.evaluate("window.payAviatorHandleAndroidBack()")
        pg.evaluate("__mock.routes['/api/billing/google-play/verify']={status:200,body:{active:true,subscriptionState:'SUBSCRIPTION_STATE_ACTIVE'}};__mock.routes['/api/billing/status']={status:200,body:{plan:'premium',limit:null,billingConfigured:true}}")
        r=pg.evaluate("window.PayAviatorBillingPurchaseResult({productId:'payaviator_premium',purchaseToken:'tok'})")
        calls=pg.evaluate("__mock.calls")
        v=[x for x in calls if x[1]=='/api/billing/google-play/verify']
        check('purchase -> POST verify with productId+purchaseToken',v and v[-1][0]=='POST' and json.loads(v[-1][2])=={'productId':'payaviator_premium','purchaseToken':'tok'} and r['ok'],v)
        check('status refreshed after verify -> premium',pg.evaluate("PayAviatorAccountGate.billing.plan")=='premium')
        for plan in ['comp','premium']:
            pg.evaluate("p=>{__mock.routes['/api/billing/status']={status:200,body:{plan:p,linkedBanks:3,limit:null,grandfathered:false,billingConfigured:true}}}",plan)
            pg.evaluate("PayAviatorAccountGate.refreshStatus()"); pg.wait_for_timeout(300)
            check(f'{plan}: full access, no bank limit',pg.evaluate("PayAviatorAccountGate.isPaid()") and pg.evaluate("PayAviatorAccountGate.bankLimit()") is None)
            pg.evaluate("__mock.routes['/api/plaid/create-link-token']={status:402,body:{error:'subscription_required',code:'SUBSCRIPTION_REQUIRED'}}")
            pg.evaluate("window.PayAviatorBankApi('/api/plaid/create-link-token',{method:'POST',body:'{}'}).catch(()=>0);0"); pg.wait_for_timeout(400)
            check(f'{plan}: no upgrade screen / button',onb(pg)!='upgrade')
        pg.evaluate("__mock.routes['/api/billing/status']={status:200,body:{plan:'free',limit:1,billingConfigured:true}};PayAviatorAccountGate.refreshStatus()"); pg.wait_for_timeout(300)
        check('free: limit 1, not paid',pg.evaluate("PayAviatorAccountGate.bankLimit()")==1 and not pg.evaluate("PayAviatorAccountGate.isPaid()"))
        pg.evaluate("__mock.routes['/api/billing/google-play/verify']={status:503,body:{error:'billing_not_configured',code:'BILLING_NOT_CONFIGURED'}}")
        r=pg.evaluate("window.PayAviatorBillingPurchaseResult({productId:'payaviator_premium',purchaseToken:'tok'})")
        check('verify 503 handled without throwing',r['ok']==False and r['status']==503)
        pg.evaluate("PayAviatorLinkStats.reset()")
        pg.evaluate("window.PayAviatorPlaidNativeResult(JSON.stringify({status:'exit',error_code:'INVALID_CREDENTIALS',error_message:'x',institution_id:'ins_3',link_session_id:'sess-1'}))"); pg.wait_for_timeout(300)
        pg.evaluate("__mock.routes['/api/plaid/exchange-public-token']={status:200,body:{}};window.PayAviatorPlaidNativeResult(JSON.stringify({status:'connected',public_token:'public-sandbox-abc',institution_name:'Chase',institution_id:'ins_3',link_session_id:'sess-2'}))"); pg.wait_for_timeout(800)
        ls=pg.evaluate("PayAviatorLinkStats.get()"); raw=pg.evaluate("localStorage.getItem('payaviator_link_stats_v1')")
        check('link stats: exit code + success counted',ls.get('counts',{}).get('exit_native')==1 and ls.get('counts',{}).get('success_native')==1 and ls.get('codes',{}).get('exit_native:INVALID_CREDENTIALS')==1,ls)
        check('link stats store no ids/tokens/institutions',not any(x in raw for x in ['ins_3','sess','public-','Chase','u1','a@b']),raw)
        check('no native alert/confirm/prompt',not pg.evaluate("window.__native||0"))
        check('no page errors (signed in)',not pg.errs,pg.errs); c.close()
        # 3. restore on start with an existing purchase
        c=b.new_context(viewport={'width':vw,'height':vh}); c.route(lambda u:not u.startswith('http://localhost'),lambda r:r.abort())
        c.add_init_script(MOCK%'true'); c.add_init_script("window.__mock.purchases=[{productId:'payaviator_premium',purchaseToken:'old'}]")
        pg=c.new_page(); pg.goto(URL); pg.wait_for_timeout(2500)
        calls=pg.evaluate("__mock.calls")
        check('app start: verify existing purchase, then status',[x[1] for x in calls if '/api/billing' in x[1]][:2]==['/api/billing/google-play/verify','/api/billing/status'],[x[1] for x in calls]); c.close()
    print('ACCOUNTS410 '+('PASS' if ok else 'FAIL')); sys.exit(0 if ok else 1)
