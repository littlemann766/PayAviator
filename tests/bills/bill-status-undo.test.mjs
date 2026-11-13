/**
 * Bills tab: recurring paid/unpaid status and Undo.
 * Runs the real index.html in headless Chrome (no Playwright).
 * Usage: node tests/bills/bill-status-undo.test.mjs
 */
import { spawn } from 'node:child_process';
import http from 'node:http';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../..');
const CHROME = process.env.CHROME || '/usr/local/bin/google-chrome';
const fails = [];
function check(name, cond, extra) {
  if (cond) console.log('  ok  ', name);
  else { fails.push(name); console.log('  FAIL', name, extra === undefined ? '' : JSON.stringify(extra)); }
}

const server = http.createServer((req, res) => {
  const url = new URL(req.url, 'http://127.0.0.1');
  const file = path.normalize(path.join(ROOT, decodeURIComponent(url.pathname)));
  if (!file.startsWith(ROOT)) { res.writeHead(403); res.end(); return; }
  fs.readFile(file, (err, buf) => {
    if (err) { res.writeHead(404); res.end(); return; }
    res.writeHead(200, { 'content-type': file.endsWith('.html') ? 'text/html; charset=utf-8' : 'text/plain' });
    res.end(buf);
  });
});
await new Promise(res => server.listen(0, '127.0.0.1', res));
const port = server.address().port;
const debugPort = 9300 + Math.floor(Math.random() * 200);
const profile = fs.mkdtempSync('/tmp/pa-bill-status-');
const chrome = spawn(CHROME, [
  '--headless=new', '--no-sandbox', '--disable-gpu',
  `--remote-debugging-port=${debugPort}`,
  `--user-data-dir=${profile}`,
  'about:blank'
], { stdio: 'ignore' });

const sleep = ms => new Promise(r => setTimeout(r, ms));
let ws, seq = 0, pending = new Map();
function bind(socket) {
  ws = socket; seq = 0; pending = new Map();
  ws.addEventListener('message', ev => {
    const msg = JSON.parse(ev.data);
    if (msg.id && pending.has(msg.id)) { pending.get(msg.id)(msg); pending.delete(msg.id); }
  });
}
function send(method, params = {}) {
  return new Promise((resolve, reject) => {
    const id = ++seq;
    const timer = setTimeout(() => { pending.delete(id); reject(new Error('cdp timeout ' + method)); }, 20000);
    pending.set(id, msg => { clearTimeout(timer); resolve(msg); });
    ws.send(JSON.stringify({ id, method, params }));
  });
}
async function evaluate(expression, awaitPromise = false) {
  const msg = await send('Runtime.evaluate', { expression, awaitPromise, returnByValue: true });
  if (!msg.result) throw new Error('no result');
  if (msg.result.exceptionDetails) {
    const d = msg.result.exceptionDetails;
    throw new Error((d.exception?.description || d.text || 'exception').slice(0, 800));
  }
  return msg.result.result?.value;
}
async function connect(target) {
  const socket = new WebSocket(target.webSocketDebuggerUrl);
  await new Promise((resolve, reject) => { socket.addEventListener('open', resolve); socket.addEventListener('error', reject); });
  bind(socket);
  await send('Runtime.enable');
  await send('Page.enable');
}
async function pageTarget() {
  for (let i = 0; i < 50; i++) {
    try {
      const list = await (await fetch(`http://127.0.0.1:${debugPort}/json/list`)).json();
      const page = list.find(t => t.type === 'page' && t.webSocketDebuggerUrl);
      if (page) return page;
    } catch {}
    await sleep(100);
  }
  throw new Error('chrome page did not start');
}

const CARDS = `(()=>[...document.querySelectorAll('#list .bill')].map(el=>({
  id: el.dataset.billId||'',
  iso: el.dataset.billIso||'',
  name: el.querySelector('.name')?.textContent||'',
  meta: el.querySelector('.meta')?.textContent||'',
  flag: el.querySelector('.bill-due-flag')?.textContent||'',
  pill: el.querySelector('.bill-status-pill')?.textContent||'',
  pillClass: el.querySelector('.bill-status-pill')?.className||''
})))()`;

