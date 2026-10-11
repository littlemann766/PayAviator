# Firebase sign-in for bank features

Sign-in only gates bank (Plaid) features. Bills, income, spending, backups and reminders keep working
on the phone without an account.

## How it works
- **Native Firebase Auth** (`app/src/main/java/com/payaviator/app/auth/FirebaseSignIn.java`): Google via
  Credential Manager (`GetSignInWithGoogleOption` with `R.string.default_web_client_id`, then
  `GoogleAuthProvider.getCredential`) and Email/Password (sign in, create account, password reset).
  Google blocks OAuth inside WebViews, so the WebView never runs the Firebase JS SDK.
- **Token contract** (`auth/AuthedRequest.java`, unit-tested in `app/src/test`): every `/api/plaid/*` call made by
  `AndroidBridge.apiRequest` carries `Authorization: Bearer <Firebase ID token>` from `getIdToken(false)`.
  On HTTP 401 the token is force-refreshed (`getIdToken(true)`) and the call is retried once; a second 401
  (or a revoked/disabled user) signs the user out and the page shows the sign-in screen.
  With nobody signed in, `/api/plaid/*` is never called. `/api/health` stays unauthenticated.
  ID tokens never reach JavaScript.
- **Bridge** (`AndroidBridge`): `authGetState()`, `authSignInWithGoogle(id)`, `authSignInWithEmail(id, email, pw)`,
  `authCreateAccount(id, email, pw)`, `authSendPasswordReset(id, email)`, `authSignOut(id)`, `authDeleteAccount(id)`.
  Results come back through `window.PayAviatorAuthResult(json)` and state changes through
  `window.PayAviatorAuthStateChanged(json)`. The page wraps this as `window.PayAviatorAuth`.
- **Routes**: the app uses the path-less routes (`GET /api/plaid/accounts`, `/hosted-status`, `/transactions`,
  `DELETE /api/plaid/items/:itemId`) and no longer sends a `userId` anywhere; the backend takes the user
  from the token (it returns 403 `USER_MISMATCH` otherwise).
- **Item health / update mode**: items with `needs_update` show **Reconnect** in Connected Accounts →
  `POST /api/plaid/update-link-token {item_id}` → Hosted Link → poll `GET /api/plaid/hosted-status` until
  `success` / `exited` / `failed`.
- **Account deletion**: Connected Accounts → Delete account calls `DELETE /api/plaid/user` first and deletes the
  Firebase user only if that succeeds. If the last sign-in is older than ~4 minutes, the app asks for a fresh
  sign-in before touching any bank.
- **Errors**: backend bodies are `{error, code, request_id}`; `error` is shown, `request_id` is logged.
- **Bank data on this phone** belongs to the signed-in user: it is cleared on sign-out, session expiry, account
  deletion, or when a different user signs in. Banks linked before sign-in existed (old device ids) must be
  connected again once; the app tells the user after their first sign-in.

## Configuration
- `app/google-services.json` is committed on purpose (Firebase client config, not a secret).
  It must contain an Android OAuth client (`client_type: 1`) whose `certificate_hash` matches the signing key,
  or Google sign-in fails with DEVELOPER_ERROR (Email/Password still works). Registered today: the PayAviator
  release key from 3.9.6 (SHA-1 `9E:93:4C:92:BE:E0:38:90:9B:29:B5:4F:6E:E0:F1:E7:0B:70:B6:9C`) and one local debug key.
  If Play App Signing is used, the Play app-signing key's SHA-1 must be added too, then the file refreshed.
- Unit tests for the token contract: `gradle testDebugUnitTest`.
- The browser/PWA build shows "Bank connections are available in the PayAviator Android app": its CSP
  (`connect-src 'self'`, `script-src 'self'`) blocks both the backend and the Firebase JS SDK.
