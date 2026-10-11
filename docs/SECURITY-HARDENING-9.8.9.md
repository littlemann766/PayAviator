# PayAviator app security hardening — 9.8.9

- Banking API calls use the native Android HTTPS bridge rather than exposing backend authentication in web storage.
- Each app install receives a cryptographically random device ID and secret stored in Android private app storage.
- The device secret is attached only by native code and is not exposed to JavaScript.
- Cleartext HTTP remains disabled; mixed content and WebView debugging remain disabled.
- Android backups remain disabled for app-private data.
- Banking endpoints are paired with the hardened 9.8.9 backend and reject access to another device profile.

No Plaid client secret, Plaid access token, database password, or Railway secret is packaged in the APK.
