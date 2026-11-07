#!/usr/bin/env python3
"""Candidate auth feedback for 4.2.6. No live Firebase, no email send.
Usage: test-auth-feedback-426.py http://127.0.0.1:PORT/index.html
"""
import os, re, sys
from playwright.sync_api import sync_playwright

URL = sys.argv[1]
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
ok = True

def check(name, cond, detail=''):
    global ok
    print(('PASS ' if cond else 'FAIL ') + name + ((' ' + str(detail)) if detail else ''))
    ok = ok and bool(cond)

java = open(os.path.join(ROOT, 'app/src/main/java/com/payaviator/app/auth/FirebaseSignIn.java'), encoding='utf-8').read()
req = open(os.path.join(ROOT, 'app/src/main/java/com/payaviator/app/auth/VerifyEmailRequest.java'), encoding='utf-8').read()
html = open(os.path.join(ROOT, 'index.html'), encoding='utf-8').read()
assets = open(os.path.join(ROOT, 'app/src/main/assets/index.html'), 'rb').read()
check('assets/index.html matches root index.html', assets == open(os.path.join(ROOT, 'index.html'), 'rb').read())
check('signup send keeps a callback', 'sendVerificationWithWebKey(u, true, cb)' in java)
check('signup no longer ignores the send result', 'sendVerificationWithWebKey(u, null)' not in java)
check('failed signup send does not delete the user', 'user.delete' not in java.split('sendVerificationWithWebKey')[1].split('reloadAndRefreshToken')[0])
returns = [ln for ln in req.splitlines() if ln.strip().startswith('return "')]
check('verification body has no continueUrl field', bool(returns) and all('continueUrl' not in ln for ln in returns), returns)
check('HTTP 200 is not described as inbox delivery', 'does not prove' in req)
check('google failure is classified', 'GoogleSignInFailure.fromCredentialError' in java)
check('no provider linking was added', 'linkWithCredential' not in java and 'linkWithCredential' not in html)

MOCK = r"""(()=>{
const st=window.__authCase={mode:'incomplete'};
const deliver=(fn,o)=>setTimeout(()=>window[fn]&&window[fn](JSON.stringify(o)),30);
const state=(signed)=>({available:true,googleAvailable:true,signedIn:!!signed,uid:signed?'u-email':'',email:signed?'tester@gmail.com':'',provider:signed?'password':'',emailVerified:false});
window.AndroidBridge={
 authGetState:()=>JSON.stringify(state(false)),
 apiRequest:(id)=>{deliver('PayAviatorNativeApiResult',{requestId:id,status:200,body:'{}'})},
 billingGetPurchases:()=>'[]',
 authSignInWithGoogle:(id)=>{
   const mode=st.mode;
   if(mode==='ok'){deliver('PayAviatorAuthResult',{requestId:id,ok:true,code:'',error:'',state:Object.assign(state(true),{provider:'google',emailVerified:true})});return}
   if(mode==='collision'){deliver('PayAviatorAuthResult',{requestId:id,ok:false,code:'ERROR_ACCOUNT_EXISTS_WITH_DIFFERENT_CREDENTIAL',error:'This email already has an email-and-password PayAviator account. Sign in with email and password. Google was not linked, and the account was not changed.'});return}
   if(mode==='blank'){deliver('PayAviatorAuthResult',{requestId:id,ok:false,code:'CANCELLED',error:''});return}
   deliver('PayAviatorAuthResult',{requestId:id,ok:false,code:'GOOGLE_INCOMPLETE',error:'Google sign-in did not finish. Try again, or use email and password.'});
 },
 authCreateAccount:(id)=>{
   const mode=st.mode;
   const base={requestId:id,ok:true,state:state(true)};
   if(mode==='verify-fail')deliver('PayAviatorAuthResult',Object.assign(base,{code:'VERIFY_EMAIL_FAILED',error:'Your account was created and kept. PayAviator could not confirm the verification email was sent (status 403). Use Send verification email. Nothing was deleted.'}));
   else if(mode==='verify-ok')deliver('PayAviatorAuthResult',Object.assign(base,{code:'VERIFY_EMAIL_REQUESTED',error:'Your account was created. PayAviator asked Firebase to send a verification email. Check inbox and spam. The app cannot see whether it arrived.'}));
   else deliver('PayAviatorAuthResult',Object.assign(base,{code:'',error:''}));
 },
 authSendEmailVerification:(id)=>{
   if(st.mode==='resend-fail')deliver('PayAviatorAuthResult',{requestId:id,ok:false,code:'VERIFY_EMAIL_FAILED',error:'Could not confirm the verification email was sent (status 403). Try again.'});
   else deliver('PayAviatorAuthResult',{requestId:id,ok:true,code:'',error:'',state:state(true)});
 },
 authReloadUser:(id)=>deliver('PayAviatorAuthResult',{requestId:id,ok:true,state:state(true)})
};
window.alert=window.confirm=window.prompt=function(){return false};
})()"""
BASE = """(()=>{localStorage.clear();localStorage.setItem('payAviator_onboarding_v1_done','1');localStorage.setItem('payaviator_tip_popup_seen_v1','1');localStorage.setItem('payaviator_security_tip_launch_count_v1','99');localStorage.setItem('payaviator_onboarding_choice_v1','account')})()"""

