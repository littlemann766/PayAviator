#!/usr/bin/env python3
"""4.2.4 nav: slim on every size with simulated safe-area inset 0/24/48. Usage: test-nav-424.py [shotdir]"""
import re,sys,os
from playwright.sync_api import sync_playwright
SH=sys.argv[1] if len(sys.argv)>1 else None
root=os.path.join(os.path.dirname(os.path.abspath(__file__)),'..')
src=open(os.path.join(root,'index.html')).read()
ok=True
def check(n,c,d=''):
    global ok; print(('PASS ' if c else 'FAIL ')+n+(' '+str(d) if d else '')); ok=ok and bool(c)
INIT="window.AndroidBridge={scheduleNotifications:()=>{},requestNotificationPermission:()=>{},takeFiredAlerts:()=>'[]',takeLaunchAlert:()=>''};"
M="""()=>{const n=document.getElementById('mb119BottomNav'),r=n.getBoundingClientRect();const hd=document.querySelector('.mb123-sticky-header');
const t=[...n.children].map(c=>{const b=c.getBoundingClientRect();return [b.width,b.height]});const d=document.documentElement;
const fit=[...n.children].every(c=>{const r=c.getBoundingClientRect();return [...c.children].every(k=>{const q=k.getBoundingClientRect();return q.top>=r.top-1&&q.bottom<=r.bottom+1&&q.left>=r.left-1&&q.right<=r.right+1&&k.scrollWidth<=k.clientWidth+1})});
const lab=[...n.querySelectorAll('.mb119-nav span:not(.ico)')].every(s=>s.getClientRects().length===1&&s.getBoundingClientRect().height<=16);
const ico=n.querySelector('.ico').getBoundingClientRect(),first=n.children[0].getBoundingClientRect();
return {nav:r.height,hdr:hd?hd.getBoundingClientRect().height:0,t,sw:d.scrollWidth,cw:d.clientWidth,bottom:r.bottom,ih:innerHeight,fit,lab,top:ico.top-first.top}}"""
sizes=[(360,640),(360,740),(390,844),(393,850),(412,915),(430,932),(600,960),(768,1024),(1024,768),(1024,1366),(1280,800),(1600,900)]
with sync_playwright() as p:
    b=p.chromium.launch(executable_path='/usr/bin/google-chrome',args=['--no-sandbox'])
    for inset in (0,24,48):
        h=re.sub(r'env\(safe-area-inset-bottom(,\s*0px)?\)',f'{inset}px',src)
        for vw,vh in sizes:
            ctx=b.new_context(service_workers='block',viewport={'width':vw,'height':vh},has_touch=True,is_mobile=vw<800,device_scale_factor=2.6 if vw<500 else 2)
            pg=ctx.new_page(); pg.route('**/index.html',lambda r,q=None,h=h:r.fulfill(body=h,content_type='text/html'))
            pg.add_init_script(INIT); pg.goto('http://localhost:8842/index.html')
            pg.evaluate("localStorage.clear();localStorage.setItem('payAviator_onboarding_v1_done','1');localStorage.setItem('payaviator_tip_popup_seen_v1','true');localStorage.setItem('payAviator_security_tip_launch_count_v1','99');localStorage.setItem('payaviator_onboarding_choice_v1','guest')")
            pg.reload(); pg.wait_for_timeout(2500)
            m=pg.evaluate(M); k=f'{vw}x{vh} inset{inset}'
            check(f'{k}: nav <= 64px (and <= 48+min(inset,12)+2)',m['nav']<=64 and m['nav']<=50+min(inset,12)+0.5,m['nav'])
            if inset<=12 or True: check(f'{k}: nav shorter than header',m['hdr']==0 or m['nav']<m['hdr'],(m['nav'],m['hdr']))
            check(f'{k}: 6 tabs >=44px',len(m['t'])==6 and all(w>=44 and h>=44 for w,h in m['t']),m['t'])
            check(f'{k}: bottom edge, no h-scroll',abs(m['bottom']-m['ih'])<=1 and m['sw']<=m['cw'],(m['bottom'],m['ih']))
            check(f'{k}: labels fit, one line, no empty strip',m['fit'] and m['lab'] and m['top']<=8,m['top'])
            if SH: pg.screenshot(path=f'{SH}/nav-{vw}x{vh}-inset{inset}.png')
            ctx.close()
    b.close()
print('ALL PASS' if ok else 'SOME FAIL'); sys.exit(0 if ok else 1)
