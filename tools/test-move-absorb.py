#!/usr/bin/env python3
"""4.0.1 regression: "only this date" then "all future dates" on the same Rent occurrence
must leave exactly one Rent on the new date (also after reload).
Usage: test-move-absorb.py http://localhost:PORT/index.html  (needs Playwright + Chrome)."""
import sys
from playwright.sync_api import sync_playwright
URL=sys.argv[1]
SEED="""(()=>{localStorage.clear();const D=s=>s;localStorage.setItem('payAviator_v1',JSON.stringify([{id:'b-rent',name:'Rent',amount:1450,due:'2026-10-01',recurring:true,recurrence:'monthly',paid:false,color:'#3b82f6',category:'Housing',notes:'',dateMoves:{}}]));
localStorage.setItem('payAviator_onboarding_v1_done','1');localStorage.setItem('payaviator_tip_popup_seen_v1','1');localStorage.setItem('payAviator_security_tip_launch_count_v1','99')})()"""
COUNT="""()=>{const out={};[9,10,11].forEach(m=>monthBillOccurrencesV47(2026,m,true).forEach(({b,iso})=>{if(/rent/i.test(b.name)){out[iso]=(out[iso]||0)+1}}));return out}"""
def edit(pg,iso,newdue,choice):
    pg.evaluate(f"window.editBillOccurrence('b-rent','{iso}')"); pg.wait_for_timeout(600)
    pg.fill('#due',newdue)
    pg.evaluate("v=>{document.getElementById('calendarRecurringEditMode').value=v}",{'only':'single','all':'future'}[choice])  # lives under 'More bill options'
    pg.locator('#dlg button[type=submit]').first.click(); pg.wait_for_timeout(900)
ok=True
with sync_playwright() as p:
    b=p.chromium.launch(executable_path='/usr/bin/google-chrome',args=['--no-sandbox'])
    c=b.new_context(viewport={'width':390,'height':844},timezone_id='America/New_York')
    pg=c.new_page(); errs=[]; pg.on('pageerror',lambda e:errs.append(str(e)))
    pg.goto(URL); pg.wait_for_timeout(500); pg.evaluate(SEED); pg.reload(); pg.wait_for_timeout(3000)
    edit(pg,'2026-11-01','2026-11-03','only'); a=pg.evaluate(COUNT)
    edit(pg,'2026-11-01','2026-11-03','all'); b2=pg.evaluate(COUNT)
    pg.reload(); pg.wait_for_timeout(3000); r=pg.evaluate(COUNT)
    print('after only:',a,'after all:',b2,'after reload:',r,'errors:',errs)
    for label,cnt in (('after all',b2),('after reload',r)):
        if cnt.get('2026-11-03')!=1 or cnt.get('2026-11-01') or cnt.get('2026-12-03')!=1 or cnt.get('2026-10-01')!=1:
            ok=False; print('FAIL',label,cnt)
    if errs: ok=False
print('PASS' if ok else 'FAIL'); sys.exit(0 if ok else 1)
