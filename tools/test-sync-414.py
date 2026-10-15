#!/usr/bin/env python3
"""4.1.4 cloud sync client: mocked backend (in-memory fake of the cloud-sync-pause-banks contract), run from the repo root."""
import sys,subprocess,time,json,re
from playwright.sync_api import sync_playwright
srv=subprocess.Popen(['python3','-m','http.server','8852'],cwd='.',stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL);time.sleep(1)
ok=True
def check(n,c,d=''):
    global ok;print(('PASS ' if c else 'FAIL ')+n+(' '+str(d) if d else ''));ok=ok and bool(c)
class Server:
    def __init__(s):
        s.items={};s.seq=0;s.offline=False;s.hide=set();s.calls=[];s.status=None;s.accounts={'accounts':[],'items':[],'errors':[]};s.tx={'transactions':[],'errors':[]};s.billing={'plan':'free','billingConfigured':True,'pausedBanks':0}
    def put(s,kind,id,data,u,deleted=False):
        s.seq+=1;s.items[(kind,id)]={'kind':kind,'id':id,'data':None if deleted else data,'updatedAt':u,'deleted':deleted,'seq':s.seq}
    def handle(s,route,req):
        h={'access-control-allow-origin':'*','access-control-allow-headers':'*','access-control-allow-methods':'*'}
        if req.method=='OPTIONS':return route.fulfill(status=204,headers=h)
        path=req.url.split('api.payaviator.app')[1];s.calls.append((req.method,path))
        def ok_(b,st=200):return route.fulfill(status=st,headers=dict(h,**{'content-type':'application/json'}),body=json.dumps(b))
        if path.startswith('/api/sync/'):
            if s.offline:return route.abort()
            if s.status:return ok_({'error':'x','code':s.status[1]},s.status[0])
            if path.startswith('/api/sync/changes'):
                since=int(re.search(r'since=(\d+)',path).group(1));lim=int(re.search(r'limit=(\d+)',path).group(1))
                rows=sorted([i for i in s.items.values() if i['seq']>since and (i['kind'],i['id']) not in s.hide],key=lambda i:i['seq'])
                page=rows[:min(lim,500)];nxt=page[-1]['seq'] if page else since
                return ok_({'items':page,'next':nxt,'more':len(rows)>len(page)})
            if path=='/api/sync/push':
                body=json.loads(req.post_data);res=[]
                s.last_push=body
                for it in body['items']:
                    if not re.match(r'^[A-Za-z0-9_.:@-]{1,128}$',it['id']):res.append({'kind':it['kind'],'id':it['id'],'status':'rejected','reason':'invalid_id'});continue
                    cur=s.items.get((it['kind'],it['id']))
                    dele=bool(it.get('deleted'))
                    if cur and cur['updatedAt']>it['updatedAt']:res.append({'kind':it['kind'],'id':it['id'],'status':'rejected','reason':'stale','winner':cur});continue
                    if cur and not dele and cur['data']==it['data'] and not cur['deleted']:res.append({'kind':it['kind'],'id':it['id'],'status':'accepted'});continue
                    s.put(it['kind'],it['id'],it.get('data'),it['updatedAt'],dele);res.append({'kind':it['kind'],'id':it['id'],'status':'accepted'})
                return ok_({'results':res})
            if path=='/api/sync/all' and req.method=='DELETE':
                n=len(s.items);s.items={};return ok_({'deleted':n})
        if path.startswith('/api/plaid/accounts'):return ok_(s.accounts)
        if path.startswith('/api/plaid/transactions'):return ok_(s.tx)
        if path.startswith('/api/billing/status'):return ok_(s.billing)
        if path.startswith('/api/health'):return ok_({'plaidEnvironment':'sandbox'})
        return ok_({})
