#!/usr/bin/env python3
"""4.1.1 Home: no Edit Cushion button, Cushion tile (chevron) opens the in-app cushion editor, Add Spending full width."""
import sys
from playwright.sync_api import sync_playwright
URL=sys.argv[1] if len(sys.argv)>1 else 'http://localhost:8811/index.html'; SH=sys.argv[2] if len(sys.argv)>2 else None
ok=True
def check(n,c,d=''):
    global ok; print(('PASS ' if c else 'FAIL ')+n+(' '+str(d) if d else '')); ok=ok and bool(c)
with sync_playwright() as p:
    b=p.chromium.launch(executable_path='/usr/bin/google-chrome',args=['--no-sandbox'])
    for vw,vh in [(390,844),(360,640)]:
        pg=b.new_page(viewport={'width':vw,'height':vh},has_touch=True,is_mobile=True); errs=[]; pg.on('pageerror',lambda e:errs.append(str(e)))
        pg.on('dialog',lambda d:(errs.append('NATIVE '+d.message),d.dismiss()))
        pg.goto(URL); pg.evaluate("localStorage.clear();localStorage.setItem('payAviator_onboarding_v1_done','1');localStorage.setItem('payaviator_tip_popup_seen_v1','true');localStorage.setItem('payAviator_security_tip_launch_count_v1','99');localStorage.setItem('payaviator_onboarding_choice_v1','guest')")
        pg.reload(); pg.wait_for_timeout(2500)
        pg.evaluate("document.querySelectorAll('dialog[open]').forEach(d=>d.close());document.querySelector('.mb119-nav[data-view=home]').click()"); pg.wait_for_timeout(500)
        check(f'{vw}: Edit Cushion button not shown',not pg.evaluate("(()=>{const e=document.getElementById('mb20419EditCushion');return !!e&&e.getBoundingClientRect().width>0})()"))
        r=pg.evaluate("(()=>{const a=document.getElementById('mb20419AddSpending').getBoundingClientRect(),p=document.getElementById('mb20419Actions').getBoundingClientRect();return [Math.round(a.width),Math.round(p.width),Math.round(a.x-p.x)]})()")
        check(f'{vw}: Add Spending fills the action row',abs(r[0]-r[1])<=2 and abs(r[2])<=1,r)
        c=pg.locator('#pp967Cushion'); c.scroll_into_view_if_needed()
        check(f'{vw}: Cushion tile has chevron',c.count()==1 and '›' in c.inner_text())
        if SH: pg.evaluate("document.getElementById('pp2059GaugeMetrics').scrollIntoView({block:'center'})"); pg.wait_for_timeout(300); pg.screenshot(path=f'{SH}/boss-411-{vw}x{vh}-cushion-tile.png')
        c.tap(); pg.wait_for_timeout(600)
        op=pg.evaluate("[...document.querySelectorAll('dialog[open]')].map(d=>d.id)")
        check(f'{vw}: tapping Cushion opens the in-app cushion editor',any(op) and pg.evaluate("!!document.getElementById('mb20419SaveCushion')&&document.getElementById('mb20419SaveCushion').getBoundingClientRect().width>0"),op)
        if SH: pg.screenshot(path=f'{SH}/boss-411-{vw}x{vh}-cushion-editor.png')
        check(f'{vw}: no errors / native dialogs',not errs,errs); pg.close()
    b.close()
print('ALL PASS' if ok else 'SOME FAILED'); sys.exit(0 if ok else 1)
