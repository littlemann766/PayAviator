#!/usr/bin/env python3
"""Ordinary account deletion. Mocked bridge only. No production user is deleted.
Usage: python3 tools/test-account-deletion.py http://127.0.0.1:PORT/index.html
"""
import sys
from playwright.sync_api import sync_playwright

URL = sys.argv[1]
MOCK = r"""(()=>{
const st=window.__mock={signedIn:true,uid:'u1',recent:true,calls:[],routes:{}};
const deliver=(fn,obj)=>setTimeout(()=>window[fn]&&window[fn](JSON.stringify(obj)),15);
const state=()=>({available:true,googleAvailable:false,signedIn:st.signedIn,uid:st.signedIn?st.uid:'',email:'a@b.co',emailVerified:true,provider:'password'});
window.AndroidBridge={
 authGetState:()=>JSON.stringify(state()),
 authDeleteAccount:(id)=>{
   st.calls.push(['NATIVE','authDeleteAccount',id]);
   if(!st.recent){deliver('PayAviatorAuthResult',{requestId:id,ok:false,code:'REQUIRES_RECENT_LOGIN',error:'For your security, sign in again, then delete your account.',state:state()});return}
   st.calls.push(['DELETE','/api/plaid/user','']);
   const r=st.routes['/api/plaid/user']||{status:200,body:{removed:0,failed_item_ids:[]}};
   if(r.status>=200&&r.status<300){
     st.signedIn=false;
     deliver('PayAviatorAuthResult',{requestId:id,ok:true,code:'',error:'',state:Object.assign(state(),{signedIn:false,reason:'account_deleted'})});
     deliver('PayAviatorAuthStateChanged',{available:true,signedIn:false,uid:'',reason:'account_deleted'});
   }else{
     const body=r.body||{};
     deliver('PayAviatorAuthResult',{requestId:id,ok:false,code:body.code||'DELETE_INCOMPLETE',error:body.error||'Your sign-in was not deleted. PayAviator could not finish removing every bank. Try again. Banks that were already removed stay removed. Nothing on this phone was erased.',state:state()});
   }
 },
 authSignOut:(id)=>{st.calls.push(['NATIVE','authSignOut']);st.signedIn=false;deliver('PayAviatorAuthResult',{requestId:id,ok:true,state:state()});deliver('PayAviatorAuthStateChanged',{available:true,signedIn:false,reason:'signed_out'})},
 authSignInWithEmail:(id)=>{st.calls.push(['NATIVE','authSignInWithEmail']);st.signedIn=true;st.uid='u2';deliver('PayAviatorAuthResult',{requestId:id,ok:true,state:{available:true,signedIn:true,uid:'u2',email:'b@c.co',emailVerified:true}})}
};
})()"""
BASE = """(()=>{localStorage.clear();localStorage.setItem('payAviator_onboarding_v1_done','1');localStorage.setItem('payaviator_tip_popup_seen_v1','1');localStorage.setItem('payAviator_security_tip_launch_count_v1','99');localStorage.setItem('payaviator_onboarding_choice_v1','account')})()"""
ACCTS = [
    {'id':'a1','name':'Checking','institutionName':'First National','itemId':'item-A','mask':'1111','type':'depository','subtype':'checking','available':10,'current':10,'source':'plaid'},
    {'id':'b1','name':'Checking','institutionName':'Second Credit Union','itemId':'item-B','mask':'2222','type':'depository','subtype':'checking','available':20,'current':20,'source':'plaid'},
]
ok = True

def check(name, cond, detail=''):
    global ok
    print(('PASS ' if cond else 'FAIL ') + name + ((' ' + str(detail)) if detail else ''))
    ok = ok and bool(cond)

def seed(pg, accounts):
    pg.evaluate("""(a)=>{localStorage.setItem('payaviator_connected_accounts_v1',JSON.stringify(a));localStorage.setItem('payAviator_v1',JSON.stringify([{id:'bill1',name:'Rent',amount:10}]));localStorage.setItem('payaviator_auth_uid_v1','u1')}""", accounts)

def ids(pg):
    return pg.evaluate("JSON.parse(localStorage.getItem('payaviator_connected_accounts_v1')||'[]').map(a=>a.id)")

def bill(pg):
    return pg.evaluate("JSON.parse(localStorage.getItem('payAviator_v1')||'[]')[0].id")

def open_delete(pg):
    pg.evaluate('__mock.calls=[]')
    pg.evaluate('window.openPayAviatorConnectedAccounts920()')
    pg.wait_for_timeout(350)
    pg.evaluate("document.querySelector('#pp920AccountsBody [data-ppauth-delete]').click()")
    pg.wait_for_timeout(200)

