#!/usr/bin/env python3
"""Item-level bank removal with a mocked bridge. No production calls.

Usage: python3 tools/test-bank-removal.py http://127.0.0.1:PORT/index.html
"""
import json
import sys
from playwright.sync_api import sync_playwright

URL = sys.argv[1]
MOCK = r"""(()=>{
const st=window.__mock={signedIn:true,uid:'u1',calls:[],routes:{}};
const deliver=(fn,obj)=>setTimeout(()=>window[fn]&&window[fn](JSON.stringify(obj)),15);
const state=()=>({available:true,googleAvailable:false,signedIn:st.signedIn,uid:st.signedIn?st.uid:'',email:'a@b.co',emailVerified:true,provider:'password'});
window.AndroidBridge={
 authGetState:()=>JSON.stringify(state()),
 apiRequest:(id,m,p,b)=>{st.calls.push([m,p,b||'']);const path=String(p).split('?')[0];const r=st.routes[path]||{status:200,body:{disconnected:true}};deliver('PayAviatorNativeApiResult',{requestId:id,status:r.status,body:JSON.stringify(r.body)})},
 authDeleteAccount:(id)=>{st.calls.push(['NATIVE','authDeleteAccount']);deliver('PayAviatorAuthResult',{requestId:id,ok:false,code:'REQUIRES_RECENT_LOGIN',error:'sign in again',state:state()})},
 authSignOut:(id)=>{st.calls.push(['NATIVE','authSignOut']);st.signedIn=false;deliver('PayAviatorAuthResult',{requestId:id,ok:true,state:state()})}
};
window.alert=window.confirm=window.prompt=function(){window.__native=(window.__native||0)+1};
})()"""
BASE = """(()=>{localStorage.clear();localStorage.setItem('payAviator_onboarding_v1_done','1');localStorage.setItem('payaviator_tip_popup_seen_v1','1');localStorage.setItem('payAviator_security_tip_launch_count_v1','99');localStorage.setItem('payaviator_onboarding_choice_v1','account')})()"""
ACCTS = [
    {'id': 'chk-a', 'name': 'Checking', 'institutionName': 'First National', 'institution': 'First National', 'itemId': 'item-A', 'mask': '1111', 'type': 'depository', 'subtype': 'checking', 'available': 100, 'current': 100, 'source': 'plaid'},
    {'id': 'sav-a', 'name': 'Savings', 'institutionName': 'First National', 'institution': 'First National', 'itemId': 'item-A', 'mask': '2222', 'type': 'depository', 'subtype': 'savings', 'available': 50, 'current': 50, 'source': 'plaid'},
    {'id': 'cc-a', 'name': 'Visa', 'institutionName': 'First National', 'institution': 'First National', 'itemId': 'item-A', 'mask': '4242', 'type': 'credit', 'subtype': 'credit card', 'available': 0, 'current': 20, 'source': 'plaid'},
    {'id': 'chk-b', 'name': 'Checking', 'institutionName': 'Second Credit Union', 'institution': 'Second Credit Union', 'itemId': 'item-B', 'mask': '3333', 'type': 'depository', 'subtype': 'checking', 'available': 80, 'current': 80, 'source': 'plaid'},
]
TX = [
    {'transaction_id': 't-a', 'item_id': 'item-A', 'account_id': 'chk-a', 'name': 'Coffee', 'amount': 4},
    {'transaction_id': 't-b', 'item_id': 'item-B', 'account_id': 'chk-b', 'name': 'Groceries', 'amount': 10},
]
BILL = [{'id': 'bill1', 'name': 'Rent', 'amount': 900, 'due': '2026-12-01'}]
ok = True

def check(name, cond, detail=''):
    global ok
    print(('PASS ' if cond else 'FAIL ') + name + ((' ' + str(detail)) if detail else ''))
    ok = ok and bool(cond)

def ids(pg):
    return pg.evaluate("""()=>JSON.parse(localStorage.getItem('payaviator_connected_accounts_v1')||'[]').map(a=>a.id)""")

