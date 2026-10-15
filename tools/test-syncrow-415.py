#!/usr/bin/env python3
"""4.1.5 Settings Cloud sync row: mocked backend (in-memory fake of the cloud-sync-pause-banks contract), run from the repo root."""
import sys,subprocess,time,json,re
from playwright.sync_api import sync_playwright
srv=subprocess.Popen(['python3','-m','http.server','8853'],cwd='.',stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL);time.sleep(1)
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
    pg.goto('http://localhost:8853/index.html');pg.evaluate(INIT);pg.reload();pg.wait_for_timeout(1500)
    pg.evaluate("document.querySelector('.mb119-nav[data-view=settings]').click()");pg.wait_for_timeout(500)
    t=lambda:pg.evaluate("(document.getElementById('pa415SyncRow')||{}).innerText||''")
    check('row visible when signed out',pg.evaluate("!!document.getElementById('pa415SyncRow')") and 'Not signed in' in t(),t())
    pg.evaluate(SIGNIN);pg.wait_for_timeout(2500)
    check('sync ran right after sign-in',any(c[1].startswith('/api/sync/changes') for c in S.calls),S.calls[:3])
    check('row shows email + last synced',('a@yahoo.com' in t()) and 'Last synced' in t() and 'Not yet' not in t(),t())
    n=len(S.calls);pg.evaluate("document.querySelector('[data-pa415-sync]').click()");pg.wait_for_timeout(1500)
    check('Sync now calls the server',len(S.calls)>n)
    S.status=(401,'SIGN_IN_REQUIRED');pg.evaluate("document.querySelector('[data-pa415-sync]').click()");pg.wait_for_timeout(1500)
    check('401 shows error text',('sign in again' in t().lower()) and 'not signed in' in t().lower(),t())
    pg.screenshot(path='/tmp/syncrow415.png')
    check('no page errors',not errs,errs[:3])
finally: srv.terminate()
sys.exit(0 if ok else 1)