S=Server()
INIT="""localStorage.clear();localStorage.setItem('payAviator_onboarding_v1_done','1');localStorage.setItem('payaviator_onboarding_choice_v1','guest');localStorage.setItem('payaviator_tip_popup_seen_v1','1');
localStorage.setItem('payAviator_v1',JSON.stringify([{id:'b1',name:'Rent',amount:1200,due:'2026-11-01',recurring:true,recurrence:'monthly',paid:false,color:'#00f5ff'},{id:'b2',name:'Phone',amount:60,due:'2026-11-05',recurring:true,recurrence:'monthly',paid:false,color:'#00f5ff'}]));
localStorage.setItem('payAviator_bill_overrides_v1',JSON.stringify({'b1|2026-10-01':true}));
localStorage.setItem('payAviator_paychecks_v1',JSON.stringify([{id:'p1',name:'Job',amount:1500,date:'2026-10-16',frequency:'biweekly'}]));
localStorage.setItem('payAviator_budget_spending_v1',JSON.stringify([{id:'s1',name:'Coffee',amount:4.5,date:'2026-10-14'},{id:'s2',name:'Gas',amount:30,date:'2026-10-13'},{name:'NoId',amount:1,date:'2026-10-12'}]));
localStorage.setItem('payAviator_savings_goals_v1',JSON.stringify([{id:'g1',name:'Trip',target:500,saved:50}]));
localStorage.setItem('payAviator_monthly_budgets_v1',JSON.stringify({'2026-10':900}));
localStorage.setItem('payaviator_payday_cushion_v2045',JSON.stringify({type:'dollar',amount:25,percent:0}));
localStorage.setItem('payAviator_category_map_v86',JSON.stringify({'b1':'Housing','Some Merchant!':'Food'}));
"""
SIGNIN="window.PayAviatorAuth._setStateForTest({available:true,signedIn:true,uid:'u1',email:'a@yahoo.com',provider:'password',emailVerified:true},'signed_in')"
def _wait(pg,expr,timeout=15000):
    t=time.time()
    while time.time()-t<timeout/1000:
        if pg.evaluate(expr):return True
        pg.wait_for_timeout(150)
    raise Exception('timeout waiting for '+expr[:80]+' status='+json.dumps(pg.evaluate('window.PayAviatorSync.status()')))