def seed(pg):
    pg.evaluate("""([a,tx,bill])=>{
      localStorage.setItem('payaviator_connected_accounts_v1', JSON.stringify(a));
      localStorage.setItem('payaviator_bank_transactions_v954', JSON.stringify(tx));
      localStorage.setItem('payaviator_imported_transactions_v1', JSON.stringify(tx));
      localStorage.setItem('payAviator_v1', JSON.stringify(bill));
      localStorage.removeItem('payaviator_removed_plaid_items_v1');
    }""", [ACCTS, TX, BILL])

def open_bank(pg, name):
    pg.evaluate("window.openPayAviatorConnectedAccounts920()")
    pg.wait_for_timeout(400)
    pg.evaluate("""(name)=>{const b=[...document.querySelectorAll('#pp920AccountsBody .pp920-bankhead')].find(x=>x.innerText.includes(name)); b&&b.click()}""", name)
    pg.wait_for_timeout(200)

def confirm_text(pg):
    return pg.evaluate("document.querySelector('#ppConfirm902 .pp902-confirm-copy')?.textContent||''")

def click_confirm(pg):
    pg.evaluate("document.querySelector('#ppConfirm902 .pp902-remove')?.click()")
    pg.wait_for_timeout(400)

with sync_playwright() as p:
    browser = p.chromium.launch(executable_path='/usr/bin/google-chrome', args=['--no-sandbox'])
    ctx = browser.new_context(viewport={'width': 390, 'height': 844}, has_touch=True, is_mobile=True)
    ctx.route(lambda u: not u.startswith('http://127.0.0.1') and not u.startswith('http://localhost'), lambda r: r.abort())
    pg = ctx.new_page()
    errs = []
    pg.on('pageerror', lambda e: errs.append(str(e)))
    pg.goto(URL)
    pg.evaluate(BASE)
    ctx.add_init_script(MOCK)
    pg.reload()
    pg.wait_for_timeout(2500)
    check('no page errors on load', not errs, errs)
    check('consent version is 2026-11a', pg.evaluate("window.PayAviatorPlaidConsent?.policyVersion")=='2026-11a')
    check('draft version is not recorded', pg.evaluate("window.PayAviatorPlaidConsent?.policyVersion")!='2026-11a-draft')

    seed(pg)
    pg.evaluate("__mock.routes['/api/plaid/items/item-A']={status:200,body:{disconnected:true}}")
    open_bank(pg, 'First National')
    labels = pg.evaluate("[...document.querySelectorAll('#pp920AccountsBody [data-pp920-remove-item]')].map(b=>[b.getAttribute('data-pp920-remove-item'), b.textContent])")
    check('item A is one control for all three accounts', ['item-A', 'Remove this bank (3 accounts)'] in labels, labels)
    check('item B keeps its own control', ['item-B', 'Remove this bank'] in labels, labels)
    check('no per-account Disconnect button', pg.evaluate("document.querySelectorAll('#pp920AccountsBody [data-pp920-remove]').length")==0)
    pg.evaluate("document.querySelector('#pp920AccountsBody [data-pp920-remove-item=\"item-A\"]').click()")
    pg.wait_for_timeout(200)
    copy = confirm_text(pg)
    check('confirm names checking, savings, and the card', 'Checking' in copy and 'Savings' in copy and 'Visa' in copy, copy)
    check('confirm says other banks and the bank account stay', 'Other banks stay' in copy and 'does not close the account at the bank' in copy, copy)
    check('confirm does not ask for a reason', 'reason' not in copy.lower())
    pg.evaluate("document.querySelector('#ppConfirm902 .pp902-cancel').click()")
    pg.wait_for_timeout(150)
    check('cancel does not call the server', not any(c[0]=='DELETE' for c in pg.evaluate("__mock.calls")))
    check('cancel keeps every account', ids(pg)==['chk-a','sav-a','cc-a','chk-b'], ids(pg))

    pg.evaluate("document.querySelector('#pp920AccountsBody [data-pp920-remove-item=\"item-A\"]').click()")
    pg.wait_for_timeout(150)
    click_confirm(pg)
    deletes = [c for c in pg.evaluate("__mock.calls") if c[0]=='DELETE']
    check('success calls DELETE for item A only', deletes==[['DELETE','/api/plaid/items/item-A','']], deletes)
    check('item A accounts are gone and item B remains', ids(pg)==['chk-b'], ids(pg))
    check('manual bill remains', pg.evaluate("JSON.parse(localStorage.getItem('payAviator_v1'))[0].id")=='bill1')
    check('still signed in', pg.evaluate("window.PayAviatorAuth.isSignedIn()")==True)
    txs = pg.evaluate("JSON.parse(localStorage.getItem('payaviator_bank_transactions_v954')).map(t=>t.transaction_id)")
    check('item A transactions purged and item B transactions kept', txs==['t-b'], txs)
    tomb = pg.evaluate("JSON.parse(localStorage.getItem('payaviator_removed_plaid_items_v1'))")
    check('tombstone is stored under this user only', tomb=={'u1':['item-A']}, tomb)

    stale_accounts = [
        {'account_id':'chk-a','name':'Checking','institution_name':'First National','item_id':'item-A','mask':'1111','type':'depository','subtype':'checking','balances':{'available':100,'current':100}},
        {'account_id':'sav-a','name':'Savings','institution_name':'First National','item_id':'item-A','mask':'2222','type':'depository','subtype':'savings','balances':{'available':50,'current':50}},
        {'account_id':'cc-a','name':'Visa','institution_name':'First National','item_id':'item-A','mask':'4242','type':'credit','subtype':'credit card','balances':{'available':0,'current':20}},
        {'account_id':'chk-b','name':'Checking','institution_name':'Second Credit Union','item_id':'item-B','mask':'3333','type':'depository','subtype':'checking','balances':{'available':80,'current':80}},
    ]
    stale_items = [
        {'item_id':'item-A','institution_name':'First National','needs_update':True,'error_code':'ITEM_LOGIN_REQUIRED'},
        {'item_id':'item-B','institution_name':'Second Credit Union','needs_update':False},
    ]
    pg.evaluate("""([accounts,items,tx])=>{
      __mock.routes['/api/plaid/accounts']={status:200,body:{accounts,items,errors:[]}};
      __mock.routes['/api/plaid/transactions']={status:200,body:{transactions:tx,errors:[]}};
    }""", [stale_accounts, stale_items, TX])
    pg.evaluate("window.PayAviatorSyncLiveBank982()")
    pg.wait_for_timeout(500)
    check('stale sync does not resurrect item A', ids(pg)==['chk-b'], ids(pg))
    health = pg.evaluate("JSON.parse(localStorage.getItem('payaviator_plaid_items_v1')).items.map(i=>i.item_id)")
    check('stale item health does not restore reconnect for item A', health==['item-B'], health)
    pg.evaluate("""()=>{window.PayAviatorAuthStateChanged(JSON.stringify({available:true,signedIn:true,uid:'u2',email:'b@c.co',emailVerified:true,provider:'password'}))}""")
    pg.wait_for_timeout(200)
    pg.evaluate("window.PayAviatorSyncLiveBank982()")
    pg.wait_for_timeout(500)
    after_other = ids(pg)
    check('a different user is not filtered by the first user tombstone', 'chk-a' in after_other and 'chk-b' in after_other, after_other)
    pg.evaluate("""()=>{window.PayAviatorAuthStateChanged(JSON.stringify({available:true,signedIn:true,uid:'u1',email:'a@b.co',emailVerified:true,provider:'password',reason:'signed_in'}))}""")
    pg.wait_for_timeout(300)

    seed(pg)
    pg.evaluate("__mock.calls=[]; __mock.routes['/api/plaid/items/item-A']={status:502,body:{error:'Could not disconnect this bank right now. Please try again.',code:'DISCONNECT_FAILED'}}")
    open_bank(pg, 'First National')
    pg.evaluate("document.querySelector('#pp920AccountsBody [data-pp920-remove-item=\"item-A\"]').click()")
    click_confirm(pg)
    check('failure keeps all four accounts', ids(pg)==['chk-a','sav-a','cc-a','chk-b'], ids(pg))
    check('failure does not write a tombstone', pg.evaluate("localStorage.getItem('payaviator_removed_plaid_items_v1')") in (None, 'null'))
    check('failure message says the bank is still connected', 'still connected' in pg.evaluate("document.body.innerText"))
    pg.evaluate("document.querySelector('#pp920AccountsBody [data-pp920-remove-item=\"item-A\"]').click()")
    click_confirm(pg)
    n = len([c for c in pg.evaluate("__mock.calls") if c[0]=='DELETE' and c[1]=='/api/plaid/items/item-A'])
    check('retry sends DELETE again', n==2, n)

    seed(pg)
    pg.evaluate("__mock.calls=[]; __mock.routes['/api/plaid/items/item-A']={status:403,body:{error:'Forbidden.',code:'USER_MISMATCH'}}")
    open_bank(pg, 'First National')
    pg.evaluate("document.querySelector('#pp920AccountsBody [data-pp920-remove-item=\"item-A\"]').click()")
    click_confirm(pg)
    check('403 does not purge any bank', ids(pg)==['chk-a','sav-a','cc-a','chk-b'], ids(pg))
    check('no per-account delete route is called', not any('/api/plaid/accounts/' in c[1] and c[0]=='DELETE' for c in pg.evaluate("__mock.calls")))

    seed(pg)
    pg.evaluate("__mock.calls=[]; __mock.routes['/api/plaid/items/item-A']={status:200,body:{ok:true}}")
    open_bank(pg, 'First National')
    pg.evaluate("document.querySelector('#pp920AccountsBody [data-pp920-remove-item=\"item-A\"]').click()")
    click_confirm(pg)
    check('200 without disconnected:true does not purge', ids(pg)==['chk-a','sav-a','cc-a','chk-b'], ids(pg))

    seed(pg)
    pg.evaluate("document.body.insertAdjacentHTML('beforeend','<button id=\"ccTap\" class=\"pp9163-disconnect\" data-pp9163-id=\"cc-a\" data-pp9163-mask=\"4242\">card</button>')")
    pg.evaluate("document.getElementById('ccTap').click()")
    pg.wait_for_timeout(200)
    card_copy = confirm_text(pg)
    check('credit card control confirms the whole connection', 'Remove this bank?' in pg.evaluate("document.querySelector('#ppConfirm902 .pp902-confirm-title')?.textContent||''") and 'Checking' in card_copy and 'Savings' in card_copy, card_copy)
    check('credit card control did not drop the local card before confirm', 'cc-a' in ids(pg))
    pg.evaluate("document.querySelector('#ppConfirm902 .pp902-cancel').click()")

    before = ids(pg)
    pg.evaluate("window.PayAviatorAuth.deleteAccount()")
    pg.wait_for_timeout(400)
    native = pg.evaluate("__mock.calls.filter(c=>c[0]==='NATIVE')")
    check('stale sign-in does not call authSignOut', ['NATIVE','authDeleteAccount'] in native and ['NATIVE','authSignOut'] not in native, native)
    check('banks remain until deletion actually runs', ids(pg)==before, ids(pg))
    notice = pg.evaluate("document.getElementById('ppAuthNotice')?.textContent||''")
    check('reauth notice does not ask for a reason', 'do not need to give a reason' in notice.lower() and 'banks stay' in notice.lower(), notice)
    check('no page errors', not errs, errs)
    browser.close()

print('BANK REMOVAL ' + ('PASS' if ok else 'FAIL'))
sys.exit(0 if ok else 1)
