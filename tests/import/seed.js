(()=>{
const t=new Date(); const y=t.getFullYear(), m=t.getMonth();
const iso=(d)=>new Date(y,m,d).toISOString().slice(0,10);
const pad=n=>String(n).padStart(2,'0');
const D=d=>`${y}-${pad(m+1)}-${pad(d)}`;
const bill=(id,name,amount,day,cat,color,rec='monthly',extra={})=>({id,name,amount,due:D(day),recurring:true,recurrence:rec,paid:false,color,category:cat,notes:'',autopay:false,notify:false,notifyDaysBefore:[1],notifyTime:'09:00',notifySound:'default',notifyVibrate:true,dateMoves:{},...extra});
const bills=[
 bill('b-rent','Rent',1450,1,'Housing','#3b82f6'),
 bill('b-car','Car Payment',389.42,5,'Transportation','#8b5cf6'),
 bill('b-ins','Car Insurance',142.10,8,'Insurance','#06b6d4'),
 bill('b-power','Electric (Duke Energy)',118.37,12,'Utilities','#f59e0b'),
 bill('b-net','Internet',74.99,15,'Utilities','#10b981'),
 bill('b-phone','Phone',85,18,'Utilities','#ec4899'),
 bill('b-netflix','Netflix',15.49,21,'Subscriptions','#ef4444'),
 bill('b-spotify','Spotify',11.99,22,'Subscriptions','#22c55e'),
 bill('b-gym','Gym Membership',29.99,25,'Health','#f97316'),
 bill('b-cc','Credit Card',150,27,'Debt','#64748b'),
];
const paid={}; const ov={};
['b-rent','b-car','b-ins'].forEach(id=>{const b=bills.find(x=>x.id===id); const k=id+'|'+b.due; paid[k]=b.amount; ov[k]={paid:true};});
localStorage.setItem('payAviator_v1',JSON.stringify(bills));
localStorage.setItem('payAviator_bills_rev_v1',String(Date.now()));
// find a Friday on/before the 3rd of the month for biweekly checks
let first=new Date(y,m,1); while(first.getDay()!==5) first.setDate(first.getDate()+1);
first.setDate(first.getDate()-14);
const fd=`${first.getFullYear()}-${pad(first.getMonth()+1)}-${pad(first.getDate())}`;
localStorage.setItem('payAviator_paychecks_v1',JSON.stringify([{id:'pc-1',amount:2180.55,date:fd,frequency:'biweekly',incomeType:'salary',annualSalary:72000}]));
localStorage.setItem('payAviator_income_type_v1','salary');
localStorage.setItem('payAviator_annual_salary_v1','72000');
const sp=(id,name,amount,day,cat)=>({id,name,amount,date:D(day),enteredAt:new Date(y,m,day).toISOString(),source:'manual',flow:'spending',category:cat,notes:''});
const today=t.getDate();
const spend=[sp('s1','Kroger',86.43,2,'Groceries'),sp('s2','Shell Gas',48.20,3,'Gas'),sp('s3','Chipotle',14.85,4,'Dining'),sp('s4','Target',62.17,6,'Shopping'),sp('s5','Starbucks',6.45,7,'Dining'),sp('s6','Walmart Groceries',104.92,9,'Groceries'),sp('s7','Amazon',39.99,Math.min(10,today),'Shopping'),sp('s8','Shell Gas',44.10,Math.min(10,today),'Gas')].filter(x=>Number(x.date.slice(8))<=today);
localStorage.setItem('payAviator_budget_spending_v1',JSON.stringify(spend));
localStorage.setItem('payAviator_bill_paid_amounts_v1',JSON.stringify(paid));
localStorage.setItem('payAviator_bill_overrides_v1',JSON.stringify(ov));
localStorage.setItem('payAviator_onboarding_v1_done','1');
localStorage.setItem('payaviator_cash_wallet_v950',JSON.stringify({saved:250,spendable:1840.62}));
localStorage.setItem('payaviator_tip_popup_seen_v1','1');
localStorage.setItem('payaviator_connected_accounts_v1',JSON.stringify([{id:'acc-demo-chk',institutionName:'Demo Credit Union',name:'Everyday Checking',mask:'4821',type:'depository',subtype:'checking',available:2486.17,current:2486.17,balance:2486.17}]));
localStorage.setItem('payaviator_debt_planner_v20425',JSON.stringify([{id:'debt-1',name:'Visa Card',balance:3240.55,apr:24.99,minPayment:98,creditLimit:8000,limit:8000,snowballMinPayment:98,avalanchePayment:250},{id:'debt-2',name:'Store Card',balance:612.3,apr:29.99,minPayment:35,creditLimit:1500,limit:1500,snowballMinPayment:35,avalanchePayment:60},{id:'debt-3',name:'Car Loan',balance:11850,apr:6.4,minPayment:389.42}]));
localStorage.setItem('payaviator_debt_planner_settings_v20425',JSON.stringify({strategy:'avalanche',extra:150}));
localStorage.setItem('payaviator_debt_payment_overrides_v1321',JSON.stringify({'debt-1':{minPayment:180,avalanchePayment:300},'debt-2':{minPayment:45,avalanchePayment:90},'debt-3':{minPayment:389.42,avalanchePayment:389.42}}));
return {bills:bills.length,spend:spend.length,fd};
})()
