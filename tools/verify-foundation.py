from pathlib import Path
import re, sys

root = Path(__file__).resolve().parents[1]
version_file = root / 'VERSION.txt'
if not version_file.exists():
    sys.exit('ERROR: VERSION.txt is missing')
raw = version_file.read_text(encoding='utf-8').strip()
version = re.sub(r'(?i)^Version:\s*', '', raw).strip()
if not re.fullmatch(r'\d+\.\d+\.\d+', version):
    sys.exit('ERROR: malformed VERSION.txt; expected Version: MAJOR.MINOR.PATCH')

gradle_file = root / 'app' / 'build.gradle'
if not gradle_file.exists():
    sys.exit('ERROR: app/build.gradle is missing')
gradle = gradle_file.read_text(encoding='utf-8')
required = [
    "rootProject.file('VERSION.txt')",
    'versionName payAviatorVersion',
    'versionCode payAviatorVersionCode',
    "rootProject.file('ANDROID_VERSION_CODE.txt')",
    "System.getenv('PAYAVIATOR_ANDROID_VERSION_CODE')",
    "applicationId 'com.payaviator.app'",
    "keyAlias 'payaviator'",
    "tasks.register('syncPayAviatorWebAssets', Sync)",
    'assets.srcDirs = [generatedWebAssetsDir.get().asFile]',
    "tasks.named('preBuild').configure",
]
for marker in required:
    if marker not in gradle:
        sys.exit(f'ERROR: missing foundation marker: {marker}')
if re.search(r"versionName\s+['\"]\d", gradle):
    sys.exit('ERROR: hardcoded versionName found')
if re.search(r"versionCode\s+\d+", gradle):
    sys.exit('ERROR: hardcoded versionCode found')

code_file = root / 'ANDROID_VERSION_CODE.txt'
if not code_file.exists() or not code_file.read_text().strip().isdigit():
    sys.exit('ERROR: missing or invalid Android versionCode floor')
if int(code_file.read_text().strip()) < 400000:
    sys.exit('ERROR: Android versionCode floor must be >= 400000')
if "const BUNDLED_VERSION='" + version + "';" not in (root / 'index.html').read_text():
    sys.exit('ERROR: bundled app display version is not synced with VERSION.txt')

web_assets = [
    'index.html','payaviator.css','manifest.webmanifest',
    'payaviator-v126-192.png','payaviator-v126-512.png','payaviator-v126-favicon.png','VERSION.txt'
]
for name in web_assets:
    if not (root / name).exists():
        sys.exit(f'ERROR: required authoritative web source missing: {name}')

html = (root / 'index.html').read_text(encoding='utf-8')
if re.search(r"const VERSION=['\"]\d+\.\d+\.\d+['\"]", html):
    sys.exit('ERROR: hardcoded active VERSION constant found in index.html')
if "AndroidBridge.getAppVersionName" not in html:
    sys.exit('ERROR: index.html is not using installed APK version bridge')

print(f'PayAviator foundation verified: {version}')
