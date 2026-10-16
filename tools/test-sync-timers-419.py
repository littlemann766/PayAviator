#!/usr/bin/env python3
"""Static check: the cloud-sync script has no timer shorter than 5 min and pulls on focus/visibility/online/pageshow. Usage: test-sync-timers-419.py [index.html]"""
import re, sys
t = open(sys.argv[1] if len(sys.argv) > 1 and not sys.argv[1].startswith('http') else 'index.html').read()
a = t.index('<script id="pa414-cloud-sync">'); s = t[a:t.index('</script>', a)]
iv = [int(x) for x in re.findall(r'setInterval\([^;]*?,\s*(\d+)\)\s*;', s)]
assert iv and min(iv) >= 300000, iv
for ev in ("'visibilitychange'", "'online'", "'pageshow'", "'focus'"): assert ev in s, ev
assert 'queueScan' in s
print('PASS sync timers', iv)
