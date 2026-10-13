#!/usr/bin/env python3
"""4.1.2 notification rework: plan logic (paid/deleted/edit/disable), bell + Alerts center, deep links, privacy row, persistence."""
import sys
from playwright.sync_api import sync_playwright
URL=sys.argv[1] if len(sys.argv)>1 else 'http://localhost:8842/index.html'; SH=sys.argv[2] if len(sys.argv)>2 else None
ok=True
def check(n,c,d=''):
    global ok; print(('PASS ' if c else 'FAIL ')+n+(' '+str(d) if d else '')); ok=ok and bool(c)
SEED="""(()=>{const t=new Date();const f=n=>{const d=new Date(t.getFullYear(),t.getMonth(),t.getDate()+n);return d.getFullYear()+'-'+String(d.getMonth()+1).padStart(2,'0')+'-'+String(d.getDate()).padStart(2,'0')};
localStorage.setItem('payAviator_v1',JSON.stringify([{id:'b1',name:'Rent',amount:850,due:f(5),recurring:true,recurrence:'monthly',color:'#ff0000'},{id:'b2',name:'Electric',amount:65,due:f(3),recurring:false,color:'#ffff00'}]));
const s=JSON.parse(localStorage.getItem('payAviator_settings_v2')||'{}');s.notificationsEnabled=true;s.notificationDays=1;s.notificationTime='09:00';localStorage.setItem('payAviator_settings_v2',JSON.stringify(s));return [f(5),f(3)]})()"""
with sync_playwright() as p:
    b=p.chromium.launch(executable_path='/usr/bin/google-chrome',args=['--no-sandbox'])
    for vw,vh in [(390,844),(360,640)]:
        pg=b.new_page(viewport={'width':vw,'height':vh},has_touch=True,is_mobile=True,device_scale_factor=2); errs=[]
        pg.on('pageerror',lambda e:errs.append(str(e))); pg.on('dialog',lambda d:(errs.append('NATIVE '+d.message),d.dismiss()))
        # fake native bridge records plans
        pg.add_init_script("window.__plans=[];window.AndroidBridge={scheduleNotifications:j=>window.__plans.push(JSON.parse(j)),requestNotificationPermission:()=>{},takeFiredAlerts:()=>window.__fired||'[]',takeLaunchAlert:()=>''};")
        pg.goto(URL); pg.evaluate("localStorage.clear();localStorage.setItem('payAviator_onboarding_v1_done','1');localStorage.setItem('payaviator_tip_popup_seen_v1','true');localStorage.setItem('payAviator_security_tip_launch_count_v1','99');localStorage.setItem('payaviator_onboarding_choice_v1','guest')")
        due=pg.evaluate(SEED)
        pg.reload(); pg.wait_for_timeout(3200)
        pg.evaluate("document.querySelectorAll('dialog[open]').forEach(d=>d.close());document.querySelector('.mb119-nav[data-view=home]').click()"); pg.wait_for_timeout(400)
        nb=pg.evaluate("bills.length")
        check(f'{vw}: seeded bills loaded',nb==2,nb)
        plan=pg.evaluate("window.__plans[window.__plans.length-1]")
        check(f'{vw}: app start sends a v2 plan to native',plan and plan.get('version')==2,len(pg.evaluate('window.__plans')))
        keys=[a['key'] for a in plan['alarms']] if plan else []
        check(f'{vw}: Rent + Electric occurrences scheduled', f'bill|b1|{due[0]}' in keys and f'bill|b2|{due[1]}' in keys, keys[:4])
        a=[x for x in plan['alarms'] if x['key']==f'bill|b1|{due[0]}'][0]
        check(f'{vw}: public lock-screen text has no amount','$' not in a['publicTitle']+a['publicText'] and a['publicTitle']=='A bill is due tomorrow',a['publicTitle'])
        check(f'{vw}: private text has amount + deep link','$850' in a['text'] and a['open']==f'bill:b1:{due[0]}',a['text'])
        check(f'{vw}: lock-screen amounts off by default',plan['showAmountsOnLockScreen'] is False)
        # mark Rent occurrence paid -> rescheduled without it
        n0=pg.evaluate("window.__plans.length")
        pg.evaluate(f"setBillPaidOnDate(bills.find(b=>b.id==='b1'),'{due[0]}',true);setBillPaidAmount(bills.find(b=>b.id==='b1'),'{due[0]}',850)"); pg.wait_for_timeout(900)
        plan2=pg.evaluate("window.__plans[window.__plans.length-1]"); k2=[x['key'] for x in plan2['alarms']]
        check(f'{vw}: marking paid reschedules and drops that occurrence',pg.evaluate("window.__plans.length")>n0 and f'bill|b1|{due[0]}' not in k2 and f'bill|b2|{due[1]}' in k2)
        check(f'{vw}: next month Rent still scheduled',any(k.startswith('bill|b1|') for k in k2))
        # delete Electric -> gone
        pg.evaluate("bills=bills.filter(b=>b.id!=='b2');persistBills()"); pg.wait_for_timeout(900)
        k3=[x['key'] for x in pg.evaluate("window.__plans[window.__plans.length-1]")['alarms']]
        check(f'{vw}: deleting a bill cancels its alarms',not any(k.startswith('bill|b2|') for k in k3))
        # edit Rent amount -> text updates
        pg.evaluate("bills=bills.map(b=>b.id==='b1'?{...b,amount:900}:b);persistBills()"); pg.wait_for_timeout(900)
        p4=pg.evaluate("window.__plans[window.__plans.length-1]")
        check(f'{vw}: editing a bill reschedules with new amount',all('$900' in x['text'] for x in p4['alarms'] if x['billId']=='b1') and p4['alarms'])
        # global off -> no bill alarms
        pg.evaluate("appSettings.notificationsEnabled=false;scheduleNativeNotifications()"); pg.wait_for_timeout(900)
        check(f'{vw}: notifications off = no bill alarms',not [x for x in pg.evaluate("window.__plans[window.__plans.length-1]")['alarms'] if x['type']=='bill'])
        pg.evaluate("appSettings.notificationsEnabled=true;scheduleNativeNotifications()"); pg.wait_for_timeout(700)
        # bell
        bell=pg.evaluate("(()=>{const b=document.getElementById('pa412Bell');if(!b)return null;const r=b.getBoundingClientRect(),h=document.querySelector('#mb119Home > .pp-help-btn').getBoundingClientRect();return {w:r.width,top:Math.round(r.top),htop:Math.round(h.top),gap:Math.round(h.left-r.right)}})()")
        check(f'{vw}: bell in Home header beside ?',bell and bell['w']>30 and abs(bell['top']-bell['htop'])<=2 and 0<=bell['gap']<=16,bell)
        if SH and vw==390:
            pg.evaluate("window.scrollTo(0,0)"); pg.screenshot(path=f'{SH}/412-390-home-bell-empty.png')
        # native fired alerts merge + badge
        pg.evaluate(f"""window.__fired=JSON.stringify([{{key:'bill|b1|{due[0]}',type:'bill',title:'Rent is due tomorrow',text:'$900.00 · Tap to view or mark paid',open:'bill:b1:{due[0]}',ts:Date.now()-3600e3}},{{key:'r|x',type:'reminder',title:'Call the insurance company',text:'Ask about the renewal',open:'calendar:{due[1]}',ts:Date.now()-3*86400e3}}]);PayAviatorAlerts.mergeNative();window.__fired='[]';
          PayAviatorAlerts.add({{id:'reconnect|demo',type:'reconnect',title:'Chase needs a quick reconnect',text:'Sign in again so your balances stay up to date.',ts:Date.now()-600e3,open:'reconnect:demo'}})""")
        pg.wait_for_timeout(200)
        bt=pg.evaluate("document.getElementById('pa412BellBadge').textContent")
        check(f'{vw}: badge shows 3 unread',bt=='3',bt)
        if SH and vw==390: pg.screenshot(path=f'{SH}/412-390-home-bell.png')
        pg.locator('#pa412Bell').tap(); pg.wait_for_timeout(400)
        check(f'{vw}: Alerts center opens with 3 items',pg.evaluate("document.getElementById('pa412Alerts').classList.contains('show')&&document.querySelectorAll('.pa412-item').length===3"))
        if SH and vw==390: pg.screenshot(path=f'{SH}/412-390-alerts-center.png')
        pg.locator('.pa412-item').first.tap(); pg.wait_for_timeout(500)
        st=pg.evaluate("[document.querySelector('.mb119-nav.active')?.dataset.view,document.getElementById('pa412Alerts').classList.contains('show')]")
        check(f'{vw}: tapping an alert closes the center and navigates',st[1] is False and st[0] in ('settings','bills'),st)
        pg.evaluate("document.querySelectorAll('dialog[open]').forEach(d=>d.close())")
        # deep link for bill
        pg.evaluate(f"PayAviatorOpenAlert('bill:b1:{due[0]}')"); pg.wait_for_timeout(800)
        st=pg.evaluate("[document.querySelector('.mb119-nav.active')?.dataset.view,[...document.querySelectorAll('dialog[open]')].map(d=>d.id)]")
        check(f'{vw}: notification deep link opens the bill',st[0]=='bills' and len(st[1])>0,st)
        pg.evaluate("document.querySelectorAll('dialog[open]').forEach(d=>d.close())")
        # mark all read + persistence across reload
        pg.evaluate("PayAviatorAlerts.open()"); pg.wait_for_timeout(200)
        pg.evaluate("document.getElementById('pa412ReadAll')&&document.getElementById('pa412ReadAll').click()")
        check(f'{vw}: mark all read clears badge',pg.evaluate("document.getElementById('pa412BellBadge').hidden"))
        pg.reload(); pg.wait_for_timeout(3000)
        check(f'{vw}: alert history persists after reload',pg.evaluate("PayAviatorAlerts.list().length")==3)
        check(f'{vw}: bills persist after reload',pg.evaluate("bills.length")==1)
        pg.evaluate("document.querySelectorAll('dialog[open]').forEach(d=>d.close());PayAviatorAlerts.open()"); pg.wait_for_timeout(200)
        pg.evaluate("document.getElementById('pa412ClearAll').click()")
        check(f'{vw}: clear all shows empty state',pg.evaluate("!!document.querySelector('.pa412-empty')"))
        if SH and vw==390: pg.screenshot(path=f'{SH}/412-390-alerts-empty.png')
        pg.evaluate("document.getElementById('pa412Back').click()")
        check(f'{vw}: privacy row in settings',pg.evaluate("!!document.getElementById('pa412ShowAmounts')"))
        pg.evaluate("const c=document.getElementById('pa412ShowAmounts');c.checked=true;c.dispatchEvent(new Event('change'))"); pg.wait_for_timeout(700)
        check(f'{vw}: lock-screen toggle reaches native plan',pg.evaluate("window.__plans[window.__plans.length-1].showAmountsOnLockScreen")==True)
        check(f'{vw}: no page errors / native dialogs',not errs,errs); pg.close()
    b.close()
print('ALL PASS' if ok else 'SOME FAILED'); sys.exit(0 if ok else 1)
