#!/usr/bin/env python3
"""4.1.3 verify-email loop regression. Uses a REAL throwaway Firebase email user: the mocked backend
gates create-link-token on the email_verified claim of the actual Firebase ID token the 'native' side holds.
Usage: test-verify-413.py URL USERJSON   (USERJSON = signUp response with idToken/refreshToken, user already verified)"""
import sys, json, base64, urllib.request
from playwright.sync_api import sync_playwright
URL,UJ=sys.argv[1],sys.argv[2]; K='AIzaSyAcMkfgXQps-FaRC-hbQzwFOiPRI1wlEPk'
u=json.load(open(UJ)); tok={'id':u['idToken']}   # stale token from before verification
def claim(t):
    p=t.split('.')[1]; p+='='*(-len(p)%4); return json.loads(base64.urlsafe_b64decode(p)).get('email_verified')
def refresh():
    r=urllib.request.urlopen(urllib.request.Request('https://securetoken.googleapis.com/v1/token?key='+K,
        data=('grant_type=refresh_token&refresh_token='+u['refreshToken']).encode(),headers={'Content-Type':'application/x-www-form-urlencoded'}))
    tok['id']=json.load(r)['id_token']; return claim(tok['id'])
def api(path):
    if path.startswith('/api/plaid/create-link-token'):
        return [200,{'link_token':'link-sandbox-test'}] if claim(tok['id']) is True else [403,{'error':'email_not_verified','code':'EMAIL_NOT_VERIFIED'}]
    return [200,{}]
MOCK="""(()=>{const st=window.__mock={v:false,calls:[]};
const deliver=(fn,o)=>setTimeout(()=>window[fn]&&window[fn](JSON.stringify(o)),20);
const state=()=>({available:true,googleAvailable:false,signedIn:true,uid:'u1',email:'t@x.co',provider:'password',emailVerified:st.v});
window.AndroidBridge={authGetState:()=>JSON.stringify(state()),
 apiRequest:(id,m,p,b)=>{st.calls.push(['API',p]);window.pyApi(p).then(([s,body])=>deliver('PayAviatorNativeApiResult',{requestId:id,status:s,body:JSON.stringify(body)}))},
 authSendEmailVerification:(id)=>{st.calls.push(['NATIVE','sendVerify']);deliver('PayAviatorAuthResult',{requestId:id,ok:true,state:state()})},
 authReloadUser:(id)=>{st.calls.push(['NATIVE','reload']);window.pyRefresh().then(v=>{st.v=!!v;deliver('PayAviatorAuthResult',{requestId:id,ok:true,state:state()})})},
 openPlaidLink:(t)=>{st.calls.push(['PLAID',t])},billingGetPurchases:()=>'[]'};
window.alert=window.confirm=window.prompt=function(){};})()"""
BASE="""(()=>{localStorage.clear();localStorage.setItem('payAviator_onboarding_v1_done','1');localStorage.setItem('payaviator_tip_popup_seen_v1','1');localStorage.setItem('payAviator_security_tip_launch_count_v1','99');localStorage.setItem('payaviator_onboarding_choice_v1','account')})()"""
ok=True
def check(n,c,d=''):
    global ok; print(('PASS ' if c else 'FAIL ')+n+(' '+str(d) if d else '')); ok=ok and bool(c)
with sync_playwright() as p:
    b=p.chromium.launch(executable_path='/usr/bin/google-chrome',args=['--no-sandbox'])
    def run(scenario):
        tok['id']=u['idToken']
        c=b.new_context(viewport={'width':390,'height':844},is_mobile=True,has_touch=True)
        c.route(lambda x:not x.startswith('http://localhost'),lambda r:r.abort())
        c.expose_function('pyApi',api); c.expose_function('pyRefresh',refresh)
        pg=c.new_page(); errs=[]; pg.on('pageerror',lambda e:errs.append(str(e)))
        pg.goto(URL); pg.evaluate(BASE); c.add_init_script(MOCK); pg.reload(); pg.wait_for_timeout(2500)
        pg.evaluate("window.PayAviatorPlaidConsent&&(window.PayAviatorPlaidConsent.ask=async()=>true)")  # consent screen is covered by its own tests
        check(scenario+': stale token really says email_verified=false',claim(tok['id']) is False)
        pg.evaluate("window.openPayAviatorConnectedAccounts920&&window.openPayAviatorConnectedAccounts920()"); pg.wait_for_timeout(1200)
        if scenario=='dialog':
            pg.evaluate("PayAviatorAccountGate.openVerify()"); pg.wait_for_timeout(200)
            check('button says "I verified, continue"',pg.locator('[data-pa410-verify="done"]').inner_text().strip()=='I verified, continue')
            pg.locator('[data-pa410-verify="send"]').tap(); pg.wait_for_timeout(300)
            pg.locator('[data-pa410-verify="send"]').tap(); pg.wait_for_timeout(300)
            sends=sum(1 for x in pg.evaluate("__mock.calls") if x==['NATIVE','sendVerify'])
            check('resend cooldown: 2 taps -> 1 email',sends==1 and 'resend in' in pg.inner_text('#pa410VerifyStatus'),sends)
            pg.locator('[data-pa410-verify="done"]').tap(); pg.wait_for_timeout(4000)
        elif scenario=='resume':
            pg.evaluate("PayAviatorAccountGate.openVerify()"); pg.wait_for_timeout(200)
            pg.evaluate("document.dispatchEvent(new Event('visibilitychange'))"); pg.wait_for_timeout(4000)
        else:  # verified in mail app, came back and tapped Connect bank directly
            pg.evaluate("window.PayAviatorConnectBank()"); pg.wait_for_timeout(5000)
        calls=pg.evaluate("__mock.calls")
        lt=[x for x in calls if x[0]=='API' and 'create-link-token' in x[1]]
        check(scenario+': reload + force refresh done',['NATIVE','reload'] in calls)
        check(scenario+': fresh token has email_verified=true',claim(tok['id']) is True)
        check(scenario+': create-link-token attempted after refresh and Plaid opened',len(lt)>=1 and any(x[0]=='PLAID' for x in calls),calls)
        check(scenario+': no auto-resend of verification email',sum(1 for x in calls if x==['NATIVE','sendVerify'])<=1)
        check(scenario+': verify dialog closed, no loop',not pg.evaluate("!!document.getElementById('pa410VerifyDlg')?.open"))
        check(scenario+': no page errors',not errs,errs); c.close()
    for s in ['direct','dialog','resume']: run(s)
print('ALL PASS' if ok else 'SOME FAILED'); sys.exit(0 if ok else 1)
