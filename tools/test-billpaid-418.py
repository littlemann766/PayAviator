#!/usr/bin/env python3
"""4.1.8: billPaidAmount honors override.paid; {deleted}/{paid:false} overrides don't make a bill paid. Usage: test-billpaid-418.py URL"""
import sys
from playwright.sync_api import sync_playwright
URL=sys.argv[1]; ok=True
def check(n,c,d=''):
    global ok; print(('PASS ' if c else 'FAIL ')+n+(' '+str(d) if d else '')); ok=ok and bool(c)
with sync_playwright() as p:
    b=p.chromium.launch(executable_path='/usr/bin/google-chrome',args=['--no-sandbox']); pg=b.new_context().new_page(); pg.route(lambda u:not u.startswith('http://localhost'),lambda r:r.abort())
    pg.goto(URL); pg.wait_for_timeout(3000)
    r=pg.evaluate("""(()=>{const bill={id:'t1',amount:100,paid:false};const out={};
      billOverrides={};billPaidAmounts={};out.none=billPaidAmount(bill,'2026-10-01');
      billOverrides['t1|2026-10-01']={paid:false};out.paidFalse=billPaidAmount(bill,'2026-10-01');
      billOverrides['t1|2026-10-02']={deleted:true,movedTo:'2026-10-09'};out.deleted=billPaidAmount(bill,'2026-10-02');
      billOverrides['t1|2026-10-03']={paid:true};out.paidTrue=billPaidAmount(bill,'2026-10-03');
      billPaidAmounts['t1|2026-10-04']=40;out.partial=billPaidAmount(bill,'2026-10-04');
      return out})()""")
    check('no entry -> unpaid',r['none']==0,r); check('{paid:false} -> unpaid',r['paidFalse']==0); check('{deleted,movedTo} -> unpaid',r['deleted']==0); check('{paid:true} -> full',r['paidTrue']==100); check('paid amount 40 -> partial',r['partial']==40)
print('PASS' if ok else 'FAIL'); sys.exit(0 if ok else 1)
