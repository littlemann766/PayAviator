#!/usr/bin/env python3
"""4.1.1 Continue with Google / email / phone on Beth's screens, Settings > Sign in -> Beth's sign-in screen,
Google account = verified email. Mocked Android bridge.
Usage: test-google-411.py http://localhost:PORT/index.html [shotdir]"""
import sys, os
from playwright.sync_api import sync_playwright
URL=sys.argv[1]; SHOTS=sys.argv[2] if len(sys.argv)>2 else None
MOCK="""(()=>{
const st=window.__mock={signedIn:false,provider:'',google:%s,calls:[]};
const deliver=(fn,o)=>setTimeout(()=>window[fn]&&window[fn](JSON.stringify(o)),20);
const state=()=>({available:true,googleAvailable:st.google,signedIn:st.signedIn,uid:st.signedIn?'u1':undefined,email:'a@gmail.com',provider:st.provider,emailVerified:st.provider==='google'});
window.AndroidBridge={
 authGetState:()=>JSON.stringify(state()),
 apiRequest:(id,m,p,b)=>{st.calls.push([m,p]);deliver('PayAviatorNativeApiResult',{requestId:id,status:200,body:'{}'})},
 authSignInWithGoogle:(id)=>{st.calls.push(['NATIVE','google']);st.signedIn=true;st.provider='google';deliver('PayAviatorAuthResult',{requestId:id,ok:true,state:state()})},
 authSignInWithEmail:(id)=>{st.signedIn=true;st.provider='password';deliver('PayAviatorAuthResult',{requestId:id,ok:true,state:state()})},
 authCreateAccount:(id)=>{st.signedIn=true;st.provider='password';deliver('PayAviatorAuthResult',{requestId:id,ok:true,state:state()})},
 authSendEmailVerification:(id)=>{st.calls.push(['NATIVE','sendVerify']);deliver('PayAviatorAuthResult',{requestId:id,ok:true,state:state()})},
 authReloadUser:(id)=>{st.calls.push(['NATIVE','reload']);deliver('PayAviatorAuthResult',{requestId:id,ok:true,state:state()})},
 billingGetPurchases:()=>'[]',
 getAppVersionName:()=>'4.1.1',
 openSupportEmail:()=>{st.calls.push(['NATIVE','support']);return st.mailApp!==false}
};
window.alert=window.confirm=window.prompt=function(){window.__native=(window.__native||0)+1};
})()"""
BASE="""(()=>{localStorage.clear();localStorage.setItem('payAviator_onboarding_v1_done','1');localStorage.setItem('payaviator_tip_popup_seen_v1','1');localStorage.setItem('payAviator_security_tip_launch_count_v1','99')})()"""
ok=True
def check(n,c,d=''):
    global ok; print(('PASS ' if c else 'FAIL ')+n+(' '+str(d) if d else '')); ok=ok and bool(c)