def confirm(pg):
    pg.evaluate("document.querySelector('#ppConfirm902 .pp902-remove').click()")
    pg.wait_for_timeout(400)

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
    check('policy version is 2026-11a', pg.evaluate('window.PayAviatorPlaidConsent.policyVersion')=='2026-11a')

    seed(pg, ACCTS)
    open_delete(pg)
    check('manage is offered beside delete', pg.evaluate("!!document.querySelector('#pp920AccountsBody [data-pp-manage-sub]')"))
    copy = pg.evaluate("document.querySelector('#ppConfirm902 .pp902-confirm-copy')?.textContent||''")
    fields = pg.evaluate("document.querySelectorAll('#ppConfirm902 textarea, #ppConfirm902 input').length")
    check('one confirmation explains billing and bank accounts', 'does not cancel Google Play or Stripe billing' in copy and 'they set the end date' in copy and 'does not close those accounts at the bank' in copy and 'is not required' in copy and 'do not need to give a reason' in copy.lower(), copy)
    check('confirmation has no survey fields', fields==0, fields)
    pg.evaluate("document.querySelector('#ppConfirm902 .pp902-cancel').click()")
    pg.wait_for_timeout(150)
    check('cancel does not delete', pg.evaluate('__mock.calls')==[] and ids(pg)==['a1','b1'], pg.evaluate('__mock.calls'))

    pg.evaluate('__mock.recent=false')
    open_delete(pg)
    confirm(pg)
    calls = pg.evaluate('__mock.calls')
    check('stale sign-in does not call bank deletion or sign-out', [c[1] for c in calls if c[0]=='NATIVE']==['authDeleteAccount'] and not any(c[0]=='DELETE' for c in calls), calls)
    check('stale sign-in keeps banks and the bill', ids(pg)==['a1','b1'] and bill(pg)=='bill1' and pg.evaluate('window.PayAviatorAuth.isSignedIn()') is True)
    notice = pg.evaluate("document.getElementById('ppAuthNotice')?.textContent||''")
    check('stale sign-in asks to sign in again before anything is removed', 'Nothing is removed until' in notice, notice)

    pg.evaluate("window.PayAviatorAuthStateChanged(JSON.stringify({available:true,signedIn:true,uid:'u2',email:'b@c.co',emailVerified:true}))")
    pg.wait_for_timeout(200)
    check('a different sign-in does not continue the delete', pg.evaluate('__mock.calls.filter(c=>c[1]==="authDeleteAccount").length')==1)

    pg.evaluate("window.PayAviatorAuthStateChanged(JSON.stringify({available:true,signedIn:true,uid:'u1',email:'a@b.co',emailVerified:true}))")
    pg.wait_for_timeout(200)
    seed(pg, ACCTS)
    pg.evaluate('__mock.recent=true; __mock.routes["/api/plaid/user"]={status:502,body:{removed:1,failed_item_ids:["item-B"]}}')
    open_delete(pg)
    confirm(pg)
    check('partial failure keeps the sign-in and local banks', pg.evaluate('window.PayAviatorAuth.isSignedIn()') is True and ids(pg)==['a1','b1'] and bill(pg)=='bill1', ids(pg))
    check('partial failure does not sign out', 'authSignOut' not in [c[1] for c in pg.evaluate('__mock.calls')])
    check('partial failure says the sign-in was not deleted', 'sign-in was not deleted' in pg.evaluate('document.body.innerText').lower())

    pg.evaluate('__mock.routes["/api/plaid/user"]={status:403,body:{error:"Forbidden.",code:"USER_MISMATCH"}}')
    open_delete(pg)
    confirm(pg)
    paths = [c[1] for c in pg.evaluate('__mock.calls') if c[0]=='DELETE']
    check('delete uses only /api/plaid/user', paths==['/api/plaid/user'], paths)
    check('other-user rejection keeps local banks', ids(pg)==['a1','b1'] and pg.evaluate('window.PayAviatorAuth.isSignedIn()') is True)

    seed(pg, [])
    pg.evaluate('__mock.routes["/api/plaid/user"]={status:200,body:{removed:0,failed_item_ids:[]}}')
    open_delete(pg)
    confirm(pg)
    check('no banks still deletes the sign-in', pg.evaluate('window.PayAviatorAuth.isSignedIn()') is False)
    check('no banks still keeps the typed bill', bill(pg)=='bill1')
    check('success does not say billing was cancelled', 'did not cancel Google Play or Stripe billing' in pg.evaluate('document.body.innerText'))

    pg.evaluate("window.PayAviatorAuthStateChanged(JSON.stringify({available:true,signedIn:true,uid:'u1',email:'a@b.co',emailVerified:true}))")
    pg.wait_for_timeout(200)
    seed(pg, ACCTS)
    pg.evaluate('__mock.recent=true; __mock.signedIn=true; __mock.routes["/api/plaid/user"]={status:200,body:{removed:2,failed_item_ids:[]}}')
    open_delete(pg)
    copy = pg.evaluate("document.querySelector('#ppConfirm902 .pp902-confirm-copy')?.textContent||''")
    check('active plus wording does not require cancel', 'is not required' in copy and 'must cancel' not in copy.lower())
    confirm(pg)
    check('delete with banks signs out only after success', pg.evaluate('window.PayAviatorAuth.isSignedIn()') is False and ids(pg)==[] and bill(pg)=='bill1', ids(pg))
    check('no page errors at end', not errs, errs)
    browser.close()

print('ACCOUNT DELETION ' + ('PASS' if ok else 'FAIL'))
sys.exit(0 if ok else 1)