def ls(pg,k):return pg.evaluate("k=>JSON.parse(localStorage.getItem(k)||'null')",k)
def st(pg):return pg.evaluate("window.PayAviatorSync.status()")
try:
  with sync_playwright() as p:
    b=p.chromium.launch(executable_path='/usr/bin/google-chrome',args=['--no-sandbox'])
    ctx=b.new_context(viewport={'width':390,'height':844});ctx.route('https://api.payaviator.app/**',S.handle)
    ctx.route(lambda u:not u.startswith('http://localhost') and 'api.payaviator.app' not in u,lambda r:r.abort())
    pg=ctx.new_page();errs=[];pg.on('pageerror',lambda e:errs.append(str(e)))
    pg.goto('http://localhost:8852/index.html');pg.evaluate(INIT);pg.reload();pg.wait_for_timeout(1500)
    # 1 signed-out
    pg.evaluate("localStorage.setItem('payAviator_budget_spending_v1',localStorage.getItem('payAviator_budget_spending_v1'))");pg.wait_for_timeout(2200)
    check('signed-out: no sync traffic',not [c for c in S.calls if c[1].startswith('/api/sync')])
    check('signed-out: sync API reports skipped',pg.evaluate("window.PayAviatorSync.sync('manual')")=={'skipped':'signed-out'})
    # 2 migration on first signed-in sync
    pg.evaluate(SIGNIN);_wait(pg,"window.PayAviatorSync.status().migrated===true&&window.PayAviatorSync.status().queued===0",15000)
    kinds=sorted(set(k[0] for k in S.items));check('migration uploads every kind',kinds==['bill','budget','category','cushion','goal','income','spending'],kinds)
    check('migration counts',sum(1 for k in S.items if k[0]=='bill')==2 and sum(1 for k in S.items if k[0]=='spending')==3 and sum(1 for k in S.items if k[0]=='category')==2,len(S.items))
    check('all ids valid',all(re.match(r'^[A-Za-z0-9_.:@-]{1,128}$',k[1]) for k in S.items))
    check('bill carries its overrides',S.items[('bill','b1')]['data'].get('_ov')=={'2026-10-01':True})
    check('non-simple key hashed to valid id',any(k[0]=='category' and k[1].startswith('c:') is False or k[1].startswith('h_') for k in S.items if k[0]=='category'))
    n_items=len(S.items);seq=S.seq
    check('status synced',st(pg)['state']=='synced',st(pg))
    # 3 idempotency: wipe all local sync state (reinstall-like) and migrate again
    pg.evaluate("['base','outbox','cursor','meta'].forEach(k=>localStorage.removeItem('payaviator_sync_'+k+'_v414'))")
    r=pg.evaluate("window.PayAviatorSync.sync('manual')");_wait(pg,"window.PayAviatorSync.status().migrated===true",15000)
    check('re-migration: no duplicates on server',len(S.items)==n_items,(len(S.items),n_items))
    check('re-migration: no new server changes',S.seq==seq,(S.seq,seq))
    check('re-migration: local data unchanged',len(ls(pg,'payAviator_v1'))==2 and len(ls(pg,'payAviator_budget_spending_v1'))==3)
    # 4 edit -> push; remote -> local; tombstones
    pg.evaluate("(()=>{const a=JSON.parse(localStorage.getItem('payAviator_v1'));a[0].name='Rent 2';localStorage.setItem('payAviator_v1',JSON.stringify(a))})()")
    pg.wait_for_timeout(4000);check('local edit pushed',S.items[('bill','b1')]['data']['name']=='Rent 2')
    pg.evaluate("localStorage.setItem('payAviator_budget_spending_v1',JSON.stringify(JSON.parse(localStorage.getItem('payAviator_budget_spending_v1')).filter(x=>x.id!=='s2')))")
    pg.wait_for_timeout(4000)
    check('local delete pushed as tombstone',S.items[('spending','s2')]['deleted'] is True)
    S.put('bill','web1',{'id':'web1','name':'Web bill','amount':10,'due':'2026-11-09','recurring':False,'paid':False},int(time.time()*1000)+1000)
    pg.evaluate("window.PayAviatorSync.sync('resume')");pg.wait_for_timeout(1500)
    check('remote bill appears locally',any(x['id']=='web1' for x in ls(pg,'payAviator_v1')))
    check('remote bill in memory too',pg.evaluate("bills.some(b=>b.id==='web1')"))
    S.put('spending','s1',None,int(time.time()*1000)+2000,True)
    pg.evaluate("window.PayAviatorSync.sync('resume')");pg.wait_for_timeout(1500)
    check('remote tombstone removes local item',not any(x.get('id')=='s1' for x in ls(pg,'payAviator_budget_spending_v1')))
    check('echo not re-pushed',st(pg)['queued']==0)
    # 5 conflict: stale winner adopted (server hides it from changes so only push reveals it)
    S.put('goal','g1',{'id':'g1','name':'Trip WEB','target':900,'saved':50},int(time.time()*1000)+60000);S.hide.add(('goal','g1'))
    pg.evaluate("(()=>{const a=JSON.parse(localStorage.getItem('payAviator_savings_goals_v1'));a[0].name='Trip local';localStorage.setItem('payAviator_savings_goals_v1',JSON.stringify(a))})()")
    _wait(pg,"JSON.parse(localStorage.getItem('payAviator_savings_goals_v1'))[0].name==='Trip WEB'",15000)
    check('stale winner adopted locally',ls(pg,'payAviator_savings_goals_v1')[0]['target']==900)
    S.hide.clear();_wait(pg,"window.PayAviatorSync.status().queued===0",10000)
    check('no push loop after adopt',st(pg)['queued']==0)
    # 6 offline queue + backoff + persistence + flush on connectivity
    S.offline=True
    pg.evaluate("(()=>{const a=JSON.parse(localStorage.getItem('payAviator_v1'));a[1].amount=77;localStorage.setItem('payAviator_v1',JSON.stringify(a));const s=JSON.parse(localStorage.getItem('payAviator_budget_spending_v1'));s.push({id:'s9',name:'Offline',amount:9,date:'2026-10-15'});localStorage.setItem('payAviator_budget_spending_v1',JSON.stringify(s))})()")
    _wait(pg,"window.PayAviatorSync.status().tries>=1",15000)
    s1=st(pg);check('offline: changes queued',s1['queued']>=2,s1);check('offline: backoff scheduled',s1['nextAt']>time.time()*1000+3000 and s1['state']=='retrying',s1)
    before=len(S.calls);pg.evaluate("window.PayAviatorSync.sync('timer')");pg.wait_for_timeout(500)
    check('timer attempt respects backoff',len(S.calls)==before)
    pg.reload();pg.wait_for_timeout(1500)
    check('outbox survives restart (signed out at boot)',st(pg)['queued']>=2,st(pg))
    pg.evaluate("window.PayAviatorAuth._setStateForTest({available:true,signedIn:true,uid:'u1',email:'a@yahoo.com',provider:'password',emailVerified:true})")
    check('outbox survives restart',st(pg)['queued']>=2,st(pg))
    S.offline=False;pg.evaluate("window.dispatchEvent(new Event('online'))")
    _wait(pg,"window.PayAviatorSync.status().queued===0",15000);pg.wait_for_timeout(400)
    check('online event flushes queue (bypasses backoff)',S.items[('spending','s9')]['data']['amount']==9 and S.items[('bill','b2')]['data']['amount']==77)
    check('tries reset after success',st(pg).get('tries',0)==0)
    # 7 unverified email -> no traffic
    pg.evaluate("window.PayAviatorAuth._setStateForTest({available:true,signedIn:true,uid:'u1',email:'a@yahoo.com',provider:'password',emailVerified:false})")
    n=len([c for c in S.calls if c[1].startswith('/api/sync')]);r=pg.evaluate("window.PayAviatorSync.sync('manual')")
    check('unverified: sync skipped, no calls',r=={'skipped':'unverified'} and len([c for c in S.calls if c[1].startswith('/api/sync')])==n)
    pg.evaluate("window.PayAviatorAuth._setStateForTest({available:true,signedIn:true,uid:'u1',email:'a@yahoo.com',provider:'password',emailVerified:true})")
    _wait(pg,"window.PayAviatorSync.status().state!=='syncing'")
    S.status=(403,'EMAIL_NOT_VERIFIED');r=pg.evaluate("window.PayAviatorSync.sync('manual')")
    check('403 EMAIL_NOT_VERIFIED handled quietly (no verify dialog)',r.get('error')=='EMAIL_NOT_VERIFIED' and not pg.evaluate("!!document.getElementById('pa410VerifyDlg')?.open"),r)
    S.status=None
    # 8 mass delete held back
    pg.evaluate("localStorage.setItem('payAviator_budget_spending_v1',JSON.stringify([...JSON.parse(localStorage.getItem('payAviator_budget_spending_v1')),...[1,2,3,4,5,6].map(i=>({id:'m'+i,name:'M'+i,amount:i,date:'2026-10-10'}))]))");pg.wait_for_timeout(4000)
    check('six more rows synced',sum(1 for k in S.items if k[1].startswith('m') and k[0]=='spending')==6)
    pg.evaluate("localStorage.setItem('payAviator_savings_goals_v1','[]');localStorage.setItem('payAviator_budget_spending_v1','[]')");pg.wait_for_timeout(3500)
    check('mass local wipe is held, not synced as deletes',st(pg).get('held',0)>=1 and not S.items[('spending','s9')]['deleted'],st(pg))
    # 9 account switch resets cursor/base
    pg.evaluate("window.PayAviatorAuth._setStateForTest({available:true,signedIn:true,uid:'u2',email:'b@aol.com',provider:'password',emailVerified:true})")
    pg.evaluate("window.PayAviatorSync.sync('manual')");pg.wait_for_timeout(1500)
    check('new uid starts a fresh migration',st(pg)['uid']=='u2')
    # 10 paused banks UI
    pg.evaluate("window.PayAviatorAuth._setStateForTest({available:true,signedIn:true,uid:'u2',email:'b@aol.com',provider:'password',emailVerified:true})")
    pg.evaluate("window.PayAviatorSavePlaidItemHealth({items:[{item_id:'it2',institution_name:'Second Bank',paused:true,pause_reason:'plus_ended',status:'paused',needs_update:false}],errors:[{code:'ITEM_PAUSED',item_id:'it2',institution_name:'Second Bank',paused:true,needs_update:false}]})")
    pg.evaluate("window.openPayAviatorConnectedAccounts920()");pg.wait_for_timeout(600)
    html=pg.evaluate("document.getElementById('pp920AccountsBody').innerText")
    check('paused card shows name + Paused',('Second Bank' in html) and ('PAUSED' in html.upper()),html[:200])
    check('paused card message',('pause when' in html) and ('Plus' in html))
    check('BILLING_LIVE=false: no purchase button, coming-soon wording',pg.evaluate("!document.querySelector('[data-pp414-resub]')") and 'Plus is coming soon' in html)
    check('paused: no reconnect prompt',pg.evaluate("!document.querySelector('#pp920AccountsBody [data-ppauth-reconnect]')"))
    check('paused: one card only (deduped)',pg.evaluate("document.querySelectorAll('.pp414-paused').length")==1)
    pg.evaluate("window.PayAviatorBillingLive=()=>true;window.openPayAviatorConnectedAccounts920()");pg.wait_for_timeout(400)
    check('billing live: Resubscribe button appears',pg.evaluate("!!document.querySelector('[data-pp414-resub]')"))
    pg.evaluate("window.PayAviatorSavePlaidItemHealth({items:[],errors:[]})")
    S.billing={'plan':'free','billingConfigured':True,'pausedBanks':2}
    pg.evaluate("window.PayAviatorAccountGate.refreshStatus()");pg.wait_for_timeout(800)
    pg.evaluate("window.openPayAviatorConnectedAccounts920()");pg.wait_for_timeout(300)
    check('billing/status pausedBanks count card',pg.evaluate("(document.querySelector('.pp414-paused')||{}).innerText||''").lower().startswith('2 banks paused'))
    pg.screenshot(path='/tmp/paused414.png')
    check('no page errors',not errs,errs[:3])
finally: srv.terminate()
sys.exit(0 if ok else 1)
