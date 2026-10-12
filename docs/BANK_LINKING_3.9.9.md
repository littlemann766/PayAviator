# PayAviator bank linking — 3.9.9

## What was changed in the app

- **Hosted Link first**: if the authenticated bank service returns `hosted_link_url`, Android opens it outside the app, retaining the existing return/deep-link flow.
- **Native Plaid SDK fallback**: if the bank service returns `link_token` only, the official Android Plaid SDK 6.2.2 opens a secure native connection flow. The old in-process Plaid WebView is not used.
- **Firebase identity**: `/api/plaid/*` requests remain authenticated by Firebase ID tokens attached in the native HTTP bridge. The app no longer invents a user ID in the new token request; account paths favor the signed-in Firebase UID.
- **Reconnect**: native SDK update flows call `/api/plaid/update-complete`; new links exchange the `public_token` with the backend, never inside the app.
- **Responsiveness**: the native-call timeout allows Firebase token fetch plus HTTP connect/read timeouts to complete without a premature 22-second error.
- Existing budget, bill, calendar, savings, and backup storage keys remain untouched.

## Required backend capabilities (backend source not included in this ZIP)

- Verify Firebase ID tokens on all `/api/plaid/*` routes. Never trust a `userId` field from a client as authorization.
- `POST /api/plaid/create-link-token`: return `hosted_link_url` or `link_token`. The app sends `{ "mobile": true, "native_sdk": true, "android_package_name": "com.payaviator.app" }`. For a native SDK link token, the backend must use Plaid's `android_package_name` parameter and register `com.payaviator.app` in Plaid Dashboard (Build > API). For Hosted Link include `hosted_link.is_mobile_app=true`, `hosted_link.completion_redirect_uri="payaviator://plaid-complete"`, a `webhook`, and support retrieving the result using `/link/token/get` or the `SESSION_FINISHED` webhook. A backend which blindly ignores the native-sdk hint may issue a token intended only for the web.
- `POST /api/plaid/exchange-public-token`: securely exchange a valid `public_token`, save the resulting access token encrypted server-side and scoped to the verified user; **never** return a Plaid access token to this app.
- `GET /api/plaid/accounts/:userId`: return the current authenticated user's `accounts` array (with `balances`, account ID, type, institution name) and optional `items`/`errors`; enforce authorization regardless of path.
- `GET /api/plaid/transactions/:userId`: return the signed-in user's bank transactions and errors. Refresh from Plaid securely on the backend with appropriate rate limits.
- For update mode, `POST /api/plaid/update-link-token` returns the same Hosted Link or native link token shape; `POST /api/plaid/update-complete` marks completed updates and initiates sync.
- For Hosted Link, `GET /api/plaid/hosted-status` must report session `connected`, `pending`, mode and any error based on a durable per-user link-token session record; never assume a browser redirect proves a successful link.

## Release and testing

1. Keep the **existing** repository, application ID `com.payaviator.app`, and its existing **release signing keystore** secrets. Do not uninstall the app.
2. Upload the unzipped source **contents** (including `.github/`) to the existing PayAviator GitHub repo, and run the existing signed release build workflow. Use the same workflow family that made your currently installed signed APK to avoid lowering versionCode.
3. Verify `3.9.9` is installed via an update rather than reinstall, and that bills/calendar data remain in place.
4. Confirm sign-in with your existing PayAviator account. Test linking and syncing a **Plaid Sandbox** bank before testing a live bank.
5. Verify a real institution only when the production access, Link configuration and security controls on the backend are actually ready. Test a simple login plus an OAuth bank (e.g. Capital One) on an Android device.

> Backend service health, Plaid credentials, real bank institutions, and APK release signing are not testable solely from this source ZIP. The web HTML/JS and source-fidelity checks cannot prove an actual connection until the backend is deployed and the real device is used.
