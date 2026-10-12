(function(){
'use strict';
// Independent Payoff Planner screen. The old, overlapping redraw modules remain
// inactive because the previous planner dialog is never opened by this screen.
const ROOT='pa3102Planner', DEBTS='payaviator_debt_planner_v20425', PREFS='payaviator_debt_planner_settings_v20425', BANK='payaviator_connected_accounts_v1';
const $=id=>document.getElementById(id), n=v=>{const x=Number(v);return Number.isFinite(x)&&x>0?x:0};
const round=v=>Math.round((n(v)+Number.EPSILON)*100)/100, cents=v=>Math.round(round(v)*100);
const money=v=>new Intl.NumberFormat('en-US',{style:'currency',currency:'USD'}).format(Number(v)||0);
const esc=v=>String(v==null?'':v).replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const read=(k,f)=>{try{const v=JSON.parse(localStorage.getItem(k)||'null');return v??f}catch(_){return f}};
const rows=()=>{const v=read(DEBTS,[]);return Array.isArray(v)?v:[]};
const saveRows=x=>{if(typeof window.ppDebtSaveRows==='function')window.ppDebtSaveRows(x);else localStorage.setItem(DEBTS,JSON.stringify(x));};
const prefs=()=>{const p=read(PREFS,{});return {strategy:p.strategy==='avalanche'?'avalanche':'snowball',extra:round(p.extra)}};
const savePrefs=p=>{if(typeof window.ppDebtSavePrefs==='function')window.ppDebtSavePrefs(p);else localStorage.setItem(PREFS,JSON.stringify(p));};
const minFor=d=>Math.min(n(d.balance),round(d.minPayment)||Math.max(1,Math.min(n(d.balance),Math.max(25,round(n(d.balance)*.03)))));
const cards=()=>{const v=read(BANK,[]);return (Array.isArray(v)?v:[]).filter(a=>{const t=String(a.type||'').toLowerCase(),sub=String(a.subtype||'').toLowerCase();return t==='credit'||t==='loan'||/credit|mortgage|student|auto loan/.test(sub)});};
const bankId=a=>String(a.id||a.account_id||'');
const used=a=>round(a.balanceUsed??a.balance_used??a.current??a.balances?.current);
const limit=a=>round(a.creditLimit??a.credit_limit??a.limit??a.balances?.limit);
let selectedId='',editor='',view='main',pendingRemove='',syncing=false,oldOverflow='';
const getSelected=()=>{const all=rows();return all.find(d=>String(d.id)===selectedId)||all[0]||null};
const outstanding=items=>items.reduce((s,x)=>s+Math.max(0,cents(x.balance)),0)/100;
// Accurate cent-rounded interest and fixed combined monthly budget. Paid-off
// minimums roll into the next priority account (Snowball or Avalanche).
function simulate(items,settings){
 const all=items.map(d=>({id:String(d.id),name:String(d.name||'Balance'),balance:cents(d.balance),rate:Math.min(n(d.apr),200)/1200,min:cents(minFor(d)),interest:0,months:0}));
 const positive=all.filter(d=>d.balance>0),initial=all.reduce((s,d)=>s+d.balance,0),minBudget=positive.reduce((s,d)=>s+d.min,0),budget=minBudget+cents(settings.extra);let paid=0,interest=0,month=0;
 if(initial===0)return {finished:true,months:0,interest:0,monthlyBudget:0,byId:{},total:0};
 if(budget<=0)return {finished:false,months:null,interest:null,monthlyBudget:0,byId:{},total:initial/100};
 const byId={};let stagnant=0;
 for(month=1;month<=600;month++){
  let remaining=budget,charged=0,spent=0;
  for(const d of all){if(d.balance<=0)continue;const charge=Math.round(d.balance*d.rate);d.balance+=charge;d.interest+=charge;interest+=charge;charged+=charge}
  for(const d of all){if(d.balance<=0)continue;const pay=Math.min(d.balance,d.min,remaining);d.balance-=pay;remaining-=pay;spent+=pay}
  const priority=all.filter(d=>d.balance>0).sort(settings.strategy==='avalanche'?((a,b)=>b.rate-a.rate||a.balance-b.balance):((a,b)=>a.balance-b.balance||b.rate-a.rate));
  for(const d of priority){if(remaining<=0)break;const pay=Math.min(remaining,d.balance);d.balance-=pay;remaining-=pay;spent+=pay}
  paid+=spent;
  for(const d of all)if(d.balance===0&&!Object.hasOwn(byId,d.id))byId[d.id]={months:month,interest:d.interest/100};
  if(all.every(d=>d.balance<=0))return {finished:true,months:month,interest:interest/100,monthlyBudget:budget/100,byId,total:initial/100};
  if(spent<=charged)stagnant++;else stagnant=0;
  if(stagnant>=2)break;
 }
 return {finished:false,months:null,interest:null,monthlyBudget:budget/100,byId,total:initial/100};
}
function payoffDate(months){if(months===0)return 'Paid off';if(months==null)return 'Payment too low';const d=new Date();d.setDate(1);d.setMonth(d.getMonth()+months);return d.toLocaleDateString('en-US',{month:'short',year:'numeric'})}
function refreshLinked(){
 const bank=cards();if(!bank.length)return false;const mapped=new Map(bank.map(a=>[bankId(a),a]));let changed=false;const list=rows();
 for(const d of list){if(!d.linkedAccountId)continue;const a=mapped.get(String(d.linkedAccountId));if(!a)continue;
  const current=a.balanceUsed??a.balance_used??a.current??a.balances?.current;
  const bal=used(a),li=limit(a),last=a.lastSync||'';
  if(current!=null&&Number.isFinite(Number(current))&&Number(current)>=0&&bal!==round(d.balance)){d.balance=bal;changed=true}
  if(!d.creditLimitManual&&li>0&&round(d.creditLimit??d.limit)!==li){d.creditLimit=li;d.limit=li;changed=true}
  if(last&&last!==d.linkedLastSync){d.linkedLastSync=last;changed=true}
 }
 if(changed)saveRows(list);return changed;
}
function create(){let root=$(ROOT);if(root)return root;root=document.createElement('div');root.id=ROOT;root.setAttribute('role','dialog');root.setAttribute('aria-modal','true');root.setAttribute('aria-label','Payoff Planner');root.hidden=true;
 root.innerHTML=`<section class="pa3102-shell"><header class="pa3102-head"><div><h2>Payoff Planner</h2><small>Credit cards & loans</small></div><button type="button" data-act="close" class="pa3102-close" aria-label="Close Payoff Planner">×</button></header><main class="pa3102-body" id="pa3102Body"></main><footer class="pa3102-footer"><span>Estimates only · No automatic bank payments</span></footer></section>`;
 document.body.appendChild(root);root.addEventListener('click',onClick);root.addEventListener('change',onChange);root.addEventListener('input',onInput);root.addEventListener('touchstart',e=>{const dial=e.target.closest('.pa3102-gauge');if(!dial)return;root.dataset.swipeX=String(e.touches[0].clientX);root.dataset.swipeY=String(e.touches[0].clientY)},{passive:true});
 root.addEventListener('touchend',e=>{if(!root.dataset.swipeX||!e.target.closest('.pa3102-gauge'))return;const dx=e.changedTouches[0].clientX-Number(root.dataset.swipeX),dy=e.changedTouches[0].clientY-Number(root.dataset.swipeY);delete root.dataset.swipeX;if(Math.abs(dx)>55&&Math.abs(dx)>Math.abs(dy)*1.4)selectRelative(dx<0?1:-1)},{passive:true});
 return root;
}
function open(){const root=create();if(root.hidden){oldOverflow=document.body.style.overflow;document.body.style.overflow='hidden'}root.hidden=false;view='main';refreshLinked();draw();$('pa3102Body').scrollTop=0;try{root.querySelector('[data-act="close"]').focus({preventScroll:true})}catch(_){}
 // Refresh is asynchronous and cannot discard saved local rows if Plaid is offline.
 if(typeof window.PayAviatorSyncLiveBank982==='function'&&!syncing){syncing=true;Promise.resolve().then(()=>window.PayAviatorSyncLiveBank982()).then(()=>{refreshLinked();if(!root.hidden&&view==='main')draw()}).catch(()=>{}).finally(()=>{syncing=false})}
}
function close(){const root=$(ROOT);if(!root||root.hidden)return;root.hidden=true;document.body.style.overflow=oldOverflow}
function setView(v){view=v;draw();$('pa3102Body').scrollTop=0}
function setSelected(id){selectedId=String(id);draw();$('pa3102Body').scrollTop=0}
function selectRelative(d){const list=rows();if(!list.length)return;const i=Math.max(0,list.findIndex(x=>String(x.id)===String(getSelected()?.id)));selectedId=String(list[(i+d+list.length)%list.length].id);draw()}
function gauge(percent,display){let ticks='',arcs='';const segs=[[0,.30,'#22c55e'],[.30,.55,'#eab308'],[.55,.75,'#fb923c'],[.75,1,'#ef4444']];const point=(angle,r)=>{const rad=angle*Math.PI/180;return[200+r*Math.cos(rad),206+r*Math.sin(rad)]};const path=(a,b)=>{const p=point(a,155),q=point(b,155);return `M${p[0].toFixed(2)},${p[1].toFixed(2)} A155,155 0 0 1 ${q[0].toFixed(2)},${q[1].toFixed(2)}`};
 for(const [a,b,color] of segs)arcs+=`<path d="${path(180+180*a,180+180*b)}" fill="none" stroke="${color}" stroke-width="28"/>`;
 for(let i=0;i<=20;i++){const ang=180+i*9,p=point(ang,135),q=point(ang,i%5===0?113:122);ticks+=`<line x1="${p[0]}" y1="${p[1]}" x2="${q[0]}" y2="${q[1]}" stroke="#081a32" stroke-width="${i%5===0?3.5:2}"/>`}
 const ang=180+Math.max(0,Math.min(100,percent??0))*1.8,tip=point(ang,105);
 return `<svg viewBox="0 0 400 250" role="img" aria-label="Credit used ${esc(display)}"><path d="${path(180,360)}" fill="none" stroke="#cbd5e1" stroke-width="40"/>${arcs}${ticks}${percent==null?'':`<line x1="200" y1="206" x2="${tip[0]}" y2="${tip[1]}" stroke="#fff" stroke-width="8" stroke-linecap="round"/>`}<circle cx="200" cy="206" r="15" fill="#d9e3ed" stroke="#071a32" stroke-width="7"/><text x="47" y="237" fill="#d1ddec" font-size="17" text-anchor="middle">0%</text><text x="353" y="237" fill="#d1ddec" font-size="17" text-anchor="middle">100%</text></svg>`
}
function renderMain(){const list=rows(),p=prefs(),d=getSelected();if(d)selectedId=String(d.id);const total=outstanding(list),active=list.filter(x=>n(x.balance)>0);
 const snow=simulate(list,{...p,strategy:'snowball'}),ava=simulate(list,{...p,strategy:'avalanche'}),plan=p.strategy==='avalanche'?ava:snow;
 const creditLimit=d?round(d.creditLimit??d.limit):0,usedValue=d?round(d.balance):0,pct=creditLimit>0?Math.round(usedValue/creditLimit*1000)/10:null,avail=creditLimit>0?Math.max(0,creditLimit-usedValue):null;
 const selectText=list.length>1?`${list.findIndex(x=>String(x.id)===selectedId)+1} of ${list.length}`:'1 account';
 const activeProj=d&&usedValue<=0?'Paid off':d&&plan.byId[String(d.id)]?payoffDate(plan.byId[String(d.id)].months):!d?'Add a balance':'Payment too low';
 const summary=list.length?`<div class="pa3102-gauge" aria-label="Selected account credit gauge"><div class="pa3102-accountnav"><button data-act="prev" aria-label="Previous balance" ${list.length<2?'disabled':''}>‹</button><div><b>${esc(d.name||'Account')}</b><small>${esc(d.linkedInstitution||'Manual balance')} · ${esc(selectText)}</small></div><button data-act="next" aria-label="Next balance" ${list.length<2?'disabled':''}>›</button></div>${gauge(pct,pct==null?'limit unknown':pct+'%')}<div class="pa3102-gaugeread"><b>${pct==null?'—':pct+'%'}</b><span>${pct==null?'CREDIT LIMIT UNKNOWN':'CREDIT USED'}</span></div><div class="pa3102-stats"><div><small>Available credit</small><strong>${avail==null?'Not set':money(avail)}</strong></div><div><small>Balance used</small><strong>${money(usedValue)}</strong></div><div><small>Payoff estimate</small><strong>${activeProj}</strong></div></div><div class="pa3102-gaugefoot"><span>${creditLimit>0?'Limit: '+money(creditLimit):'Enter a credit limit to calculate utilization'}</span>${d.linkedAccountId?'<span>Connected bank balance</span>':''}</div></div>`:
 `<div class="pa3102-empty">No balances in your planner yet. Add a credit card or loan to begin. Connected banks can also be imported.</div>`;
 return `${summary}<section class="pa3102-panel"><div class="pa3102-sectiontitle">Payoff method</div><div class="pa3102-methods"><button type="button" class="${p.strategy==='snowball'?'selected':''}" data-act="strategy" data-value="snowball"><b>Snowball</b><small>Smallest balance first</small></button><button type="button" class="${p.strategy==='avalanche'?'selected':''}" data-act="strategy" data-value="avalanche"><b>Avalanche</b><small>Highest interest rate first</small></button></div><label class="pa3102-field" for="pa3102Extra">Extra monthly payment <input type="number" id="pa3102Extra" min="0" step="0.01" inputmode="decimal" value="${p.extra}"></label><small class="pa3102-tip">Added to your combined minimum payments, then directed to the priority balance.</small></section>
 <section class="pa3102-panel"><div class="pa3102-sectiontitle">Your payoff plan</div><div class="pa3102-plan"><div><small>Remaining balances</small><b>${money(total)}</b></div><div><small>Monthly plan budget</small><b>${money(plan.monthlyBudget)}</b></div><div><small>Estimated debt-free date</small><b>${list.length?payoffDate(plan.months):'—'}</b></div><div><small>Estimated interest</small><b>${plan.interest==null?'—':money(plan.interest)}</b></div></div><div class="pa3102-compare">Snowball: <b>${list.length?payoffDate(snow.months):'—'}</b> · Avalanche: <b>${list.length?payoffDate(ava.months):'—'}</b>${snow.interest!=null&&ava.interest!=null?`<div>Estimated interest savings with Avalanche: <b>${money(Math.max(0,snow.interest-ava.interest))}</b></div>`:''}</div><small class="pa3102-tip">Estimated with current balances, APRs, monthly minimums, and fixed total monthly budget. Actual interest and payments may differ.</small></section>
 <section class="pa3102-panel"><div class="pa3102-toolbar"><div class="pa3102-sectiontitle">Accounts (${list.length})</div><button type="button" data-act="add" class="pa3102-primary">+ Add Account</button></div><button type="button" data-act="import" class="pa3102-secondary pa3102-full">Link from connected banks</button>${list.length?`<div class="pa3102-list">${list.map(x=>`<div class="pa3102-account ${String(d.id)===String(x.id)?'active':''}"><button type="button" data-act="select" data-id="${esc(x.id)}"><strong>${esc(x.name||'Account')}</strong><span>${money(n(x.balance))} · ${round(x.apr)}% APR${x.linkedAccountId?' · Bank-linked':''}</span></button><button type="button" data-act="edit" data-id="${esc(x.id)}" aria-label="Edit ${esc(x.name)}">Edit</button></div>`).join('')}</div>`:''}</section><div class="pa3102-bottompad"></div>`;
}
function renderEditor(){const editing=editor&&rows().find(x=>String(x.id)===editor),d=editing||{},linked=!!d.linkedAccountId;
 return `<section class="pa3102-panel"><h3>${editing?'Edit balance':'Add balance'}</h3>${linked?'<p class="pa3102-tip">Bank-linked balances refresh from your institution. Unlink to edit the balance manually.</p>':''}<label class="pa3102-field">Account name<input id="pa3102Name" maxlength="100" placeholder="Credit card or loan" value="${esc(d.name||'')}"></label><label class="pa3102-field">Balance used ($)<input id="pa3102Balance" type="number" step="0.01" min="0" value="${round(d.balance)}" ${linked?'readonly':''}></label><label class="pa3102-field">Credit limit ($), optional<input id="pa3102Limit" type="number" step="0.01" min="0" value="${round(d.creditLimit??d.limit)}"></label><div class="pa3102-two"><label class="pa3102-field">APR (%)<input id="pa3102APR" type="number" step="0.01" min="0" max="200" value="${round(d.apr)}"></label><label class="pa3102-field">Required monthly minimum ($)<input id="pa3102Min" type="number" step="0.01" min="0" value="${round(d.minPayment)}"></label></div><p class="pa3102-tip">These inputs are for estimates. Editing them does not modify your bank account or make a payment.</p><div class="pa3102-row"><button data-act="cancel" type="button" class="pa3102-secondary">Cancel</button><button data-act="save" type="button" class="pa3102-primary">Save Balance</button></div>${editing?`<hr/><div class="pa3102-row">${linked?'<button type="button" data-act="unlink" class="pa3102-secondary">Unlink bank</button>':'<button type="button" data-act="payment" class="pa3102-secondary">Record Payment</button>'}<button data-act="remove" type="button" class="pa3102-danger">Remove Balance</button></div>`:''}</section>`
}
function renderImport(){const bank=cards(),list=rows();return `<section class="pa3102-panel"><h3>Link a connected bank account</h3><p class="pa3102-tip">Choose a credit card or loan already connected through Plaid. PayAviator will read its latest reported balance; no bank credentials are saved in this planner.</p>${bank.length?bank.map(a=>{const id=bankId(a),already=list.some(d=>String(d.linkedAccountId)===id),label=a.name||a.officialName||'Bank account';return `<button type="button" class="pa3102-bank" data-act="pickbank" data-id="${esc(id)}" ${!id||already?'disabled':''}><b>${esc(label)}</b><span>${esc(a.institutionName||a.institution||'Connected bank')}${a.mask?' ·•••• '+esc(a.mask):''}</span><strong>${money(used(a))}</strong><small>${already?'Already linked':limit(a)>0?'Limit '+money(limit(a)):'Credit limit unavailable'}</small></button>`}).join(''):'<div class="pa3102-empty">No connected credit cards or loans have been synced. Connect your institution in Connected Banking, then return here.</div>'}<div class="pa3102-row"><button type="button" class="pa3102-secondary" data-act="cancel">Back</button><button type="button" class="pa3102-primary" data-act="refresh">Refresh banks</button></div></section>`}
function renderPayment(){const d=rows().find(x=>String(x.id)===editor);return `<section class="pa3102-panel"><h3>Record a payment</h3><p>${esc(d?.name||'Account')} · ${money(n(d?.balance))} remaining</p><label class="pa3102-field">Payment amount ($)<input type="number" id="pa3102Payment" min="0.01" step="0.01" inputmode="decimal" value="${round(Math.min(n(d?.balance),minFor(d||{})))}"></label><p class="pa3102-tip">This only updates your manually tracked balance. It does not send money to the lender.</p><div class="pa3102-row"><button type="button" class="pa3102-secondary" data-act="editback">Cancel</button><button type="button" class="pa3102-primary" data-act="savepayment">Record</button></div></section>`}
function renderConfirm(){const d=rows().find(x=>String(x.id)===pendingRemove);return `<section class="pa3102-panel"><h3>Remove balance?</h3><p>Remove <b>${esc(d?.name||'this balance')}</b> from the Payoff Planner? Your banking connections are not removed.</p><div class="pa3102-row"><button type="button" data-act="editback" class="pa3102-secondary">Keep</button><button type="button" data-act="confirmremove" class="pa3102-danger">Remove</button></div></section>`}
function draw(){const root=create();if(root.hidden)return;const body=$('pa3102Body');if(!body)return;const y=body.scrollTop;body.innerHTML=view==='edit'?renderEditor():view==='import'?renderImport():view==='payment'?renderPayment():view==='remove'?renderConfirm():renderMain();body.scrollTop=y}
function notify(msg){const root=$(ROOT);if(!root)return;let note=root.querySelector('.pa3102-msg');if(!note){note=document.createElement('div');note.className='pa3102-msg';root.querySelector('.pa3102-shell').appendChild(note)}note.textContent=msg;note.hidden=false;clearTimeout(root.__msg);root.__msg=setTimeout(()=>{note.hidden=true},3300)}
function saveEditor(){const name=$('pa3102Name')?.value.trim(),bal=Number($('pa3102Balance')?.value),apr=Number($('pa3102APR')?.value),li=Number($('pa3102Limit')?.value),minimum=Number($('pa3102Min')?.value);if(!name)return notify('Please enter an account name.');if(!Number.isFinite(bal)||bal<0||!Number.isFinite(apr)||apr<0||apr>200||!Number.isFinite(li)||li<0||!Number.isFinite(minimum)||minimum<0)return notify('Enter valid amounts and an APR between 0 and 200%.');let list=rows(),old=editor&&list.find(x=>String(x.id)===editor),item=old||{id:'debt-'+Date.now()+'-'+Math.random().toString(36).slice(2,7)};
 const manuallyChangedLimit=li>0&&(!old||round(old.creditLimit??old.limit)!==round(li));
 Object.assign(item,{name,apr:round(apr),minPayment:round(minimum),creditLimit:round(li),limit:round(li),creditLimitManual:!!old?.creditLimitManual||manuallyChangedLimit});if(!item.linkedAccountId)item.balance=round(bal);if(!old)list.push(item);saveRows(list);selectedId=String(item.id);setView('main')}
function onClick(e){const b=e.target.closest('[data-act]');if(!b||!$(ROOT).contains(b))return;const a=b.dataset.act,id=b.dataset.id;
 if(a==='close')return close();if(a==='cancel')return setView('main');if(a==='prev'||a==='next')return selectRelative(a==='next'?1:-1);
 if(a==='select')return setSelected(id);if(a==='strategy'){const p=prefs();p.strategy=b.dataset.value;savePrefs(p);return draw()}
 if(a==='add'){editor='';return setView('edit')};if(a==='edit'){editor=id;return setView('edit')};if(a==='save')return saveEditor();
 if(a==='import')return setView('import');if(a==='pickbank'){const bank=cards().find(x=>bankId(x)===id);if(!bank)return;const list=rows();if(list.some(d=>String(d.linkedAccountId)===id))return notify('This bank account is already linked.');const card={id:'linked-'+Date.now()+'-'+Math.random().toString(36).slice(2,7),name:bank.name||bank.officialName||'Connected card',balance:used(bank),creditLimit:limit(bank),limit:limit(bank),apr:0,minPayment:0,linkedAccountId:id,linkedInstitution:bank.institutionName||bank.institution||'',linkedMask:bank.mask||'',linkedLastSync:bank.lastSync||''};list.push(card);saveRows(list);selectedId=card.id;editor=card.id;setView('edit');return notify('Linked. Enter APR and minimum payment to improve the estimate.')}
 if(a==='refresh'){if(syncing)return notify('Bank refresh is already running.');if(typeof window.PayAviatorSyncLiveBank982!=='function')return notify('Connected Banking is unavailable right now.');syncing=true;Promise.resolve().then(()=>window.PayAviatorSyncLiveBank982()).then(()=>{refreshLinked();draw();notify('Bank account list refreshed.')}).catch(()=>notify('Bank sync failed. Previously saved accounts are safe.')).finally(()=>{syncing=false});return}
 if(a==='payment')return setView('payment');if(a==='editback')return setView('edit');if(a==='remove'){pendingRemove=editor;return setView('remove')};
 if(a==='confirmremove'){const list=rows().filter(d=>String(d.id)!==String(pendingRemove));saveRows(list);selectedId=String(list[0]?.id||'');pendingRemove='';return setView('main')}
 if(a==='unlink'){const list=rows(),d=list.find(x=>String(x.id)===editor);if(d){delete d.linkedAccountId;delete d.linkedInstitution;delete d.linkedMask;delete d.linkedLastSync;saveRows(list)}return setView('edit')}
 if(a==='savepayment'){const amount=Number($('pa3102Payment')?.value),list=rows(),d=list.find(x=>String(x.id)===editor);if(!d||d.linkedAccountId)return notify('Only manually tracked balances can be adjusted here.');if(!Number.isFinite(amount)||amount<=0)return notify('Enter a payment amount above $0.');d.balance=Math.max(0,Math.round((n(d.balance)-amount)*100)/100);saveRows(list);return setView('main')}
}
function onChange(e){if(e.target.id==='pa3102Extra'){const p=prefs();p.extra=round(e.target.value);savePrefs(p);draw()}}
function onInput(e){if(e.target.id==='pa3102Extra'){const p=prefs();if(e.target.value==='')return;p.extra=round(e.target.value);savePrefs(p);
 // Update just the projection, not the focused input. Full redraw on change.
 }}
const previousBack=window.payAviatorHandleAndroidBack;window.payAviatorHandleAndroidBack=function(){if($(ROOT)&&!$(ROOT).hidden){close();return true}return typeof previousBack==='function'?previousBack():false};
window.openDebtPayoffPlanner=open;
window.PayAviatorPayoffPlanner3102={open,close,simulate,refreshLinked,rows,prefs};
// Let actual synced balances update a currently visible planner without a timer
// or a MutationObserver that would re-create its controls while being edited.
window.addEventListener('payaviator:accounts-updated',()=>{refreshLinked();if($(ROOT)&&!$(ROOT).hidden&&view==='main')draw()});
})();