try {
  await connect(await pageTarget());
  await send('Page.navigate', { url: `http://127.0.0.1:${port}/index.html` });
  for (let i = 0; i < 80; i++) {
    if (await evaluate(`typeof window.decorateMainBillStatuses==='function' && !!(window.saveBillPaymentFromDialog&&window.saveBillPaymentFromDialog._v57)`)) break;
    await sleep(100);
  }
  check('status decorator and undo wrapper are installed', await evaluate(`typeof window.decorateMainBillStatuses==='function' && !!window.saveBillPaymentFromDialog._v57`));

  const single = await evaluate(`(() => {
    localStorage.clear();
    bills = [
      {id:'internet', name:'Internet', amount:105, due:'2026-11-10', recurring:true, recurrence:'monthly', paid:false, category:'Utilities', color:'#2563eb'},
      {id:'cs', name:'Child Support', amount:400, due:'2026-11-10', recurring:true, recurrence:'monthly', paid:false, category:'Family', color:'#dc2626'},
      {id:'amanda', name:'Amanda', amount:50, due:'2026-11-14', recurring:true, recurrence:'monthly', paid:false, category:'Personal', color:'#ca8a04'}
    ];
    billOverrides = {}; billPaidAmounts = {};
    calDate = new Date(2026, 10, 1);
    render();
    const before = ${CARDS};
    openBillPayment('internet','2026-11-10','');
    document.getElementById('billPaidInFullBtn').click();
    const paid = ${CARDS};
    openBillPayment('internet','2026-11-10','');
    document.getElementById('billMarkUnpaidBtn').click();
    const unpaid = ${CARDS};
    const internet = bills.find(b => b.id==='internet');
    return {before, paid, unpaid, status: billStatus(internet,'2026-11-10'), amount: billPaidAmount(internet,'2026-11-10'), toast: (document.getElementById('v57UndoToast')||{}).style?.display||''};
  })()`);
  const internetBefore = single.before.find(c => c.id === 'internet');
  const internetPaid = single.paid.find(c => c.id === 'internet');
  const internetUnpaid = single.unpaid.find(c => c.id === 'internet');
  check('unpaid recurring Internet shows Unpaid and Overdue, not Paid', internetBefore && internetBefore.meta.includes('Recurring • Unpaid') && internetBefore.pill === 'Overdue' && internetBefore.pill !== 'Paid', internetBefore);
  check('marking it paid removes it from the unpaid Bills list', !internetPaid, single.paid);
  check('marking it unpaid again shows Unpaid and Overdue, not a Paid pill', internetUnpaid && internetUnpaid.meta.includes('Recurring • Unpaid') && internetUnpaid.pill === 'Overdue' && internetUnpaid.pillClass.includes('overdue') && !internetUnpaid.pillClass.includes('paid'), internetUnpaid);
  check('mark unpaid stores a zero payment', single.status === 'unpaid' && single.amount === 0, single);
  check('mark unpaid offers undo', single.toast === 'flex', single.toast);
  const cs = single.unpaid.find(c => c.name === 'Child Support');
  const amanda = single.unpaid.find(c => c.name === 'Amanda');
  check('Child Support stays Overdue', cs && cs.pill === 'Overdue' && cs.meta.includes('Unpaid'), cs);
  check('Amanda stays due soon', amanda && amanda.flag === 'Due tomorrow' && amanda.pill === 'Due Soon', amanda);

  let undoLive = null;
  try {
    undoLive = await evaluate(`(async () => {
      window.PayAviatorConfirm = async () => true;
      await undoLastChange();
      const internet = bills.find(b => b.id==='internet');
      return {amount: billPaidAmount(internet,'2026-11-10'), status: billStatus(internet,'2026-11-10'), cards: ${CARDS}};
    })()`, true);
  } catch (e) {
    undoLive = { died: String(e.message || e) };
  }
  if (undoLive && !undoLive.died) {
    check('undo immediately restores the paid amount', undoLive.amount === 105 && undoLive.status === 'paid', undoLive);
    check('undo removes the unpaid Internet card', !undoLive.cards.some(c => c.id === 'internet'), undoLive.cards);
  }
  await sleep(700);
  try {
    const list = await (await fetch(`http://127.0.0.1:${debugPort}/json/list`)).json();
    const page = list.find(t => t.type === 'page' && t.webSocketDebuggerUrl);
    await connect(page);
    for (let i = 0; i < 40; i++) { if (await evaluate(`typeof billStatus==='function' && Array.isArray(bills)`)) break; await sleep(100); }
    await sleep(300);
    const after = await evaluate(`(() => {
      const internet = (bills||[]).find(b => b.id==='internet');
      return {amount: internet ? billPaidAmount(internet,'2026-11-10') : null, status: internet ? billStatus(internet,'2026-11-10') : null, cards: ${CARDS}};
    })()`);
    check('undo still shows paid after reload', after.status === 'paid' && after.amount === 105 && !after.cards.some(c => c.id === 'internet'), after);
  } catch (e) {
    if (!undoLive || undoLive.died) check('undo restores the paid bill', false, undoLive || String(e));
  }

  const dup = await evaluate(`(() => {
    bills = [
      {id:'internet-old', name:'Internet', amount:105, due:'2026-11-10', recurring:true, recurrence:'monthly', paid:true, category:'Utilities', color:'#16a34a'},
      {id:'internet', name:'Internet', amount:105, due:'2026-11-10', recurring:true, recurrence:'monthly', paid:false, category:'Utilities', color:'#2563eb'},
      {id:'cs', name:'Child Support', amount:400, due:'2026-11-10', recurring:true, recurrence:'monthly', paid:false, category:'Family', color:'#dc2626'},
      {id:'amanda', name:'Amanda', amount:50, due:'2026-11-14', recurring:true, recurrence:'monthly', paid:false, category:'Personal', color:'#ca8a04'}
    ];
    billOverrides = {'internet-old|2026-11-10': {paid:true}};
    billPaidAmounts = {'internet-old|2026-11-10': 105};
    calDate = new Date(2026, 10, 1);
    render();
    const cards = ${CARDS};
    const moved = (() => {
      bills = [
        {id:'internet', name:'Internet', amount:105, due:'2026-11-10', recurring:true, recurrence:'monthly', paid:false, category:'Utilities', color:'#2563eb'},
        {id:'once-internet-2026-11-10', name:'Internet', amount:105, due:'2026-11-10', recurring:false, paid:false, category:'Utilities', color:'#2563eb', instanceOf:'internet', instanceOriginal:'2026-11-10'}
      ];
      billOverrides = {'internet|2026-11-10': {paid:true, deleted:true, movedTo:'2026-11-10'}, 'once-internet-2026-11-10|2026-11-10': {paid:false}};
      billPaidAmounts = {'once-internet-2026-11-10|2026-11-10': 0};
      render();
      return ${CARDS};
    })();
    const src = bills.find(b => b.id==='internet');
    setBillPaidOnDate(src, '2026-11-10', false);
    const kept = billOverrides['internet|2026-11-10'];
    return {cards, moved, kept};
  })()`);
  const dupInternet = dup.cards.filter(c => c.name === 'Internet');
  check('same-name unpaid Internet is not given the other bill Paid pill', dupInternet.length === 1 && dupInternet[0].id === 'internet' && dupInternet[0].meta.includes('Recurring • Unpaid') && dupInternet[0].pill === 'Overdue', dup.cards);
  const movedCard = dup.moved.find(c => c.id === 'once-internet-2026-11-10');
  check('a moved unpaid copy is Overdue, not Paid', movedCard && movedCard.pill === 'Overdue' && movedCard.meta.includes('Unpaid'), dup.moved);
  check('marking unpaid keeps a moved occurrence deleted', dup.kept && dup.kept.deleted === true && dup.kept.paid === false && dup.kept.movedTo === '2026-11-10', dup.kept);
} finally {
  try { chrome.kill('SIGKILL'); } catch {}
  server.close();
  fs.rmSync(profile, { recursive: true, force: true });
}

if (fails.length) {
  console.log('FAIL ' + fails.length);
  process.exit(1);
}
console.log('PASS');
