#!/usr/bin/env python3
"""4.1.4 optional device-lock prompt + 7-day reminder."""
import sys,subprocess,time
from playwright.sync_api import sync_playwright
srv=subprocess.Popen(['python3','-m','http.server','8851'],cwd='.',stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL);time.sleep(1)
ok=True
def check(n,c,d=''):
    global ok;print(('PASS ' if c else 'FAIL ')+n+(' '+str(d) if d else ''));ok=ok and bool(c)
BR="window.__lock=false;window.__set=[];window.AndroidBridge={isAppLockEnabled:()=>window.__lock,setAppLockEnabled:v=>{window.__lock=v;window.__set.push(v)},isDeviceSecure:()=>true};"
try:
  with sync_playwright() as p:
    b=p.chromium.launch(executable_path='/usr/bin/google-chrome',args=['--no-sandbox'])
    pg=b.new_page(viewport={'width':390,'height':844});errs=[];pg.on('pageerror',lambda e:errs.append(str(e)))
    pg.add_init_script(BR)
    pg.goto('http://localhost:8851/index.html')
    pg.evaluate("localStorage.clear();localStorage.setItem('payAviator_onboarding_v1_done','1');localStorage.setItem('payaviator_onboarding_choice_v1','guest');localStorage.setItem('payaviator_connected_accounts_v1',JSON.stringify([{id:'a'}]))")
    pg.reload();pg.wait_for_timeout(8500)
    op=lambda:pg.evaluate("document.getElementById('lockPrompt414Dlg').open")
    check('reminder shows on open (bank, lock off, never reminded)',op())
    check('reminder has Dont remind me',pg.evaluate("getComputedStyle(document.getElementById('lockPrompt414Never')).display!=='none'"))
    pg.click('#lockPrompt414Later');check('Not now closes',not op())
    pg.reload();pg.wait_for_timeout(8500);check('no reminder within 7 days',not op())
    pg.evaluate("localStorage.setItem('payaviator_lock_prompt_last_v414',String(Date.now()-8*86400000))")
    pg.reload();pg.wait_for_timeout(8500);check('reminder after 8 days',op())
    pg.click('#lockPrompt414Never')
    pg.evaluate("localStorage.setItem('payaviator_lock_prompt_last_v414','0')")
    pg.reload();pg.wait_for_timeout(8500);check("Don't remind me respected",not op())
    pg.evaluate("localStorage.removeItem('payaviator_lock_prompt_never_v414');localStorage.setItem('payaviator_lock_prompt_last_v414','0')")
    pg.reload();pg.wait_for_timeout(8500)
    pg.click('#lockPrompt414On');check('Turn on lock calls bridge',pg.evaluate("window.__set")==[True])
    pg.evaluate("localStorage.setItem('payaviator_lock_prompt_last_v414','0')")
    pg.reload();pg.wait_for_timeout(8500)  # lock default false again in fake bridge
    if op(): pg.click('#lockPrompt414Later');pg.wait_for_timeout(300)  # reminder from the reload is open; dismiss before testing lock-on
    pg.evaluate("window.__lock=true;localStorage.setItem('payaviator_lock_prompt_last_v414','0')");pg.evaluate("window.PayAviatorLockPrompt414.maybeRemind()");pg.wait_for_timeout(500);check('no reminder when lock on',not op())
    pg.evaluate("window.__lock=false;document.getElementById('lockPrompt414Dlg').close();window.PayAviatorLockPrompt414.afterConnect()");pg.wait_for_timeout(1000)
    check('afterConnect shows connect prompt, no Dont-remind',op() and pg.evaluate("getComputedStyle(document.getElementById('lockPrompt414Never')).display==='none'"))
    pg.screenshot(path='/tmp/lock414.png')
    check('no page errors',not errs,errs[:2])
finally: srv.terminate()
sys.exit(0 if ok else 1)
