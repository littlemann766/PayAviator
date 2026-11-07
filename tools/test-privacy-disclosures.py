#!/usr/bin/env python3
"""Static checks for PayAviator privacy/terms disclosures, plus a live link check.

The live check confirms https://payaviator.app/privacy.html and /terms.html
still match the version and prices this app records. Set PAYAVIATOR_SKIP_LIVE=1
to run only the file checks.
"""
import os
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INDEX = (ROOT / 'index.html').read_text(encoding='utf-8')
ASSETS = (ROOT / 'app/src/main/assets/index.html').read_text(encoding='utf-8')
DRAFT = (ROOT / 'docs/PRIVACY_POLICY_DRAFT.md').read_text(encoding='utf-8')
LISTING = (ROOT / 'docs/PLAY_STORE_LISTING_DRAFT.md').read_text(encoding='utf-8')
ok = True

def check(name, cond):
    global ok
    print(('PASS' if cond else 'FAIL') + ' ' + name)
    ok = ok and cond

check('root index.html matches packaged asset copy', INDEX == ASSETS)
check('policy version recorded as live 2026-10g', "const POLICY_VERSION='2026-10g';" in INDEX)
check('unpublished 2026-11a-draft is not the recorded consent version', "POLICY_VERSION='2026-11a" not in INDEX)
check('privacy URL present', 'https://payaviator.app/privacy.html' in INDEX)
check('terms URL present', 'https://payaviator.app/terms.html' in INDEX)
check('Plaid end-user policy linked from consent', 'https://plaid.com/legal/#end-user-privacy-policy' in INDEX)
check('support address unchanged', 'support@payaviator.app' in INDEX)
check('monthly price wired', "s.setPrice('$3.99','mo')" in INDEX)
check('yearly price wired', "s.setPrice('$29.99','yr')" in INDEX)
check('Play purchases still off', 'const BILLING_LIVE=false;' in INDEX)
check('no Play Billing SDK dependency', 'billingclient' not in (ROOT / 'app/build.gradle').read_text(encoding='utf-8').lower())
check('settings lists privacy and terms', 'data-pa397-privacy' in INDEX and 'data-pa397-terms' in INDEX)
check('account creation links both documents', 'By creating an account you agree to our' in INDEX and 'Terms of Service' in INDEX)
check('upgrade agreement uses two real links', 'I agree to the <a href="https://payaviator.app/terms.html"' in INDEX and 'Privacy Policy</a>' in INDEX)
check('delete copy does not promise every server record is erased', 'Some technical records can remain' in INDEX)
check('delete copy says a failed bank removal keeps the sign-in', 'If a bank cannot be removed, the sign-in is not deleted' in INDEX)
check('delete copy does not cancel Plus or ask for a reason', 'does not cancel a Plus subscription' in INDEX and 'You do not need to give a reason' in INDEX)
check('bank removal waits for server disconnected:true', 'body.disconnected!==true' in INDEX)
check('live accounts sheet removes a connection, not one account row', 'data-pp920-remove-item' in INDEX and 'data-pp920-remove="1"' not in INDEX)
check('credit-card control uses the connection remover', 'PayAviatorBankRemoval.ask(itemId)' in INDEX)
check('recent-login deletion does not sign out first', "await call('authSignOut')" not in INDEX.split('async deleteAccount()')[1].split('takeReconnectNotice')[0])
check('delete copy says typed data stays on the phone', 'stay on this phone' in INDEX)
check('safe to spend described as an estimate', 'It is an estimate from what is in the app' in INDEX)
check('reminders are not promised', 'not a guarantee that a bill will be paid on time' in INDEX)
check('guest copy mentions cloud copy when signed in', 'a copy can also sync to your account' in INDEX)
for banned in [
    'Never miss a due date',
    'exact closed-app alerts',
    'Ask PayAviator',
    'C&R Digital',
    'does not require Android Internet permission',
    'does not include advertising SDKs, analytics SDKs, user accounts',
]:
    check('app copy does not say: ' + banned, banned not in INDEX)
check('withdrawn draft no longer claims a local-only release', 'does not require Android Internet permission' not in DRAFT)
check('withdrawn draft points at the audit note', 'PRIVACY_TERMS_AUDIT_2026-11-07.md' in DRAFT)
check('store draft does not say the release needs no internet', 'does not require an Internet connection' not in LISTING)
check('store draft keeps the not-a-bank line', 'not a bank' in LISTING.lower())
check('no analytics or crashlytics dependency', all(
    name not in (ROOT / 'app/build.gradle').read_text(encoding='utf-8')
    for name in ('firebase-analytics', 'firebase-crashlytics')
))

def fetch(url):
    req = urllib.request.Request(url, headers={'User-Agent': 'PayAviatorDisclosureCheck/1.0'})
    with urllib.request.urlopen(req, timeout=20) as res:
        body = res.read().decode('utf-8', 'replace')
        return res.status, body

if os.environ.get('PAYAVIATOR_SKIP_LIVE') == '1':
    print('SKIP live link check (PAYAVIATOR_SKIP_LIVE=1)')
else:
    try:
        status, body = fetch('https://payaviator.app/privacy.html')
        check('live privacy.html returns 200', status == 200)
        check('live privacy.html is policy 2026-10g', '2026-10g' in body)
        check('live privacy.html names support@payaviator.app', 'support@payaviator.app' in body)
        status, body = fetch('https://payaviator.app/terms.html')
        check('live terms.html returns 200', status == 200)
        check('live terms.html lists $3.99', '$3.99' in body)
        check('live terms.html lists $29.99', '$29.99' in body)
        status, _ = fetch('https://plaid.com/legal/#end-user-privacy-policy')
        check('Plaid legal page returns 200', status == 200)
    except Exception as e:
        check('live link check failed: ' + type(e).__name__ + ': ' + str(e), False)

print('ALL PASS' if ok else 'SOME FAIL')
sys.exit(0 if ok else 1)
