#!/usr/bin/env python3
"""App: slimmer bottom nav (clearly shorter than the header, 44px tap targets, no overflow) at 360/390/768/1280, plus splash redesign source checks.
Usage: python3 tests/import/nav_splash_test.py"""
import http.server, os, socketserver, threading, functools, re
from playwright.sync_api import sync_playwright
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.abspath(os.path.join(HERE, '..', '..'))
SEED = open(os.path.join(HERE, 'seed.js')).read()
class Q(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *a): pass
class TS(socketserver.ThreadingTCPServer): allow_reuse_address = True; daemon_threads = True
srv = TS(('127.0.0.1', 0), functools.partial(Q, directory=ROOT)); PORT = srv.server_address[1]
threading.Thread(target=srv.serve_forever, daemon=True).start()
fails = []
def check(n, c, e=''):
    print('  ok  ' if c else '  FAIL', n, '' if c else e)
    if not c: fails.append(n)
check('assets/index.html identical to root index.html', open(os.path.join(ROOT,'index.html'),'rb').read() == open(os.path.join(ROOT,'app/src/main/assets/index.html'),'rb').read())
j = open(os.path.join(ROOT,'app/src/main/java/com/payaviator/app/MainActivity.java'), encoding='utf-8').read()
check('splash keeps original navy + sky-blue gradient', 'Color.rgb(5, 19, 40)' in j and 'Color.rgb(12, 121, 187)' in j)
check('splash honors reduced motion (animator scale 0)', 'ANIMATOR_DURATION_SCALE' in j and 'still' in j)
check('splash scales with screen (shortSide)', 'shortSide' in j)
check('playful splash copy removed', 'taking off' not in j and 'Loading debts' not in j)
check('splash: five parallax cloud layers with shaded radial-gradient puffs (no external assets)', 'CLOUD_PUFFS' in j and 'CLOUD_LAYERS' in j and 'RadialGradient' in j and j.count('{') > 0 and j.count('// far') == 1 and j.count('// front') == 1)
check('splash: cloud tiles painted once, only translated per frame', 'renderTile' in j and 'drawBitmap(bm, null, dst' in j)
check('splash: logo emerges from a clearing veil', 'setVeilAnchor' in j and 'veilPaint' in j and 'scaleX(1f)' in j)
check('splash: reduced motion shows static clouds, no veil', 'still ? 0.3f' in j and '!still && veilAnchor' in j)
check('splash: no network/asset loads in splash code', 'http' not in j[j.index('class CloudSplashLayout'):j.index('class SplashBar')])
check('splash logo no longer 230dp', 'dp(230)' not in j)
with sync_playwright() as p:
    b = p.chromium.launch(args=['--no-sandbox'])
    for w, h in [(360, 740), (390, 844), (768, 1024), (1280, 800)]:
        ctx = b.new_context(viewport={'width': w, 'height': h}, is_mobile=w < 600, has_touch=w < 600)
        pg = ctx.new_page(); errs = []
        pg.on('pageerror', lambda e: errs.append(str(e)[:80]))
        pg.goto(f'http://localhost:{PORT}/index.html'); pg.wait_for_timeout(500)
        pg.evaluate("localStorage.clear()"); pg.reload(); pg.wait_for_timeout(2500)
        r = pg.evaluate("""()=>{const n=document.querySelector('#mb119BottomNav');if(!n)return null;const rc=n.getBoundingClientRect();
          const hd=document.querySelector('.mb123-sticky-header, #mb119Home .mb119-top, #mb119Shell header, .mb119-header, #mb119Home header');
          const items=[...n.querySelectorAll('.mb119-nav')].map(e=>{const q=e.getBoundingClientRect();return [q.width,q.height,q.right]});
          return {nh:rc.height,hh:hd?hd.getBoundingClientRect().height:null,items,sw:document.documentElement.scrollWidth,iw:innerWidth,vis:getComputedStyle(n).display!=='none'}}""")
        check(f'{w}: nav present', r is not None and r['vis'])
        if r:
            check(f'{w}: nav slim (<=56px, got {r["nh"]:.0f})', r['nh'] <= 56)
            if r['hh']: check(f'{w}: nav shorter than header ({r["nh"]:.0f} < {r["hh"]:.0f})', r['nh'] < r['hh'])
            check(f'{w}: tap targets >=44px tall', all(i[1] >= 44 - 0.5 for i in r['items']), str(r['items']))
            check(f'{w}: no horizontal overflow', r['sw'] <= r['iw'] + 1)
        check(f'{w}: no page errors', not errs, str(errs)); ctx.close()
    b.close()
print(f'{len(fails)} failed'); raise SystemExit(1 if fails else 0)
