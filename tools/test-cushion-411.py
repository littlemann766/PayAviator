#!/usr/bin/env python3
"""4.1.1 cushion default $0: new users 0; old auto preset (20% of paycheck, never user-set) reset to 0 on upgrade;
user-set cushions kept. Usage: test-cushion-411.py [http://localhost:8811/index.html]"""
import sys,json
from playwright.sync_api import sync_playwright
URL=sys.argv[1] if len(sys.argv)>1 else 'http://localhost:8811/index.html'
K='payaviator_money_settings_v20419'
PAY="localStorage.setItem('payAviator_paychecks_v1',JSON.stringify([{id:'p1',name:'Job',amount:954.5,date:new Date(Date.now()-3*864e5).toISOString().slice(0,10),frequency:'biweekly',recurring:true}]))"
cases=[('new user',None,0),
       ('auto preset persisted (20%, no user flag)',{'cushionMode':'percent','cushionPercent':20,'cushionDollar':100,'useSavings':True},0),
       ('user set 20% via Save Cushion',{'cushionMode':'percent','cushionPercent':20,'cushionDollar':100,'cushionUserSet':True},190.9),
       ('user set $75 (older build, no flag)',{'cushionMode':'dollar','cushionPercent':20,'cushionDollar':75},75),
       ('user set 10% (older build, no flag)',{'cushionMode':'percent','cushionPercent':10,'cushionDollar':100},95.45)]
ok=True
with sync_playwright() as p:
    b=p.chromium.launch(executable_path='/usr/bin/google-chrome',args=['--no-sandbox'])
    for name,store,want in cases:
        pg=b.new_page(); errs=[]; pg.on('pageerror',lambda e:errs.append(str(e)))
        pg.goto(URL); pg.evaluate("localStorage.clear();localStorage.setItem('payAviator_onboarding_v1_done','1');localStorage.setItem('payaviator_onboarding_choice_v1','guest')")
        pg.evaluate(PAY)
        if store is not None: pg.evaluate(f"localStorage.setItem('{K}',JSON.stringify({json.dumps(store)}))")
        pg.reload(); pg.wait_for_timeout(2500)
        got=pg.evaluate("Math.round(window.mb20419MoneyState().cushion*100)/100")
        good=abs(got-want)<0.01 and not errs; ok=ok and good
        print(('PASS ' if good else 'FAIL ')+name,'cushion',got,'want',want,errs or '')
        if name=='auto preset persisted (20%, no user flag)':
            pg.reload(); pg.wait_for_timeout(1500); g2=pg.evaluate("window.mb20419MoneyState().cushion"); s2=pg.evaluate(f"JSON.parse(localStorage.getItem('{K}'))")
            good=g2==0 and s2.get('useSavings')==True; ok=ok and good; print(('PASS ' if good else 'FAIL ')+'reset sticks, other settings kept',g2,s2)
        pg.close()
    # Fresh install + setup wizard with a $1,450 paycheck -> cushion $0 (4.0.2 gave 20% = $290)
    for vw,vh in [(390,844),(360,640)]:
        pg=b.new_page(viewport={'width':vw,'height':vh}); errs=[]; pg.on('pageerror',lambda e:errs.append(str(e)))
        pg.goto(URL); pg.evaluate("localStorage.clear()"); pg.reload(); pg.wait_for_timeout(2500)
        opened=pg.evaluate("!!document.getElementById('mb212Onboarding')?.open")
        pg.evaluate("""(()=>{const d=new Date(Date.now()-2*864e5).toISOString().slice(0,10);document.getElementById('mb216IncomeType').value='hourly';document.getElementById('mb212Wage').value='20';document.getElementById('mb212Frequency').value='biweekly';document.getElementById('mb212Payday').value=d;document.getElementById('mb212CheckAmount').value='1450';document.getElementById('mb212FinishAddBill').click()})()""")
        pg.wait_for_timeout(1200)
        pg.evaluate("document.querySelectorAll('dialog[open]').forEach(d=>d.close())")
        st=pg.evaluate("(()=>{const x=window.mb20419MoneyState();return [x.funding.amount,x.cushion,(window.PayAviatorGauge967?.state()||{}).cushion]})()")
        good=opened and st[0]==1450 and st[1]==0 and (st[2] in (0,None)) and not errs; ok=ok and good
        print(('PASS ' if good else 'FAIL ')+f'{vw}: fresh install + setup with $1,450 paycheck -> cushion $0','wizard',opened,'[paycheck, cushion, gauge cushion]',st,errs or '')
        pg.close()
    b.close()
print('ALL PASS' if ok else 'SOME FAILED'); sys.exit(0 if ok else 1)
