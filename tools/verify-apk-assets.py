from pathlib import Path
import hashlib, re, sys, zipfile

if len(sys.argv) != 2:
    sys.exit('Usage: verify-apk-assets.py <apk>')
root = Path(__file__).resolve().parents[1]
apk = Path(sys.argv[1])
if not apk.exists():
    sys.exit(f'ERROR: APK not found: {apk}')

names = [
    'index.html','payaviator.css','manifest.webmanifest',
    'payaviator-v126-192.png','payaviator-v126-512.png','payaviator-v126-favicon.png','VERSION.txt'
]
with zipfile.ZipFile(apk) as z:
    for name in names:
        apk_name = f'assets/{name}'
        try:
            built = z.read(apk_name)
        except KeyError:
            sys.exit(f'ERROR: APK missing {apk_name}')
        source = (root / name).read_bytes()
        if hashlib.sha256(built).digest() != hashlib.sha256(source).digest():
            sys.exit(f'ERROR: APK contains stale/different {apk_name}')
    version = re.sub(r'(?i)^Version:\s*', '', z.read('assets/VERSION.txt').decode().strip())
print(f'APK web assets verified byte-for-byte for PayAviator {version}')
