#!/usr/bin/env python3
"""4.1.9: a live bank sync must replace the cached nested `balances` (4.1.5-4.1.8 kept the balances saved at connect time, so Available now / Safe to spend stayed stale).
Usage: test-stale-balances-419.py URL"""
import sys, json
from playwright.sync_api import sync_playwright
URL=sys.argv[1]; ok=True
def check(n,c,d=''):
    global ok; print(('PASS ' if c else 'FAIL ')+n+(' '+str(d) if d else '')); ok=ok and bool(c)
with sync_playwright() as p:
    b=p.chromium.launch(executable_path='/usr/bin/google-chrome',args=['--no-sandbox']); c=b.new_context(); pg=c.new_page()
    fresh={'accounts':[{'account_id':'a1','name':'Checking','institution_name':'Bank','mask':'1111','type':'depository','subtype':'checking','balances':{'available':14.93,'current':14.93}}],'items':[],'errors':[]}
    def route(r):
        u=r.request.url
        if '/api/plaid/accounts' in u: return r.fulfill(status=200,content_type='application/json',headers={'access-control-allow-origin':'*'},body=json.dumps(fresh))
        if '/api/plaid/transactions' in u: return r.fulfill(status=200,content_type='application/json',headers={'access-control-allow-origin':'*'},body='{"transactions":[]}')
        if u.startswith('http://localhost'): return r.continue_()
        r.abort()
    c.route('**/*',route)
    pg.goto(URL); pg.wait_for_timeout(3000)
    # stale cache from connect time: nested balances 108.55
    pg.evaluate("localStorage.setItem('payaviator_connected_accounts_v1',JSON.stringify([{id:'a1',name:'Checking',institution:'Bank',institutionName:'Bank',mask:'1111',type:'depository',subtype:'checking',current:108.55,available:108.55,balances:{available:108.55,current:108.55},source:'plaid'}]))")
    before=pg.evaluate("window.PayAviatorAvailableNow().total"); check('stale cache reads 108.55 before sync',before==108.55,before)
    r=pg.evaluate("""(async()=>{try{window.PayAviatorAuth.isSignedIn=()=>true}catch(e){};try{await window.PayAviatorSyncLiveBank982();}catch(e){return 'ERR '+e.message}return window.PayAviatorAvailableNow().total})()""")
    check('after live sync Available now = 14.93',r==14.93,r)
print('PASS' if ok else 'FAIL'); sys.exit(0 if ok else 1)
