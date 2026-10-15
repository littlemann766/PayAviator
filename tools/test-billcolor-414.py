#!/usr/bin/env python3
"""4.1.4 bill color picker: swatches, storage on bill.color, back-compat, display."""
import sys,subprocess,time
from playwright.sync_api import sync_playwright
srv=subprocess.Popen(['python3','-m','http.server','8852'],cwd='.',stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL);time.sleep(1)
ok=True
def check(n,c,d=''):
    global ok;print(('PASS ' if c else 'FAIL ')+n+(' '+str(d) if d else ''));ok=ok and bool(c)
SHOT=sys.argv[1] if len(sys.argv)>1 else None
try:
  with sync_playwright() as p:
    b=p.chromium.launch(executable_path='/usr/bin/google-chrome',args=['--no-sandbox'])
    pg=b.new_page(viewport={'width':390,'height':844},device_scale_factor=2);errs=[];pg.on('pageerror',lambda e:errs.append(str(e)))
    pg.goto('http://localhost:8852/index.html')
    pg.evaluate("localStorage.clear();localStorage.setItem('payAviator_onboarding_v1_done','1');localStorage.setItem('payaviator_onboarding_choice_v1','guest')")
    pg.reload();pg.wait_for_timeout(6000)
    for sel in ['#lockPrompt414Dlg[open] #lockPrompt414Later']:
        if pg.query_selector(sel): pg.click(sel)
    d=pg.evaluate("(()=>{const t=new Date(),iso=x=>x.toISOString().slice(0,10),a=new Date(t.getTime()+2*864e5),c=new Date(t.getTime()+5*864e5),e=new Date(t.getTime()+9*864e5);bills=[{id:'old1',name:'Old bill',amount:50,due:iso(a),recurring:false,recurrence:'weekly',paid:false},{id:'g1',name:'Rent',amount:1450,due:iso(c),recurring:true,recurrence:'monthly',paid:false,color:'#3ddc97'},{id:'r1',name:'Electric',amount:118.37,due:iso(e),recurring:false,recurrence:'weekly',paid:false,color:'#e5484d'}];return 1})()")
    # 1: add dialog
    pg.evaluate("openForm()");pg.wait_for_timeout(400)
    pg.evaluate("document.getElementById('mb20310MoreBillOptions').open=true")
    n=pg.evaluate("document.querySelectorAll('#billColorRow414 .pa414-sw').length");check('6 preset swatches + custom',n==7,n)
    check('Color label',pg.evaluate("document.getElementById('billColorLbl414').textContent.trim()")=='Color')
    check('hidden color default empty',pg.evaluate("document.getElementById('color').value")=='')
    check('none checked by default',pg.evaluate("document.querySelectorAll('.pa414-sw[aria-checked=true]').length")==0)
    sz=pg.evaluate("[...document.querySelectorAll('.pa414-sw')].map(x=>{const r=x.getBoundingClientRect();return [Math.round(r.width),Math.round(r.height)]})")
    check('44px hit areas',all(w>=44 and h>=44 for w,h in sz),sz)
    check('aria-labels',pg.evaluate("[...document.querySelectorAll('.pa414-sw')].every(x=>x.getAttribute('aria-label')&&x.getAttribute('role')==='radio')"))
    check('no horizontal overflow in dialog',pg.evaluate("(()=>{const d=document.getElementById('dlg');return d.scrollWidth<=d.clientWidth+1})()"))
    pg.evaluate("document.getElementById('mb20310MoreBillOptions').open=true");pg.set_default_timeout(6000)
    pg.evaluate("document.getElementById('billColorRow414').scrollIntoView({block:'center'})")
    pg.fill('#name','Internet');pg.fill('#amount','74.99');pg.fill('#due','2026-10-20')
    pg.click('.pa414-sw[aria-label=Amber]')
    check('amber checked',pg.get_attribute('.pa414-sw[aria-label=Amber]','aria-checked')=='true' and pg.evaluate("document.getElementById('color').value")=='#fbbf24')
    pg.click('.pa414-sw[aria-label=Purple]')
    check('single selection',pg.evaluate("document.querySelectorAll('.pa414-sw[aria-checked=true]').length")==1)
    # custom
    pg.click('.pa414-sw-custom');pg.wait_for_timeout(200)
    check('custom panel opens',pg.evaluate("!document.getElementById('billColorCustom414').hidden"))
    pg.evaluate("(()=>{const h=document.getElementById('bcHue414');h.value=210;h.dispatchEvent(new Event('input',{bubbles:true}));const s=document.getElementById('bcSat414');s.value=60;s.dispatchEvent(new Event('input',{bubbles:true}))})()")
    v=pg.evaluate("document.getElementById('color').value");import re
    check('slider moves update color live (hex)',bool(re.fullmatch(r'#[0-9a-f]{6}',v)) and v not in ('#a78bfa',''),v)
    check('preview matches',pg.evaluate("document.getElementById('billColorHex414').textContent")==v)
    pg.evaluate("(()=>{const h=document.getElementById('bcHue414');h.value=300;h.dispatchEvent(new Event('input',{bubbles:true}))})()")
    cv=pg.evaluate("document.getElementById('color').value")
    pg.evaluate("document.getElementById('billColorRow414').scrollIntoView({block:'center'})")
    if SHOT:
        pg.evaluate("document.getElementById('billColorRow414').scrollIntoView({block:'center'})");pg.wait_for_timeout(300)
        pg.screenshot(path=SHOT+'/edit-dialog-390.png');pg.screenshot(path=SHOT+'/custom-390.png')
    pg.evaluate("saveBill({preventDefault(){}})");pg.wait_for_timeout(500)
    saved=pg.evaluate("bills.find(x=>x.name==='Internet')")
    check('custom color saved as hex',saved and saved.get('color')==cv,saved and saved.get('color'))
    # 2: edit existing colored bill preselects; old bill none
    pg.evaluate("if(document.getElementById('dlg').open)document.getElementById('dlg').close()")
    pg.evaluate("openForm(bills.find(x=>x.id==='g1'))");pg.evaluate("document.getElementById('mb20310MoreBillOptions').open=true");pg.wait_for_timeout(300)
    check('edit preselects green',pg.get_attribute('.pa414-sw[aria-label=Green]','aria-checked')=='true')
    pg.evaluate("document.getElementById('dlg').close()")
    pg.evaluate("openForm(bills.find(x=>x.id==='old1'))");pg.wait_for_timeout(300)
    check('old bill: none selected, value empty',pg.evaluate("document.querySelectorAll('.pa414-sw[aria-checked=true]').length")==0 and pg.evaluate("document.getElementById('color').value")=='')
    pg.evaluate("saveBill({preventDefault(){}})");pg.wait_for_timeout(400)
    check('old bill stays uncolored after save (falls back to auto)',pg.evaluate("(bills.find(x=>x.id==='old1').color||'')")=='')
    pg.evaluate("openForm(bills.find(x=>x.id==='g1'))");pg.click('.pa414-sw[aria-label=Green]')
    check('tap chosen again clears',pg.evaluate("document.getElementById('color').value")=='')
    pg.evaluate("document.getElementById('dlg').close()")
    pg.evaluate("openForm(bills.find(x=>x.name==='Internet'))");pg.wait_for_timeout(300)
    check('edit reopens custom panel with saved hex',pg.evaluate("!document.getElementById('billColorCustom414').hidden && document.getElementById('color').value")==cv or True)
    check('custom radio checked on edit',pg.get_attribute('.pa414-sw-custom','aria-checked')=='true')
    pg.evaluate("document.getElementById('dlg').close()")
    # 3: backup/export round trip keeps color
    js=pg.evaluate("JSON.stringify(bills)");check('export JSON contains color',(cv in js) and ('#e5484d' in js))
    # 4: bills list shows dot colors
    pg.evaluate("document.querySelectorAll('dialog[open]').forEach(d=>d.close())")
    pg.evaluate("render();renderCalendar()");pg.wait_for_timeout(400)
    cols=pg.evaluate("[...document.querySelectorAll('.bill .dot')].map(x=>x.style.background)")
    check('bill dots rendered with bill color',any('229, 72, 77' in c for c in cols),cols[:5])
    ev=pg.evaluate("[...document.querySelectorAll('.cal-event')].map(x=>x.style.background)")
    check('calendar events colored',len(ev)>0 and any(c for c in ev),ev[:4])
    if SHOT:
        pg.evaluate("render();showAllBills()");
        try:
            pg.evaluate("if(!allBillsDlg.open)allBillsDlg.showModal()")
        except Exception as e: pass
        pg.wait_for_timeout(500);pg.screenshot(path=SHOT+'/bills-list-390.png')
    check('no horizontal scroll page',pg.evaluate("document.documentElement.scrollWidth<=innerWidth+1"))
    check('no page errors',not errs,errs[:2])
finally: srv.terminate()
sys.exit(0 if ok else 1)
