## 4.1.3 — Email-verify loop fix, large-text fit, new Upgrade + sign-in screens
- Verify email: sends only on tap (60s resend cooldown, "use the newest email" hint); "I verified, continue" reloads and force-refreshes the sign-in token and retries Connect bank; silent refresh + retry on first 403 email_not_verified; re-check on resume.
- Large text / small screens: heading wrap, Cash/Credit gauges scale (never stack), metric tiles, nav label ellipsis, system-bar insets, textZoom cap 130%.
- Beth's Upgrade + sign-in redesign: original palette, $3.99/month and $29.99/year side by side, no trial wording. While BILLING_LIVE=false the note reads "Plus is coming soon." and the button says "Upgrade". Phone sign-in hidden (PHONE_SIGNIN=false).
- Version 4.1.3 everywhere; service-worker cache payaviator-4.1.3; Android versionCode floor 410300.

## 4.1.2 — Notifications rework (phase 1), compact Payoff Planner
- Version 4.1.2 everywhere; service-worker cache payaviator-4.1.2; Android versionCode floor 410200.
- Notifications (Beth's DESIGN.md, phase 1, local only, no server or paid service):
  - Reminders survive a phone restart: alarms are stored as one plan and re-armed by a new BootReceiver (BOOT_COMPLETED, MY_PACKAGE_REPLACED) and on every app start (RECEIVE_BOOT_COMPLETED permission).
  - Paid bills stop reminding: the web app builds the plan from real occurrences (skips paid and deleted ones, honors per-bill days/time) and rebuilds it after any pay, edit, delete or settings change; the receiver also re-checks that an alarm is still in the current plan before showing it.
  - Lock screen privacy: notifications are VISIBILITY_PRIVATE with a generic public version ("A bill is due tomorrow" / "Unlock to see details.") unless the new Settings row "Show amounts on lock screen" (off by default) is on.
  - Tapping a notification opens the related screen (bill sheet, Calendar, Connected Accounts) via window.PayAviatorOpenAlert.
  - Alerts bell with unread badge in the Home header (beside ?) and an Alerts center: Today / Earlier, unread dots, tap to open, swipe left to clear, Mark all read, Clear all, 30-day on-device history, empty state. Fired notifications, in-app reminder toasts and bank reconnect notices land there.
  - FCM bank reconnect pushes (Lucian's fcm-reconnect-push contract): firebase-messaging + PushService; token registered with POST /api/devices/fcm after sign-in, on new token and on app start, removed with DELETE before sign-out (fails quietly until the server is deployed); "bank_reconnect" high-priority channel; tap or foreground receipt starts Plaid update mode for data.item_id.
- Beth's compact Payoff Planner (pa412-payoff-compact-css): smaller gauge and tighter tiles; colors unchanged.
- Beth's setup (setup-411) and tips (tips-411) updates.
- Beth design check: Alerts keeps a solid navy bottom nav with the active tab and hides Home underneath; badge = unread count of the stored alert list; Home 💡 moved into the header (no overlap with the Credit gauge); "Clear all" on the EARLIER heading; setup step 1 "Let's get you set up", Simple preview without the Next up row.
- Email verification links had an empty apiKey ("The selected page mode is invalid"): verification is now sent through Identity Toolkit accounts:sendOobCode with the public web API key (VerifyEmailRequest), SDK sendEmailVerification() as fallback.
- tools/test-available-now.py runs in Detailed Home (Simple Home hides those tiles by design); new tools/test-notif-412.py.

## 4.1.1 — Continue with Google
- Version 4.1.1 everywhere; service-worker cache payaviator-4.1.1; Android versionCode floor 410100.
- Beth's welcome, sign-in and create-account screens get a "Continue with Google" button (Google's standard light button: white, G logo, dark text) wired to the existing native Firebase Google sign-in (authSignInWithGoogle, Credential Manager). Hidden when the build has no Google client id or Firebase is unavailable.
- "Continue with phone" button under Google on the same three screens (same style, phone icon); tapping shows an in-app "Phone sign-in is coming soon" message. No Firebase phone auth.
- Contact support: new Settings > About row and a "Need help?" link on the sign-in screen open the email app (native ACTION_SENDTO mailto via AndroidBridge.openSupportEmail; <queries> for mailto) to support@payaviator.app, subject "PayAviator support", body with app version and Android version only. No email app: in-app note with the address.
- First launch order fixed: Beth's welcome (sign-in choices) shows first; the "Setup 1 of 4" wizard runs only after sign-in, account creation or guest. Users who finished setup (or have data) never see it.
- Setup 1 of 4 copy (Beth): "Your budget is saved on this phone." / "Signing in keeps your banks synced, and backups are only made when you choose."; detail hint now says "in Settings under App Colors (Home Screen Appearance)".
- Android Back on Beth's auth screens: sign-in / create return to the welcome choices; Back on the first-launch welcome stays; other screens close fully (ppOnb-open removed, bottom nav restored). Fixes Home without the nav bar (the generic sheet-Back handler hid the overlay without closing it).
- Gauge: a $0 Safe to Spend now explains itself in #ppGaugeReason under the Safe to Spend box (window.PayAviatorGauge.reasonText() -> {text, kind: ok|cushion|bills|none}), e.g. "Your $190.90 cushion is set aside, so nothing extra to spend yet."
- Cushion defaults to $0 (was a preset: 20% of the latest paycheck, e.g. 20% x $954.50 = $190.90; Payday Health breakdown preset $100). On upgrade a preset cushion never set by the user is reset to $0 once; cushions set with Save Cushion (now flagged cushionUserSet) or other custom values are kept.
- Home: Edit Cushion button removed; the Cushion tile (Available now / Savings / Cushion row) has a chevron and opens the in-app cushion editor; + Add Spending fills the action row.
- Hidden upgrade-card prices now $3.99/month and $29.99/year (PRICE_CONFIRMED still false: "Subscriptions coming soon"). Yearly card flag shows "Save 37%" (computed: $29.99 vs $3.99 x 12), hidden with the prices.
- Settings > Sign in now opens Beth's sign-in screen instead of the old sign-in sheet.
- A Google account counts as a verified email (native stateJson emailVerified, no verification email sent); a 403 email_not_verified for a Google account refreshes the token instead of opening the Verify dialog.

## 4.1.0 — accounts, email verification, one free bank
- Version 4.1.0 everywhere; service-worker cache payaviator-4.1.0; Android versionCode floor 410000.
- Beth's auth screens (window.PayAviatorAuthScreens) are wired: welcome on first start (Android, signed out), Create account / Sign in / Forgot password through native Firebase, guest mode, guest Connect bank -> guest sign-up prompt. Biometric unlock says "coming in a later update" (no native BiometricPrompt yet). New email accounts get a verification email.
- 403 email_not_verified opens a Verify your email dialog (send link / I've verified). "I've verified" reloads the Firebase user and force-refreshes the ID token natively.
- 402 subscription_required opens Beth's upgrade screen with a distinct message for device_already_used_free, account_already_used_free and the plain one-bank limit (also hosted-status partial `skipped`). Price stays a placeholder ($X.XX/mo, $XX.XX/yr); startSubscription gets the selected {amount, period} and passes 'mo'|'yr' to the native billingPurchase stub.
- Plaid Link conversion counters (payaviator_link_stats_v1, this phone only): open hosted/native/web, success, exit with Plaid error code, hosted-link return status, open failures. No tokens, account numbers, institution or user ids. Web Link exit/success now re-enables the Connect button.
- Upgrade screen shows no price yet: plan cards, trial and price lines hidden, "Subscriptions coming soon" (PRICE_CONFIRMED=false in pa-410-accounts-js; confirmed prices $2.99/mo and $29.99/yr are preloaded for when it flips). Plaid consent POLICY_VERSION 2026-10b.
- Reconnect banner (Beth) fed from Plaid item health; one card per item, login beats new accounts; Reconnect opens update mode via update-link-token; replaces the old needs-attention card. Plan 'comp' = 'premium' (no limit, no upgrade).
- Billing: GET /api/billing/status and POST /api/billing/google-play/verify on start (restoring purchases from the native bridge when available) and after a purchase. Purchase is a stub until Play Billing is wired; 503 shows "Subscriptions open soon". Plan kept in memory only.
- Android sends X-Device-Id = Settings.Secure.ANDROID_ID (16 hex, lowercased) and, once PlayIntegrity.CLOUD_PROJECT_NUMBER is set, an X-Play-Integrity-Token (standard request, requestHash = sha256("<androidId>|<uid>"), reused up to 4 min, max 8192) on create-link-token, exchange-public-token and hosted-status; 403 integrity_failed, 503 integrity_not_configured and 400 device_id_invalid have their own messages; /api/billing/* now carries the Firebase token. New pure-Java BackendHeaders + unit tests. Regression test tools/test-accounts-410.py.

## 4.0.2 — Available now is your real spendable money
- Available now is now the total of every spendable account: connected bank accounts of type depository (checking and savings), using Plaid's available balance and falling back to current when available is empty, plus cash on hand entered in the Cash wallet (and any manual depository account). Credit cards, loans and investments are never counted.
- Cash on hand can be marked "already in one of these bank accounts" so it is not counted twice. Negative totals appear only when a real balance is negative.
- Home, the gauge, Monthly Snapshot and every older Available-now API read one shared function (window.PayAviatorAvailableNow); savings already inside Available now is not added again to Safe to Spend.
- With no accounts or cash set up, Available now falls back to the old paychecks − bills − spending estimate and is labeled as an estimate.
- Tap Available now (Home gauge or Monthly Snapshot) to see each account and the amount it counts. Regression test tools/test-available-now.py.
- Bills tab: a + Add Bill button at the top opens the same Add Bill form as the Calendar tab (Beth).
- Bill colors such as yellow #ffff00 are no longer repainted navy on the Calendar, Edit Day and Upcoming (white-background overrides now match exact white only) (Beth).
- Version 4.0.2 everywhere; service-worker cache payaviator-4.0.2; Android versionCode floor 400202.

## 4.0.1 — Budget sheets, in-app confirmations, date-move fix
- Budget sheets refreshed (Copy Previous Month confirm sheet, collapsible Categories, Monthly Snapshot, Payment History) and Back closes them in order (Beth).
- No native alert/confirm/prompt pop-ups; every question uses the app's own sheet. The duplicate-bill warning stays (Cancel / Add anyway) (Beth).
- Fixed: moving a repeating bill "only this date" and then the same date "this date and future months" left two copies (e.g. two Rents on Nov 3). The future edit now absorbs the earlier single-date move; regression test tools/test-move-absorb.py.
- Version 4.0.1 everywhere; service-worker cache payaviator-4.0.1; Android versionCode floor 400201.

## 4.0.0 — Official base release
- Budget tiles: tools open on the tap's click only (removed the pointerup early-open that let the follow-up click land on the new sheet's backdrop and close Savings Goals / Paycheck Planner on phones).
- Budget tiles: each tool runs once per tap (two extra click layers re-ran every tool, so Export Summary opened three save pickers).
- Paycheck Planner opens again when bills are due before the next paycheck (assignmentId / assignment storage were private to another script and threw).
- Payoff Planner: Snowball/Avalanche choice fits the screen instead of running off the right edge.
- Connected banking uses only the backend 4.0.0 routes (token-authenticated, Authorization: Bearer <Firebase ID token>); no user id in any URL, query or body. Removed the user-id path helper.
- Source of truth is the repository again: the uploaded PayAviator-main.zip is unpacked into the repo and removed.
- The lightbulb tip button hides while any sheet is open (it covered App Colors and the version in Backup & App) and returns when the sheet closes.
- Android Back closes only the topmost visible sheet or pop-up (any sheet, not just *Modal); with nothing open it falls through. Fixes Cash (Back hid an invisible tip instead) and Credit (Back found nothing). The lightbulb hides while any sheet is visible, using the same check.
- Budget: the whole card is the tap target, including its rounded corners, edges and padding; each tap opens the tool once.
- Paycheck Planner now plans: for the current and next 3 paychecks it lists the bills due before the following check (auto-assigned), shows what's left to spend, lets you move a bill to another paycheck or mark it paid, and warns when a check comes up short. Choices are saved on this phone (payaviator_paycheck_plan_v400); no server calls. Empty states for no paycheck and no bills.
- Version 4.0.0 everywhere (VERSION.txt, bundled version, service-worker cache payaviator-4.0.0); Android versionCode floor 400200.

## 3.10.5 — Restore dark Payoff Planner background
- Isolated the planner scroll container from the app’s default light background, keeping the full popup navy.
- Preserve the website-accurate 270-degree aviation gauge, navigation, account data and all Payoff Planner logic from 3.10.4.
- Match the Android bundled HTML and the web HTML, with a refreshed service-worker cache.

## 3.10.4 — Fix Payoff Planner blank screen for paid-off/zero-balance cards
- The no-outstanding-debt calculation now always returns the fields expected by the 270° credit gauge.
- Handles fully paid cards, mixed balances, missing credit limits, and an empty account list without rendering a blank popup.
- Adds a visible non-destructive error fallback if an unexpected rendering issue occurs.
- Preserves the PayAviator.app aviation gauge, saved balances, bank connections, and Android install-over-existing settings.

## 3.10.3 — Website-accurate Payoff Planner gauge
- Restored the payaviator.app 270° aviation gauge with silver rim, center needle, utilization arc, and full mobile view.
- Restored Snowball minimum-plus-extra and Avalanche full-balance payoff previews for each selected account.
- Show after-payment utilization and interest next to the selected account, without displaying a duplicate large combined-planner dashboard.
- Keep bank-linked balances, local debt records, and install-over-existing Android signing configuration unchanged.

## 3.10.2 — Payoff Planner consolidated repair

- Replace conflicting legacy Payoff Planner rendering layers with an isolated, responsive planner dialog.
- Fix cropped gauge, Snowball/Avalanche selection, zero-balance payoff status, and missing credit-limit representation.
- Enable manual add/edit/payment/remove, importing bank-linked credit accounts, account selection, and persistent preferences.
- Preserve the existing debt planner localStorage schema, bank data, signing configuration, and Android package identity.
- Payoff estimates use cent-rounded monthly interest and a combined fixed payment budget; payment tracking never executes bank transactions.

## 3.10.1 — Payoff Planner accuracy and controls

- Preserve the selected Snowball/Avalanche option when reopening the planner.
- Stop overwriting editable monthly Avalanche payments during screen repaint.
- Protect genuine entered minimum payments from being replaced by $25 after payoff activity.
- Show credit utilization only when a valid credit limit exists; unknown limit no longer looks like 100% used.
- Use cent-rounded per-month interest/payments for payoff projections, including the selected card in the Snowball cascade and any entered extra payment.
- Keep the existing 3.10.0 bank persistence, signing, application ID, and stored data structure intact.
- Existing connected-bank balances remain authoritative; projections do not initiate bank payments.

## 3.9.9 — Android bank linking fixes

- Use the official Plaid Android SDK v6.2.2 when the authenticated backend provides a `link_token` but not a `hosted_link_url`. Plaid Hosted Link remains the preferred first choice when available. No bank login credentials are exposed to PayAviator.
- Remove the independent health-check gate that could prevent linking even when the authenticated Plaid endpoint works.
- Send the Android package hint to the backend rather than a self-generated, legacy Plaid user ID. The backend must identify the caller using the Firebase ID token.
- Handle native Plaid success, exit and update-mode reconnections, then request fresh account and transaction data.
- Extend the native-bank-call timeout to match the Firebase-and-network time budget; prefer Firebase UID for account and transaction sync paths.
- Keep `com.payaviator.app` and the established signing configuration for install-over-existing updates.

**Backend requirement:** The backend must return either `hosted_link_url` or an Android-compatible `link_token`, verify Firebase auth, exchange new public tokens, and support the existing account/update endpoints. A frontend update cannot repair a stopped or misconfigured backend or unapproved Plaid production access.

# Changelog

Newest first. Every release keeps the Android application ID `com.payaviator.app` and the same signing key, so it installs over the previous version without losing data. The one exception is 3.9.6, which introduced the new PayAviator signing key (see [docs/UPDATE_WITHOUT_UNINSTALL.md](docs/UPDATE_WITHOUT_UNINSTALL.md)).

## 3.9.7

**Sign-in for bank features (Firebase)**
- Bank linking and sync now need a PayAviator account: Continue with Google (native Credential Manager) or email and password. Bills, income, spending, backups and reminders keep working without one.
- Every `/api/plaid/*` call sends `Authorization: Bearer <Firebase ID token>`; on a 401 the token is refreshed and the call retried once, then the app signs out and shows sign-in. The app no longer sends its own user or device ids to the backend and uses the path-less routes.
- Banks that need attention show **Reconnect** (Plaid update mode). Connected Accounts shows the signed-in account with Sign out and Delete account; deleting removes every bank at Plaid before deleting the sign-in.
- Banks linked before this release must be connected again once after signing in.
- Requires the backend release with Firebase token checks (PayAviator-Backend PR #1) to go live together with this app version. Details: [docs/FIREBASE_SIGNIN.md](docs/FIREBASE_SIGNIN.md).

## 3.9.6

- New release signing key (CN=PayAviator, alias `payaviator`). Phones with an earlier build must uninstall and reinstall once; Android rejects updates signed with a different key.

**Bank linking fixed**
- The app was still calling the backend host from before the rename. That host now returns 404, so bank linking and sync were broken in 3.9.5. `MainActivity.java` and the Plaid API constants in `index.html` now use `https://payaviator-backend-production.up.railway.app`.

**Rename finished**
- The leftover drawable is now `payaviator_app_icon.png`, and the docs are cleaned up. The repository no longer contains the old name. The signing certificate was also replaced (see above), so the old name is gone from the APK too.
- The migration from the pre-rename storage keys was removed (approved). Anyone who opened any recent version was already migrated. Someone updating straight from a very old build would start with an empty bill list.

**Signing secrets renamed: action needed**
- Both workflows read only `PAYAVIATOR_KEYSTORE_HEX` and `PAYAVIATOR_KEYSTORE_PASSWORD`, which hold the PayAviator release key introduced in 3.9.6. Signing fails if they're missing. From now on, always sign with this same key.

**Visual refresh and fixes**
- Cleaner layout in the app's original colors (light-blue page, navy cards, cyan accents, all driven by App Colors). Hairline borders, one sheet per pop-up, tinted status pills, larger touch targets.
- Home gauge labels no longer read "$0 / $0 / $1" when no custom scale is saved.
- Payoff Planner:
  - Uses the saved minimum instead of a hard-coded $25 and no longer overwrites it.
  - "Extra monthly payoff" is visible again and is applied as a full snowball: the extra plus freed-up minimums go to the smallest balance first.
  - The needle follows the selected card, and the utilization preview includes a month of interest.
  - Hand-checked: Visa $3,240.55 @ 24.99%, $180 minimum + $150 extra → 12 months, $501.34 interest.
- Credit gauge: the needle and both ends of the scale are visible. The needle is hidden when the limit is unknown. With no card connected it says "No credit card connected".
- One-time repair of minimum payments that older builds overwrote to $25 (flag `payaviator_min_payment_repair_v1`).
  - A minimum is only changed when it is exactly $25 and a month's interest on that balance is at least $25, since such a payment could never pay the card down. It is reset to 3% of the balance, at least $25.
  - It can't tell a $25 typed on purpose from one the old bug wrote. Any other $25 is left alone, and re-entering $25 after the repair sticks.
  - Credit sync no longer forces linked cards' minimums to $25.
- First-time setup:
  - Tips and the lightbulb stay hidden while setup is open. The first tip, and the PIN-lock tip, appear only after setup closes.
  - Only the setup sheet's content scrolls. The X stays pinned at the top, and Back / Continue / Finish stay visible above the keyboard.
- Budget tracked-spending rows read properly. The spending donut labels its remainder "Other categories". Cut-off Home text and stray literal `\n` characters are fixed.

**Other**
- `sw.js` cache renamed `payaviator-3.9.6`, so web/PWA installs drop the old cache on activate. The install step fetches with `cache: 'reload'` so it never stores a stale `index.html`.
- Repository tidy-up:
  - Dead `app.css` and `app.js` removed. `index.html` never loaded them.
  - Release notes merged into this file. Docs moved to `docs/`. README rewritten.
- Known: web/PWA builds still can't reach the bank backend because of the page's `connect-src 'self'` CSP. Android uses the native bridge.

## 3.9.5

- **Bill list and deleting bills.** `render()` crashed on every run because a later layer deleted `#incomeHourlyWage`. As a result, new bills didn't appear until restart and deleted bills came back. Four more scoping errors that interrupted rendering were also fixed (`addHealthStrip`, `state.hourlyWage`, `PP9173_VERSION`, `openSavings`), and the Home Savings card opens again.
- **CPU and battery.** Legacy layers rewrote the DOM even when nothing changed and re-triggered each other's page-wide observers every frame, keeping the main thread 100% busy. Writes now happen only when a value changes (`paSetText`, `paSetHTML`, `paAddClass`, `paRemoveClass`), and two layers that fought over the same elements were stopped. Idle CPU went from 100% to about 0–1%, and "Finish & Add My First Bill" opens instantly instead of after about 13 s.
- Bill status pills render and are readable on the dark theme.
- **Build.** Source moved to the repository root with workflows in `.github/workflows/`. Both workflows set versionCode to `400000 + run number` (never below `ANDROID_VERSION_CODE.txt`), install platform 36 and build-tools 35.0.0, and verify APK assets and signature. Any keystore alias is accepted.

## 3.9.4

- New Android update pipeline. versionCode is now independent of the display version and starts at 400000; each signed-update run gets `400000 + run number`, above 3.9.3's code of 30903.
- Added the `payaviator-signed-update.yml` workflow, which refuses to build without the existing signing secrets.
- Based on the real 3.9.3 source. App data, banking and bill logic are unchanged.

## 3.9.3

- Edits to one-time bills now save the bill and any moved or override records before redrawing. Before, a widget error could leave the old date saved while the calendar showed the new one.

## 3.9.2

- Every bill edit is also saved to Android app-private storage, and a newer snapshot is restored at startup.
- Snapshots are frozen and IndexedDB writes serialized, so older writes can't overwrite newer edits.
- Editing a recurring bill asks which dates to change: future dates (default), only this occurrence, or the entire schedule.
- Save results are verified, and a failed save is shown instead of being reported as saved.

## 3.9.1

- A moved recurring occurrence (for example Oct 5 → Oct 12) is saved as a stable one-time replacement. The series stays intact, the original date stays hidden, and moving it again no longer reverts after a restart.
- "This and future dates" splits the series at the selected date and keeps earlier occurrences.

## 3.2.4

- Bills list shows the **remaining** amount for partly paid bills.
- Merchant and bank logos load (CSP allows https images), with a letter mark as fallback.
- Clearer wording in the cushion dialog and gauge-scale help, and shorter work-day picker labels.

## 3.2.3

- Paychecks from hours × wage are rounded to the cent. Money formatting, bills-paid totals and debt simulation results are also cent-rounded.
- `paycheckOnDate` supports one-time, weekly, biweekly, monthly (end-of-month clamp) and semi-monthly schedules. Before, every non-weekly schedule was treated as biweekly.

## 3.2.2

- Credit limit: Edit Balance saves both `creditLimit` and `limit` and marks the value as manual, so bank sync no longer overwrites it.
- Monthly Snapshot "Bills paid" counts bills marked paid through older overrides or paid flags again.

## 3.2.1

- Monthly bills due on the 29th–31st fall on the last day of shorter months.
- Salary estimates support weekly, biweekly, semi-monthly and monthly pay, rounded to cents.
- Layout: Home actions clear the bottom nav, and buttons no longer clip labels.
- Bank-sync error toasts are hidden when no bank is linked.

## Earlier releases (8.0.0 – 20.4.12)

The display version was reset to the 3.x line after 20.4.12. That's why versionCode now comes from `ANDROID_VERSION_CODE.txt` plus the run number rather than from the version number.

- **20.4.12:**
  - The calculator uses a built-in arithmetic parser instead of eval, keeping the strict CSP.
  - Page titles follow the active tab, and refunds are classified correctly.
  - Budget and work-hours controls fit the phone width.
- **20.1.9:** PIN Lock is off by default and relocks only after 5 minutes in the background.
- **20.1.6: cleanup and security foundation.**
  - Hardening: cleartext traffic, WebView debugging, file-URL access, mixed content and third-party cookies disabled. External pages open in the browser, and a restrictive CSP is applied.
  - Android auto-backup disabled in favor of the app's own backup.
  - Targets API 36 and produces a signed APK plus Play Store AAB.
  - Guided first-run setup (hourly or salary income, ending with "Finish & Add My First Bill").
  - Accessibility: 44–48 px touch targets, focus outlines, reduced motion, safe-area padding.
  - Event-driven navigation replaces duplicate listeners.
- **9.8.9: security hardening.**
  - Banking calls go through the native HTTPS bridge.
  - Each install gets a random device ID and secret, kept in private storage and never exposed to JavaScript.
  - Backend access is limited to the device's own profile.
  - Details: [docs/SECURITY-HARDENING-9.8.9.md](docs/SECURITY-HARDENING-9.8.9.md).
- **9.2.10:** fixed the GitHub Actions build (`VERSION.txt` format, versionCode 90210).
- **8.0.0:** first official PayAviator release with its own signing identity and the airplane-and-money launcher icon.

## 3.10.0 — Persistent account sync protection
- Do not erase visible linked bank balances if linked Items exist but a balance refresh fails.
- Requires PayAviator banking backend 3.1.8 and Railway PostgreSQL for durable authenticated Item storage.
- Android version code floor 400110; original app ID and signing configuration unchanged.