def onb(pg): return pg.evaluate("document.getElementById('ppOnb').classList.contains('show')?[...document.querySelectorAll('#ppOnb section[data-onb]')].find(s=>!s.hidden)?.dataset.onb:null")
def vis(pg,sec,sel): return pg.evaluate(f"(()=>{{const e=document.querySelector('#ppOnb section[data-onb=\"{sec}\"] {sel}');if(!e)return false;const r=e.getBoundingClientRect();return r.width>0&&r.height>0}})()")
with sync_playwright() as p:
    b=p.chromium.launch(executable_path='/usr/bin/google-chrome',args=['--no-sandbox'])
    for vw,vh in [(390,844),(360,640)]:
        print('== viewport',vw,vh)
        def page(google=True,fresh=False):
            c=b.new_context(viewport={'width':vw,'height':vh},has_touch=True,is_mobile=True,timezone_id='America/New_York')
            c.route(lambda u:not u.startswith('http://localhost'),lambda r:r.abort())
            pg=c.new_page(); pg.errs=[]; pg.on('pageerror',lambda e:pg.errs.append(str(e)))
            pg.goto(URL); pg.evaluate(BASE)
            if fresh: pg.evaluate("localStorage.removeItem('payAviator_onboarding_v1_done')")
            c.add_init_script(MOCK%('true' if google else 'false'))
            pg.reload(); pg.wait_for_timeout(2500); return c,pg
        def shot(pg,name,full=False):
            if SHOTS: pg.screenshot(path=os.path.join(SHOTS,f'boss-411-{vw}x{vh}-{name}.png'))
        c,pg=page()
        check('welcome at start-up',onb(pg)=='welcome')
        labels=pg.evaluate("[...document.querySelectorAll('#ppOnb section[data-onb=welcome] .onb-actions .onb-google')].map(b=>[b.innerText.trim(),Math.round(b.getBoundingClientRect().width),Math.round(b.getBoundingClientRect().height)])")
        check('welcome: Google / email (4.1.3: phone hidden while PHONE_SIGNIN=false)',[l[0] for l in labels if l[1]]==['Continue with Google','Continue with email'] and not vis(pg,'welcome','[data-onb-act=phone]'),labels)
        labels=[l for l in labels if l[1]]
        check('three choices equal size',len({(l[1],l[2]) for l in labels})==1,labels)
        sty=pg.evaluate("(()=>{const s=getComputedStyle(document.querySelector('#ppOnb .onb-google'));return [s.backgroundColor,s.color]})()")
        check('Google standard light button (white, dark text)',sty==['rgb(255, 255, 255)','rgb(31, 31, 31)'],sty)
        check('all welcome buttons fit on screen',pg.evaluate("[...document.querySelectorAll('#ppOnb section[data-onb=welcome] .onb-actions button')].every(b=>{const r=b.getBoundingClientRect();return r.bottom<=innerHeight+1&&r.top>=0})"))
        shot(pg,'welcome')
        pg.locator('#ppOnb section[data-onb="welcome"] .onb-email').tap(); pg.wait_for_timeout(300)
        check('Continue with email -> sign-in screen',onb(pg)=='signin')
        check('sign-in: Google under the email form, phone hidden',vis(pg,'signin','.onb-alt [data-onb-act=google]') and not vis(pg,'signin','.onb-alt [data-onb-act=phone]') and pg.evaluate("(()=>{const f=document.getElementById('ppOnbSignForm'),g=document.querySelector('#ppOnb section[data-onb=signin] .onb-alt');return f.getBoundingClientRect().bottom<=g.getBoundingClientRect().top})()"))
        shot(pg,'signin')
        pg.locator('#ppOnb section[data-onb="signin"] [data-onb-go="create"]').tap(); pg.wait_for_timeout(300)
        check('New here? -> create screen',onb(pg)=='create')
        check('create: Google under the email form, phone hidden',vis(pg,'create','.onb-alt [data-onb-act=google]') and not vis(pg,'create','.onb-alt [data-onb-act=phone]') and pg.evaluate("(()=>{const f=document.getElementById('ppOnbCreateForm'),g=document.querySelector('#ppOnb section[data-onb=create] .onb-alt');return f.getBoundingClientRect().bottom<=g.getBoundingClientRect().top})()"))
        shot(pg,'create')
        pg.locator('#ppOnb section[data-onb="create"] .onb-alt [data-onb-act="google"]').tap(); pg.wait_for_timeout(800)
        check('create Google -> native authSignInWithGoogle, signed in, closed',['NATIVE','google'] in pg.evaluate("__mock.calls") and onb(pg) is None and pg.evaluate("PayAviatorAuth.isSignedIn()"))
        check('Google account counts as verified',pg.evaluate("PayAviatorAuth.getState().emailVerified")==True)
        check('choice stored as account',pg.evaluate("localStorage.getItem('payaviator_onboarding_choice_v1')")=='account')
        e=pg.evaluate("(()=>{const err={code:'EMAIL_NOT_VERIFIED'};PayAviatorAccountGate.handle(err,{});return err.message})()"); pg.wait_for_timeout(300)
        check('Google + 403 email_not_verified: no Verify dialog, token refresh',not pg.evaluate("!!document.getElementById('pa410VerifyDlg')?.open") and ['NATIVE','reload'] in pg.evaluate("__mock.calls"),e)
        check('no page errors',not pg.errs,pg.errs); c.close()
        # welcome Google
        c,pg=page()
        pg.locator('#ppOnb section[data-onb="welcome"] [data-onb-act="google"]').tap(); pg.wait_for_timeout(800)
        check('welcome Google signs in',pg.evaluate("PayAviatorAuth.isSignedIn()") and onb(pg) is None); c.close()
        # Settings > Sign in -> Beth's sign-in
        c,pg=page()
        pg.evaluate("localStorage.setItem('payaviator_onboarding_choice_v1','guest')"); pg.reload(); pg.wait_for_timeout(2500)
        pg.evaluate("window.openPayAviatorConnectedAccounts920&&window.openPayAviatorConnectedAccounts920()"); pg.wait_for_timeout(1200)
        has=pg.evaluate("!!document.querySelector('[data-ppauth-signin]')")
        pg.evaluate("document.querySelector('[data-ppauth-signin]').click()"); pg.wait_for_timeout(500)
        check('Settings > Sign in opens Beth sign-in screen (not old sheet)',has and onb(pg)=='signin' and not pg.evaluate("document.getElementById('ppAuthSheet')?.classList.contains('show')"),onb(pg))
        shot(pg,'settings-signin')
        pg.locator('#ppOnb section[data-onb="signin"] .onb-alt [data-onb-act="google"]').tap(); pg.wait_for_timeout(1000)
        check('Sign in from Settings with Google completes',pg.evaluate("PayAviatorAuth.isSignedIn()") and onb(pg) is None)
        check('no page errors (settings)',not pg.errs,pg.errs); c.close()
        # Contact support
        c,pg=page()
        pg.locator('#ppOnb section[data-onb="welcome"] .onb-email').tap(); pg.wait_for_timeout(300)
        check('sign-in screen has Need help?',vis(pg,'signin','[data-pa411-support]'))
        shot(pg,'signin-help')
        pg.locator('#ppOnb section[data-onb="signin"] [data-pa411-support]').tap(); pg.wait_for_timeout(300)
        check('Need help? -> native mailto intent',['NATIVE','support'] in pg.evaluate("__mock.calls"))
        b2=pg.evaluate("PayAviatorSupport.body()"); m2=pg.evaluate("PayAviatorSupport.mailto()")
        check('mailto: support@payaviator.app, subject, version-only body',m2.startswith('mailto:support@payaviator.app?subject=PayAviator%20support&body=') and b2.startswith('App version: 4.1.1\nAndroid version:') and 'a@gmail.com' not in m2 and 'u1' not in b2,m2)
        pg.locator('#ppOnb section[data-onb="signin"] .onb-back').tap(); pg.wait_for_timeout(200)
        pg.locator('#ppOnb [data-onb-act="guest"]').tap(); pg.wait_for_timeout(300)
        pg.evaluate("document.querySelectorAll('dialog[open]').forEach(d=>d.close());document.querySelector('.mb119-nav[data-view=settings]').click()"); pg.wait_for_timeout(800)
        row=pg.locator('#mb119Settings [data-pa411-support]')
        check('Settings has Contact support row',row.count()==1 and 'Contact support' in row.inner_text())
        pg.evaluate("document.querySelector('#mb119Settings [data-pa411-support]').scrollIntoView({block:'center'})"); pg.wait_for_timeout(400); shot(pg,'settings-support')
        n0=len([x for x in pg.evaluate("__mock.calls") if x==['NATIVE','support']])
        row.tap(); pg.wait_for_timeout(300)
        check('Settings row -> native mailto intent',len([x for x in pg.evaluate("__mock.calls") if x==['NATIVE','support']])==n0+1)
        pg.evaluate("__mock.mailApp=false"); row.tap(); pg.wait_for_timeout(300)
        t=pg.evaluate("document.querySelector('.pa411-toast')?.innerText||''")
        check('no email app: in-app note with the address, no native dialog','support@payaviator.app' in t and not pg.evaluate("window.__native||0"),t)
        check('no page errors (support)',not pg.errs,pg.errs); c.close()
        # First-launch order: welcome first, setup wizard only after a choice
        c,pg=page(fresh=True); pg.wait_for_timeout(800)
        wiz=lambda:pg.evaluate("!!document.getElementById('mb212Onboarding')?.open")
        check('first launch: welcome shown, setup wizard not yet',onb(pg)=='welcome' and not wiz())
        shot(pg,'order-1-welcome')
        pg.locator('#ppOnb section[data-onb="welcome"] [data-onb-act="guest"]').tap(); pg.wait_for_timeout(1200)
        check('after guest: setup wizard opens',onb(pg) is None and wiz())
        shot(pg,'order-2-setup')
        txt=pg.inner_text('#mb212Onboarding')
        check('Setup copy: saved on this phone + App Colors hint','Your budget is saved on this phone.' in txt and 'backups are only made when you choose' in txt and 'in Settings under App Colors' in txt and '→' not in txt)
        c.close()
        c,pg=page(fresh=True); pg.wait_for_timeout(800)
        pg.locator('#ppOnb section[data-onb="welcome"] [data-onb-act="google"]').tap(); pg.wait_for_timeout(1500)
        check('after Google sign-in: setup wizard opens',onb(pg) is None and wiz()); c.close()
        c,pg=page(); pg.evaluate("localStorage.setItem('payaviator_onboarding_choice_v1','guest')"); pg.reload(); pg.wait_for_timeout(2500)
        check('existing user (setup done): no wizard, no welcome',onb(pg) is None and not wiz()); c.close()
        # Android Back on Beth's screens
        c,pg=page()
        navvis=lambda:pg.evaluate("getComputedStyle(document.getElementById('mb119BottomNav')).visibility==='visible'&&!document.body.classList.contains('ppOnb-open')")
        bk=lambda:(pg.evaluate("window.payAviatorHandleAndroidBack()"),pg.wait_for_timeout(500))[0]
        pg.locator('#ppOnb section[data-onb="welcome"] .onb-email').tap(); pg.wait_for_timeout(300)
        r=bk(); check('Back on sign-in -> welcome',r and onb(pg)=='welcome',onb(pg))
        pg.locator('#ppOnb section[data-onb="welcome"] .onb-email').tap(); pg.wait_for_timeout(300)
        pg.locator('#ppOnb section[data-onb="signin"] [data-onb-go="create"]').tap(); pg.wait_for_timeout(300)
        r=bk(); check('Back on create -> welcome',r and onb(pg)=='welcome',onb(pg))
        r=bk(); check('Back on first-launch welcome stays (consumed, no glitched Home)',r and onb(pg)=='welcome' and pg.evaluate("document.body.classList.contains('ppOnb-open')"))
        shot(pg,'back-welcome')
        pg.locator('#ppOnb section[data-onb="welcome"] [data-onb-act="guest"]').tap(); pg.wait_for_timeout(500)
        check('guest: Home with nav bar',onb(pg) is None and navvis())
        pg.evaluate("window.openPayAviatorConnectedAccounts920&&window.openPayAviatorConnectedAccounts920()"); pg.wait_for_timeout(1000)
        pg.evaluate("document.querySelector('[data-ppauth-signin]').click()"); pg.wait_for_timeout(500)
        for i in range(4):
            if not pg.evaluate("PayAviatorVisibleSheets().length"): break
            bk()
        check('Settings sign-in + Back: overlay closed, nav bar visible',onb(pg) is None and navvis())
        shot(pg,'back-home-nav')
        check('no page errors (back)',not pg.errs,pg.errs); c.close()
        # no Google client id: Google hidden, email + phone remain
        c,pg=page(False)
        check('no Google config: Google hidden, email shown',not vis(pg,'welcome','[data-onb-act=google]') and vis(pg,'welcome','.onb-email'))
        c.close()
    b.close()
print('ALL PASS' if ok else 'SOME FAILED'); sys.exit(0 if ok else 1)
