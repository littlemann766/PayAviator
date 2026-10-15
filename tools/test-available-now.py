#!/usr/bin/env python3
"""4.0.2 regression: Available now = spendable balances, one shared function on every screen.
Sample data: Chase Checking available 1,240.50 (current 1,302.75), Chase Savings available null
-> current 3,000.00, cash on hand 150.00; Capital One credit 812.33, Ally auto loan 9,400 and a
Fidelity brokerage 5,000 are excluded. 4.1.7: checking only by default (savings excluded unless the Include choice says so) -> expected 1,390.50.
Usage: test-available-now.py http://localhost:PORT/index.html  (needs Playwright + Chrome)."""
import sys, json
from playwright.sync_api import sync_playwright
URL=sys.argv[1]
def accts(chk_av=1240.5, sav_av=None):
    return [
     {'id':'acc-chk','name':'Checking','institutionName':'Chase','mask':'1111','type':'depository','subtype':'checking','source':'plaid','balances':{'available':chk_av,'current':1302.75}},
     {'id':'acc-sav','name':'Savings','institutionName':'Chase','mask':'2222','type':'depository','subtype':'savings','source':'plaid','balances':{'available':sav_av,'current':3000}},
     {'id':'acc-cc','name':'Quicksilver','institutionName':'Capital One','mask':'3333','type':'credit','subtype':'credit card','source':'plaid','balances':{'available':1187.67,'current':812.33,'limit':2000}},
     {'id':'acc-loan','name':'Auto Loan','institutionName':'Ally','mask':'4444','type':'loan','subtype':'auto','source':'plaid','balances':{'available':None,'current':9400}},
     {'id':'acc-inv','name':'Brokerage','institutionName':'Fidelity','mask':'5555','type':'investment','subtype':'brokerage','source':'plaid','balances':{'available':None,'current':5000}}]
BASE="""(()=>{localStorage.clear();localStorage.setItem('payAviator_v1',JSON.stringify([{id:'b-rent',name:'Rent',amount:1450,due:'2026-10-01',recurring:true,recurrence:'monthly',paid:false,color:'#3b82f6',category:'Housing',notes:''}]));
localStorage.setItem('payAviator_onboarding_v1_done','1');localStorage.setItem('payaviator_tip_popup_seen_v1','1');localStorage.setItem('payAviator_security_tip_launch_count_v1','99');
/* 4.1.2: Beth's Simple Home (setup-411) hides the Available now / Savings tiles; these checks are for Detailed Home. */
localStorage.setItem('payAviator_settings_v2',JSON.stringify({homeMode:'advanced'}))})()"""
ok=True
def check(name,cond,detail=''):
    global ok
    print(('PASS ' if cond else 'FAIL ')+name+(' '+str(detail) if detail else '')); ok=ok and cond
