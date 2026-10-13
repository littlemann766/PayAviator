from playwright.sync_api import sync_playwright
ok=True
with sync_playwright() as p:
    b=p.chromium.launch(executable_path='/usr/bin/google-chrome',args=['--no-sandbox'])
    for vw,vh in [(390,844),(360,640)]:
        pg=b.new_page(viewport={'width':vw,'height':vh}); errs=[]; pg.on('pageerror',lambda e:errs.append(str(e)))
        pg.goto('http://localhost:8811/index.html')
        pg.evaluate("localStorage.clear();localStorage.setItem('payAviator_onboarding_v1_done','1');localStorage.setItem('payaviator_tip_popup_seen_v1','true');localStorage.setItem('payAviator_security_tip_launch_count_v1','99');localStorage.setItem('payaviator_onboarding_choice_v1','guest')")
        pg.reload(); pg.wait_for_timeout(2500)
        pg.evaluate("document.querySelectorAll('dialog[open]').forEach(d=>d.close());document.querySelector('.mb119-nav[data-view=home]').click()")
        # force the boss numbers: available 108.55, cushion 190.90
        pg.evaluate("window.PayAviatorAvailableNow=()=>({total:108.55,estimate:false,items:[{subtype:'checking'}]});const o=window.mb20419MoneyState;window.mb20419MoneyState=()=>Object.assign({},o(),{cushion:190.90});window.pp2059RenderGauge()")
        pg.wait_for_timeout(800)
        r=pg.evaluate("[PayAviatorGauge.reasonText(),document.getElementById('ppGaugeReason')?.innerText,document.getElementById('ppGaugeReason')?.hidden,document.getElementById('ppGaugeReason')?.nextElementSibling?.id,document.querySelector('.pp967-readout .amt')?.innerText]")
        ok=ok and r[0]['kind']=='cushion' and r[1]==r[0]['text'] and r[2]==False and r[3]=='pp2059GaugeMetrics' and not errs; print(vw,r,errs)
        pg.evaluate("document.getElementById('ppGaugeReason').scrollIntoView({block:'center'})"); pg.wait_for_timeout(300)
        pg.screenshot(path=f'/workspace/pa-audit-1012/shots/boss-411-{vw}x{vh}-gauge-reason.png')
        pg.evaluate("window.PayAviatorAvailableNow=()=>({total:500,estimate:false,items:[{subtype:'checking'}]});window.pp2059RenderGauge()"); pg.wait_for_timeout(600)
        q=pg.evaluate("[PayAviatorGauge.reasonText(),document.getElementById('ppGaugeReason').hidden]"); ok=ok and q[0]['kind']=='ok' and q[1]==True; print(' ok-case',q)
    b.close()
print('ALL PASS' if ok else 'SOME FAILED')
