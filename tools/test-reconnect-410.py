#!/usr/bin/env python3
"""4.1.0 reconnect banner (Beth's PayAviatorReconnect) wired to item health and pp920ReconnectItem.
Usage: test-reconnect-410.py http://localhost:PORT/index.html [shotdir]"""
import sys, os, json
from playwright.sync_api import sync_playwright
URL=sys.argv[1]; SHOTS=sys.argv[2] if len(sys.argv)>2 else None
src=open(os.path.join(os.path.dirname(os.path.abspath(__file__)),'test-accounts-410.py')).read()
MOCK=src.split('MOCK="""')[1].split('"""')[0]; BASE=src.split('BASE="""')[1].split('"""')[0]
HEALTH={'items':[{'item_id':'it1','institution_name':'Chase','needs_update':True,'new_accounts_available':True,'error_code':'ITEM_LOGIN_REQUIRED'},
                 {'item_id':'it2','institution_name':'Ally','needs_update':True,'new_accounts_available':True},
                 {'item_id':'it3','institution_name':'Capital One','needs_update':False}],
        'errors':[{'item_id':'it1','institution_name':'Chase','needs_update':True,'code':'ITEM_LOGIN_REQUIRED'}]}
ACCTS=[{'id':'a1','name':'Checking','institution':'Chase','institutionName':'Chase','itemId':'it1','type':'depository','subtype':'checking','source':'plaid','balances':{'available':10,'current':10},'current':10,'available':10},
       {'id':'a2','name':'Savings','institution':'Ally','institutionName':'Ally','itemId':'it2','type':'depository','subtype':'savings','source':'plaid','balances':{'available':5,'current':5},'current':5,'available':5}]
ok=True
def check(n,c,d=''):
    global ok; print(('PASS ' if c else 'FAIL ')+n+(' '+str(d) if d else '')); ok=ok and bool(c)
CARDS="[...document.querySelectorAll('#paRcHome .pa-rc')].map(c=>[c.dataset.rcBank,c.dataset.reason,c.querySelector('.pa-rc-sub').textContent])"
with sync_playwright() as p:
    b=p.chromium.launch(executable_path='/usr/bin/google-chrome',args=['--no-sandbox'])
    for W,H in [(390,844),(360,640)]:
        print('== viewport',W,H)
        def page(signed,q=''):
            c=b.new_context(viewport={'width':W,'height':H},has_touch=True,is_mobile=True)
            c.route(lambda u:not u.startswith('http://localhost'),lambda r:r.abort())
            pg=c.new_page(); pg.errs=[]; pg.on('pageerror',lambda e:pg.errs.append(str(e)))
            pg.goto(URL); pg.evaluate(BASE); pg.evaluate("localStorage.setItem('payaviator_onboarding_choice_v1','account')")
            c.add_init_script(MOCK%('true' if signed else 'false'))
            pg.goto(URL+q); pg.wait_for_timeout(2500); return c,pg
        for q,reason,title in [('?reconnect=login','login','Reconnect your bank'),('?reconnect=new','new_accounts','New accounts found')]:
            c,pg=page(False,q); cards=pg.evaluate(CARDS)
            check(f'preview {q}: one {reason} card',len(cards)==1 and cards[0][1]==reason and title in pg.inner_text('#paRcHome'),cards)
            if SHOTS: pg.screenshot(path=os.path.join(SHOTS,f'boss-410-{W}x{H}-11-reconnect-{reason}.png'))
            check('no page errors',not pg.errs,pg.errs); c.close()
        # real wiring from item health
        c,pg=page(True)
        pg.evaluate("([h,a])=>{__mock.routes['/api/plaid/accounts']={status:200,body:{accounts:[],items:h.items,errors:h.errors}};localStorage.setItem('payaviator_connected_accounts_v1',JSON.stringify(a));window.PayAviatorSavePlaidItemHealth(h)}",[HEALTH,ACCTS]); pg.wait_for_timeout(500)
        cards=pg.evaluate(CARDS)
        check('one card per item needing update (Chase, Ally); healthy item none',sorted(x[0] for x in cards)==['it1','it2'],cards)
        check("login wins over new_accounts for Chase",[x[1] for x in cards if x[0]=='it1']==['login'],cards)
        check('Ally new_accounts',[x[1] for x in cards if x[0]=='it2']==['new_accounts'],cards)
        check('names match accounts list',any('Chase' in x[2] for x in cards) and any('Ally' in x[2] for x in cards),cards)
        pg.evaluate("window.openPayAviatorConnectedAccounts920()"); pg.wait_for_timeout(1500)
        dup=pg.evaluate("[document.querySelectorAll('#pp920AccountsBody .ppauth-needs').length,document.querySelectorAll('#pp920AccountsBody .pa-rc').length]")
        check('Accounts: no old needs-attention card, banner cards only',dup[0]==0 and dup[1]==2,dup)
        pg.evaluate("document.querySelector('#pp920AccountsModal .pp920-close')?.click()"); pg.wait_for_timeout(500)
        pg.evaluate("localStorage.setItem('payaviator_plaid_consent_v1',JSON.stringify({acceptedAt:new Date().toISOString(),policyVersion:'2026-10b',context:'connect'}))")
        pg.evaluate("__mock.routes['/api/plaid/update-link-token']={status:200,body:{link_token:'link-sandbox-upd'}};window.AndroidBridge.openPlaidLink=t=>__mock.calls.push(['NATIVE','openPlaidLink',t])")
        pg.locator('#paRcHome [data-rc-go="it1"]').first.tap(); pg.wait_for_timeout(1200)
        if pg.evaluate("!!document.getElementById('ppConsentSheet')?.classList.contains('show')"):
            pg.evaluate("document.getElementById('ppConsentContinue')?.click()"); pg.wait_for_timeout(1000)
        calls=pg.evaluate("__mock.calls")
        upd=[x for x in calls if x[1]=='/api/plaid/update-link-token']
        check('Reconnect -> update-link-token for that item',upd and json.loads(upd[-1][2])=={'item_id':'it1'},upd)
        check('opens Plaid in update mode',['NATIVE','openPlaidLink','link-sandbox-upd'] in calls)
        pg.evaluate("window.PayAviatorReconnect.clear('it1')"); pg.wait_for_timeout(300)
        check('clear removes the card',[x[0] for x in pg.evaluate(CARDS)]==['it2'])
        pg.evaluate("window.PayAviatorAuthStateChanged(JSON.stringify({available:true,signedIn:false,reason:'signed_out'}))"); pg.wait_for_timeout(500)
        check('signed out -> no cards',pg.evaluate(CARDS)==[])
        check('no page errors (wired)',not pg.errs,pg.errs); c.close()
    print('RECONNECT410 '+('PASS' if ok else 'FAIL')); sys.exit(0 if ok else 1)
