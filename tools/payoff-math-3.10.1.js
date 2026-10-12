(function(root){'use strict';
  // Payoff projections are estimates; balances remain authoritative from linked banks.
  const num=v=>{const n=Number(v);return Number.isFinite(n)&&n>0?n:0};
  const cents=v=>Math.round((num(v)+Number.EPSILON)*100);
  const dollars=v=>Math.round(v*100)/100;
  const defaultMin=d=>Math.min(num(d.balance),Math.max(25,dollars(num(d.balance)*0.03)));
  function monthly(balance, apr, payment) {
    let bal=cents(balance), rate=Math.min(num(apr),200)/1200, pay=cents(payment), interest=0, months=0, firstPayment=0, afterFirst=bal;
    if(!bal)return {months:0,interest:0,finished:true,pay1:0,after1:0};
    if(!pay)return {months:0,interest:0,finished:false,pay1:0,after1:dollars(bal/100)};
    while(bal>0&&months<1200){
      const charge=Math.round(bal*rate);interest+=charge;bal+=charge;
      const applied=Math.min(bal,pay);bal-=applied;months++;
      if(months===1){firstPayment=applied;afterFirst=bal}
      if(applied<=charge&&bal>0)return {months,interest:dollars(interest/100),finished:false,pay1:dollars(firstPayment/100),after1:dollars(afterFirst/100)};
    }
    return {months,interest:dollars(interest/100),finished:bal===0,pay1:dollars(firstPayment/100),after1:dollars(afterFirst/100)};
  }
  function planFor(rows, selectedId, extra=0, strategy='snowball') {
    const accounts=(Array.isArray(rows)?rows:[]).filter(d=>num(d.balance)>0).map(d=>({id:String(d.id),name:String(d.name||'Account'),balance:cents(d.balance),apr:Math.min(num(d.apr),200)/1200,min:cents(num(d.minPayment)||defaultMin(d)),interest:0}));
    const selected=accounts.find(d=>d.id===String(selectedId));if(!selected)return null;
    const initialMin=accounts.reduce((sum,d)=>sum+d.min,0),budget=initialMin+cents(extra);
    let months=0,pay1=0,after1=selected.balance,finished=false;
    const firstTarget=[...accounts].sort((a,b)=>a.balance-b.balance||b.apr-a.apr)[0];
    for(let month=1;month<=1200;month++){
      months=month;let available=budget;const spent=new Map();
      for(const d of accounts){if(d.balance<=0)continue;const charge=Math.round(d.balance*d.apr);d.balance+=charge;d.interest+=charge;}
      for(const d of accounts){if(d.balance<=0)continue;const paid=Math.min(d.balance,d.min,available);d.balance-=paid;available-=paid;spent.set(d.id,paid);}
      const order=accounts.filter(d=>d.balance>0).sort(strategy==='avalanche'?(a,b)=>b.apr-a.apr||a.balance-b.balance:(a,b)=>a.balance-b.balance||b.apr-a.apr);
      for(const d of order){if(available<=0)break;const paid=Math.min(d.balance,available);d.balance-=paid;available-=paid;spent.set(d.id,(spent.get(d.id)||0)+paid);}
      if(month===1){pay1=spent.get(selected.id)||0;after1=selected.balance;}
      if(selected.balance<=0){finished=true;break;}
    }
    return {months,interest:dollars(selected.interest/100),finished,pay1:dollars(pay1/100),after1:dollars(after1/100),extra:num(extra),min:dollars(Math.min(selected.min,cents(rows.find(d=>String(d.id)===selected.id)?.balance))/100),target:firstTarget.id,targetName:firstTarget.name,isTarget:firstTarget===selected};
  }
  function fullPayment(d){const balance=cents(d.balance), interest=Math.round(balance*Math.min(num(d.apr),200)/1200);return dollars((balance+interest)/100)}
  root.PayAviatorPayoffMath3101={monthly,planFor,fullPayment,defaultMin};
})(typeof window!=='undefined'?window:globalThis);
