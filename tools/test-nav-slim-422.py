#!/usr/bin/env python3
"""Slim bottom nav (clearly shorter than the header, 44px tap targets, no overflow) + splash source guards.
Usage: python3 tools/test-nav-slim-422.py [url] [screenshot_dir]"""
import sys, re, os
from playwright.sync_api import sync_playwright
URL=sys.argv[1] if len(sys.argv)>1 else 'http://localhost:8842/index.html'; SH=sys.argv[2] if len(sys.argv)>2 else None
ok=True
def check(n,c,d=''):
    global ok; print(('PASS ' if c else 'FAIL ')+n+(' '+str(d) if d else '')); ok=ok and bool(c)
INIT="window.AndroidBridge={scheduleNotifications:()=>{},requestNotificationPermission:()=>{},takeFiredAlerts:()=>'[]',takeLaunchAlert:()=>''};"
M="""()=>{const n=document.getElementById('mb119BottomNav'),r=n.getBoundingClientRect();const hd=document.querySelector('#mb119Home .mb123-sticky-header')||document.querySelector('.mb123-sticky-header');
const t=[...n.children].map(c=>{const b=c.getBoundingClientRect();return [b.width,b.height]});const d=document.documentElement;
return {nav:r.height,hdr:hd?hd.getBoundingClientRect().height:0,t,sw:d.scrollWidth,cw:d.clientWidth,bottom:r.bottom,ih:innerHeight}}"""
with sync_playwright() as p:
    b=p.chromium.launch(executable_path='/usr/bin/google-chrome',args=['--no-sandbox'])
    for vw,vh in [(360,740),(390,844),(768,1024),(1280,800)]:
        pg=b.new_page(viewport={'width':vw,'height':vh},has_touch=True,is_mobile=vw<800,device_scale_factor=2)
        pg.add_init_script(INIT); pg.goto(URL)
        pg.evaluate("localStorage.clear();localStorage.setItem('payAviator_onboarding_v1_done','1');localStorage.setItem('payaviator_tip_popup_seen_v1','true');localStorage.setItem('payAviator_security_tip_launch_count_v1','99');localStorage.setItem('payaviator_onboarding_choice_v1','guest')")
        pg.reload(); pg.wait_for_timeout(3000)
        m=pg.evaluate(M)
        check(f'{vw}: nav <= 50px',m['nav']<=50,m['nav'])
        check(f'{vw}: nav clearly slimmer than header (<= 75%)',m['hdr']>0 and m['nav']<=m['hdr']*0.75,(m['nav'],m['hdr']))
        check(f'{vw}: 6 tabs, each >= 44px tall and >= 44px wide',len(m['t'])==6 and all(w>=44 and h>=44 for w,h in m['t']),m['t'])
        check(f'{vw}: nav sits at the bottom edge, no horizontal scroll',abs(m['bottom']-m['ih'])<=1 and m['sw']<=m['cw'],(m['bottom'],m['ih']))
        # labels/icons not clipped: each tab's content fits inside it
        fit=pg.evaluate("[...document.querySelectorAll('#mb119BottomNav .mb119-nav')].every(c=>{const r=c.getBoundingClientRect();return [...c.children].every(k=>{const q=k.getBoundingClientRect();return q.top>=r.top-1&&q.bottom<=r.bottom+1&&q.left>=r.left-1&&q.right<=r.right+1})})")
        check(f'{vw}: icons and labels fit inside their tabs',fit)
        if SH and vw in (360,390,768,1280): pg.screenshot(path=f'{SH}/app-nav-{vw}.png')
        # a tab still works
        pg.evaluate("document.querySelector('.mb119-nav[data-view=bills]').click()");pg.wait_for_timeout(300)
        check(f'{vw}: tapping Bills still opens Bills',pg.evaluate("document.querySelector('.mb119-nav[data-view=bills]').classList.contains('active')"))
        pg.close()
    b.close()
J=open(os.path.join(os.path.dirname(__file__),'..','app/src/main/java/com/payaviator/app/MainActivity.java')).read()
check('splash: calm copy, no emoji status',not re.search(r'setSplashStatus\("[^"]*[\u2708\u2601\U0001F300-\U0001FAFF]',J) and 'taking off' not in J)
check('splash: honors system remove-animations setting','ANIMATOR_DURATION_SCALE' in J and 'reducedMotion' in J)
check('splash: logo scales with screen (no fixed 230dp)','dp(230)' not in J and 'shortSide' in J)
check('splash: original navy + cyan + sky blue kept','Color.rgb(5, 19, 40)' in J and 'Color.rgb(22, 228, 234)' in J and 'Color.rgb(12, 121, 187)' in J)
check('splash: five parallax cloud layers with shaded radial-gradient puffs (no external assets)', 'CLOUD_PUFFS' in J and 'CLOUD_LAYERS' in J and 'RadialGradient' in J and J.count('// far') == 1 and J.count('// front') == 1)
check('splash: cloud tiles painted once, only translated per frame', 'renderTile' in J and 'drawBitmap(bm, null, dst' in J)
check('splash: logo emerges from a clearing veil', 'setVeilAnchor' in J and 'veilPaint' in J and 'scaleX(1f)' in J)
check('splash: reduced motion shows static clouds, no veil', 'still ? 0.3f' in J and '!still && veilAnchor' in J)
check('splash: no network/asset loads in splash code', 'http' not in J[J.index('class CloudSplashLayout'):J.index('class SplashBar')])
check('splash: tap-to-skip and fail-safe reveal kept','forceRevealApp()' in J and 'splashView.setOnClickListener' in J)
a=open(os.path.join(os.path.dirname(__file__),'..','index.html'),'rb').read(); c=open(os.path.join(os.path.dirname(__file__),'..','app/src/main/assets/index.html'),'rb').read()
check('index.html mirrored in assets (cmp)',a==c)
print('ALL PASS' if ok else 'SOME FAIL'); sys.exit(0 if ok else 1)