def boot(browser, mode):
    c = browser.new_context(viewport={'width': 390, 'height': 844}, is_mobile=True, has_touch=True)
    c.route(lambda u: not u.startswith('http://127.0.0.1') and not u.startswith('http://localhost'), lambda r: r.abort())
    c.add_init_script(MOCK)
    pg = c.new_page()
    errs = []
    pg.on('pageerror', lambda e: errs.append(str(e)))
    pg.goto(URL)
    pg.evaluate(BASE)
    pg.evaluate("window.__authCase.mode=%s" % repr(mode))
    pg.reload()
    pg.wait_for_timeout(800)
    pg.evaluate(BASE)
    pg.evaluate("window.__authCase.mode=%s" % repr(mode))
    return c, pg, errs

def msg_of(pg):
    return pg.evaluate("""(()=>{const s=[...document.querySelectorAll('#ppOnb section[data-onb]')].find(x=>!x.hidden);const m=s&&s.querySelector('[data-onb-msg]');return {screen:s&&s.dataset.onb,msg:(m&&m.textContent)||'',verify:!!document.getElementById('pa410VerifyDlg')?.open,status:(document.getElementById('pa410VerifyStatus')||{}).textContent||''}})()""")

with sync_playwright() as p:
    b = p.chromium.launch(executable_path='/usr/bin/google-chrome', args=['--no-sandbox'])
    c, pg, errs = boot(b, 'incomplete')
    pg.evaluate("window.PayAviatorAuthScreens.show('signin')")
    pg.locator('#ppOnb section[data-onb="signin"] [data-onb-act="google"]').tap()
    pg.wait_for_timeout(400)
    shown = msg_of(pg)
    check('incomplete Google shows a message', 'did not finish' in shown['msg'], shown)
    check('incomplete Google does not close as signed in', shown['screen'] == 'signin', shown)
    check('no page errors', not errs, errs)
    c.close()

    c, pg, errs = boot(b, 'blank')
    pg.evaluate("window.PayAviatorAuthScreens.show('welcome')")
    pg.locator('#ppOnb section[data-onb="welcome"] [data-onb-act="google"]').tap()
    pg.wait_for_timeout(400)
    shown = msg_of(pg)
    check('blank cancel is visible', 'did not finish' in shown['msg'] and shown['screen'] == 'welcome', shown)
    c.close()

    c, pg, errs = boot(b, 'collision')
    pg.evaluate("window.PayAviatorAuth.openSignIn()")
    pg.wait_for_timeout(200)
    pg.locator('#ppAuthGoogle').click()
    pg.wait_for_timeout(400)
    err = pg.locator('#ppAuthError').inner_text()
    check('existing password account is not a delete or link instruction', 'email and password' in err and 'was not linked' in err and 'delete' not in err.lower(), err)
    c.close()

    c, pg, errs = boot(b, 'ok')
    pg.evaluate("window.PayAviatorAuthScreens.show('signin')")
    pg.locator('#ppOnb section[data-onb="signin"] [data-onb-act="google"]').tap()
    pg.wait_for_timeout(500)
    check('successful Google still signs in', pg.evaluate("window.PayAviatorAuth.isSignedIn()") is True)
    c.close()

    c, pg, errs = boot(b, 'verify-fail')
    pg.evaluate("window.PayAviatorAuthScreens.show('create')")
    pg.fill('#ppOnbNewEmail', 'tester@gmail.com')
    pg.fill('#ppOnbNewPw', 'correct-horse')
    pg.fill('#ppOnbNewPw2', 'correct-horse')
    pg.locator('#ppOnb section[data-onb="create"] button[type="submit"]').tap()
    pg.wait_for_timeout(500)
    shown = msg_of(pg)
    check('failed verification send keeps the account message', 'created and kept' in shown['msg'] and 'could not confirm' in shown['msg'], shown)
    check('failed verification send opens resend', shown['verify'] is True, shown)
    check('failed verification send does not claim delivery', 'could not confirm' in shown['msg'] and 'Nothing was deleted' in shown['msg'], shown)
    c.close()

    c, pg, errs = boot(b, 'verify-ok')
    pg.evaluate("window.PayAviatorAuthScreens.show('create')")
    pg.fill('#ppOnbNewEmail', 'tester@gmail.com')
    pg.fill('#ppOnbNewPw', 'correct-horse')
    pg.fill('#ppOnbNewPw2', 'correct-horse')
    pg.locator('#ppOnb section[data-onb="create"] button[type="submit"]').tap()
    pg.wait_for_timeout(500)
    shown = msg_of(pg)
    check('accepted verification request does not claim delivery', 'cannot see whether it arrived' in shown['msg'] and shown['screen'] == 'bio', shown)
    note = pg.locator('#ppOnb section[data-onb="create"] .onb-note').text_content() or ''
    check('create note does not promise the email was sent', "We'll email" not in note and 'cannot see whether' in note, note)
    c.close()

    c, pg, errs = boot(b, 'resend-fail')
    pg.evaluate("window.PayAviatorAccountGate.openVerify()")
    pg.locator('[data-pa410-verify="send"]').tap()
    pg.wait_for_timeout(400)
    status = pg.locator('#pa410VerifyStatus').inner_text()
    check('resend failure is visible', 'not confirmed' in status or 'Could not' in status, status)
    check('resend control still exists', pg.locator('[data-pa410-verify="send"]').count() == 1)
    c.close()

print('ALL PASS' if ok else 'SOME FAILED')
sys.exit(0 if ok else 1)