with sync_playwright() as p:
    b=p.chromium.launch(executable_path='/usr/bin/google-chrome',args=['--no-sandbox'])
    c=b.new_context(viewport={'width':390,'height':844},has_touch=True,is_mobile=True,timezone_id='America/New_York')
    c.route(lambda u:not u.startswith('http://localhost'),lambda r:r.abort())
    pg=c.new_page(); errs=[]; pg.on('pageerror',lambda e:errs.append(str(e)))
    pg.goto(URL); pg.wait_for_timeout(500); pg.evaluate(BASE); pg.reload(); pg.wait_for_timeout(3000)
    def seed(a,cash):
        # Seeded after load: signed-out start-up clears any cached bank data by design.
        pg.evaluate("([a,w])=>{localStorage.setItem('payaviator_connected_accounts_v1',JSON.stringify(a));if(w)localStorage.setItem('payaviator_cash_wallet_v950',JSON.stringify(w));else localStorage.removeItem('payaviator_cash_wallet_v950');window.dispatchEvent(new CustomEvent('payaviator:accounts-updated'));document.dispatchEvent(new CustomEvent('payaviator:gaugechange'));window.pp2059RenderGauge&&window.pp2059RenderGauge()}",[a,cash]); pg.wait_for_timeout(900)
    def screens():
        home=pg.evaluate("(()=>{const m=[...document.querySelectorAll('#pp2059GaugeMetrics .pp967-metric')].find(e=>/available now/i.test(e.textContent));return m&&m.innerText.replace(/\\s+/g,' ')})()")
        pg.evaluate("window.showFinancialSnapshot()"); pg.wait_for_timeout(400)
        snap=pg.evaluate("document.querySelector('[data-pa402-avail]')?.innerText.replace(/\\s+/g,' ')")
        pg.evaluate("document.getElementById('financialSnapshotDlg').close()")
        apis=pg.evaluate("[window.PayAviatorConnectedAccounts.availableBalance(),window.PayAviatorGauge924.availableNow(),window.PayAviatorCanonicalAvailableNow924(),window.mb20419MoneyState().available]")
        return home,snap,apis
    # 1. sample data
    seed(accts(),{'spendable':150,'saved':0}); a=pg.evaluate("window.PayAviatorAvailableNow()")
    check('sample total 1390.50 (checking + cash, no savings)',a['total']==1390.5,a['total'])
    check('counted: checking 1240.50 (available), cash 150; savings not counted',[(x['name'],x['amount']) for x in a['items']]==[('Chase Checking ••1111',1240.5),('Cash on hand',150)],a['items'])
    check('credit, loan, investment excluded',sorted(x['type'] for x in a['excluded'])==['credit','depository','investment','loan'])
    home,snap,apis=screens()
    check('Home shows $1,390.50',home and '$1,390.50' in home,home)
    check('Snapshot shows $1,390.50',snap and '$1,390.50' in snap and 'estimate' not in snap.lower(),snap)
    check('all APIs agree',all(abs(x-1390.5)<0.005 for x in apis),apis)
    # breakdown by tap
    pg.locator('#pp2059GaugeMetrics .pp967-metric').filter(has_text='Available now').first.tap(); pg.wait_for_timeout(500)
    bd=pg.evaluate("document.getElementById('pa402AvailDlg').open?document.getElementById('pa402AvailBody').innerText:''")
    check('tap opens breakdown listing each account',all(s in bd for s in ['Chase Checking','$1,240.50','Chase Savings','Cash on hand','$150.00','$1,390.50','Not counted']),bd.replace('\n',' | ')[:200])
    pg.evaluate("window.payAviatorHandleAndroidBack()"); pg.wait_for_timeout(300)
    check('Back closes breakdown',not pg.evaluate("document.getElementById('pa402AvailDlg').open"))
    # 2. empty-string available falls back to current; cash already in bank is not double counted
    seed(accts(chk_av=''),{'spendable':150,'saved':0,'inBankAccount':True}); t=pg.evaluate("window.PayAviatorAvailableNow().total")
    check('blank available -> current; cash in bank not double counted (1302.75 only)',t==1302.75,t)
    # 2b. 4.1.7: per-account Include/Exclude choice is honored (checking off, savings on)
    seed(accts(),{'spendable':150,'saved':0})
    pg.evaluate("localStorage.setItem('payaviator_account_choices_v920',JSON.stringify({'acc-chk':false,'acc-sav':true}))"); t=pg.evaluate("window.PayAviatorAvailableNow().total")
    check('toggle: checking excluded + savings included -> 3150',t==3150,t)
    pg.evaluate("localStorage.setItem('payaviator_account_choices_v920',JSON.stringify({'acc-cc':true,'acc-loan':true}))"); t=pg.evaluate("window.PayAviatorAvailableNow().total")
    check('toggle can never pull in credit/loan -> 1390.50',t==1390.5,t)
    pg.evaluate("localStorage.removeItem('payaviator_account_choices_v920')")
    # 3. negative real balance shows negative
    seed(accts(chk_av=-50.25,sav_av=0),None); t=pg.evaluate("window.PayAviatorAvailableNow().total"); home,snap,_=screens()
    check('negative checking -> -50.25',t==-50.25,t); check('Home shows negative',home and '50.25' in home and ('−' in home or '-' in home),home)
    # 4. nothing set up -> estimate, labelled
    seed([],None); a=pg.evaluate("window.PayAviatorAvailableNow()"); est=pg.evaluate("(()=>{const d=new Date();return window.PayAviatorMonthState985(d.getFullYear(),d.getMonth()).available})()")
    home,snap,_=screens()
    check('fallback estimate = paychecks - bills - spending',a['estimate'] and abs(a['total']-round(est,2))<0.005,(a['total'],est))
    check('estimate labelled on Home and Snapshot',home and 'est' in home.lower() and snap and 'estimate' in snap.lower(),(home,snap))
    check('no page errors',not errs,errs)
print('PASS' if ok else 'FAIL'); sys.exit(0 if ok else 1)
