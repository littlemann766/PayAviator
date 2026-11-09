# PayAviator privacy and terms audit (engineering note)

**Date of review:** 2026-11-07
**Audience:** the person updating https://github.com/littlemann766/PayAviator-Website
**What this is:** a comparison of the current app source, the backend source, and the pages already published on payaviator.app. It is not a legal opinion, not a certification of compliance, and not a statement that a store listing or a server was changed.

Nothing in this review was deployed. The website repository and the backend repository were not modified. No live user was deleted. No purchase flow was turned on. Whether an AI assistant will exist is undecided. This update does not add one.

## Sources reviewed

| Source | Identity | What was done |
|---|---|---|
| This app repo, `main` before the disclosure edits | `444ccc81b291cbdcad15a788e71f1f07c0556dbb` | Version **4.2.6**, Android `versionCode` floor **420600** (`VERSION.txt`, `ANDROID_VERSION_CODE.txt`) |
| Tag `v4.2.7-test` (GitHub pre-release, not contained in `main`) | `f148cb87c93f15458b52e0e95fb7fe5225618294` | Read-only diff. It is two commits that are not on `main`: R8 minify and edge-to-edge insets, plus a version bump to 4.2.7. Privacy, billing and consent strings match 4.2.6 except `BUNDLED_VERSION`. This review branch does not merge that tag. |
| Backend repo `main` | `a91ab31bddb36939117dbdab6e04ae4a8fbdc56b` (2026-10-17) | Read-only clone. No Railway env vars were read. |
| Website repo `main` | `1ca81c401376f18916e5ff4451010def3ac9455e` (2026-10-17, "Privacy: disclose cached last-known bank balance (policy 2026-10g)") | Read-only clone. Not edited. |
| Live pages | `https://payaviator.app/privacy.html`, `https://payaviator.app/terms.html`, `https://payaviator.app/delete-account.html` | Fetched during the review. They matched the website repo above. |

**Play binary:** this repo does not contain a Play Console artifact, and no Play Console API was available. Do not treat `main` (4.2.6) or the 4.2.7 test tag as the binary people have installed until someone checks Play Console. The findings below are about this source and the backend source, not about an unverified store APK.

## Policy version handoff

Checked read-only on 2026-11-07. This app was not pointed at the draft.

- Live policy: https://payaviator.app/privacy.html still prints **2026-10g**. `POLICY_VERSION` in `index.html` is `2026-10g`.
- Website commit `0e6cf2cc376c9fc42ec23099d74bb779d26fbec4` (2026-11-07) adds an unpublished copy. `privacy.html` on that commit says draft **2026-11a-draft**, prepared from app `cf672f8`, and says it is **not effective** and not deployed. The same notice says a later approved publication would print **2026-11a** and that both Android `index.html` copies must set `POLICY_VERSION` to `2026-11a` in that same release.
- **Launch prerequisite, not done here:** owner approval, then one release where the public website prints `2026-11a` (the draft notice removed) and this app records `POLICY_VERSION='2026-11a'`. Do not ship the app against `2026-11a-draft`, and do not describe `2026-11a-draft` as accepted or live.
- Support timing belongs on the website. That same website commit's `support.html` draft says the aim is a first response within 72 elapsed hours, not a promise the issue will be resolved, and not an automatic reply. It does not delay self-service bank removal or account deletion. This app does not wait 72 hours and does not make support a gate. The website writer owns that support wording. It is not copied into the app here.

## Per-bank removal (verified, then changed in the app)

Backend `a91ab31`, read-only. No production deletion was run.

`DELETE /api/plaid/items/:itemId` (`src/app.js` around lines 676-686) loads items for the signed-in user only. If that Item exists, it calls Plaid `/item/remove`, then `store.deleteItem` (`src/store.js` around lines 354-365), which deletes that Item's access token, its transactions, its exchanged-token hashes, a pending update link for it, its cached balance, and its push-dedupe row. Other Items stay. The handler does not delete the Firebase user, `sync_items` (cloud bills and the other synced collections), or `billing_entitlements`. A Plaid failure returns an error and keeps the Item (`test/plaidflow.test.js`: "DELETE keeps the item if /item/remove fails" and "DELETE one item also deletes its public-token hash rows... leaving other banks intact"). One Item can include checking, savings, and a card; the route has no per-account unlink.

Wrong owner: `DELETE /api/plaid/items/:otherUserId/:itemId` with a mismatched user id returns **403** and leaves the other user's Item (`test/auth.test.js`, "valid token is scoped to its own sub"). `DELETE /api/plaid/items/:itemId` with no user id in the path, for an Item that is not in the caller's rows, returns **200** `{disconnected:true}` and does not delete another user's row, because `getItems` is scoped to the caller (`src/app.js` line 677-678). There is no separate per-account delete route.

App `cf672f8` before this fix: Connected Accounts put **Disconnect** on each account row. That removed the local row immediately and called `DELETE /api/plaid/items/:itemId` only when no local account with that Item id remained. A later sync could put the account back while the Item still existed. The credit-card control (`pp9164`) removed one local card and did not call the server.

This branch now waits for `{disconnected:true}` before it drops local accounts, transactions, or choices for that Item. The confirm names the institution connection and the accounts on it. Other institutions, the PayAviator sign-in, and typed bills are left in place. A non-success response, including 401, 403, and a 200 body that is not `{disconnected:true}`, does not purge. 401 asks the person to sign in again and does not sign them out. The removed Item id is remembered only for the signed-in user id, so a stale sync or reconnect payload for that user does not paint the connection back; a different user id on the same phone is not filtered by that list. There is still no per-account backend unlink. Hiding one card or one checking row is not treated as an unlink. Full account deletion still does not ask for a reason, does not require a survey, and does not require cancelling Plus first. A fresh sign-in is still required when Firebase says the last sign-in is older than about 4 minutes; that path no longer signs the person out before they authenticate again.

Still unsupported, and not claimed as done: removing one account inside an Item while keeping the others; closing an account at the bank; cancelling Plus as part of unlink or account deletion; a 72-hour support wait; treating website draft `2026-11a-draft` as the live policy.

## Ordinary account deletion

One confirmation. No reason, survey, or support wait. Manage subscription stays next to Delete and is not required. The confirmation says deletion does not cancel Google Play or Stripe billing and does not close accounts at the bank. Institution removal stays a separate action.

A stale Firebase sign-in (about 4 minutes) returns before `DELETE /api/plaid/user`. The phone asks for the same account again and does not sign out, so local banks stay. A different uid after that prompt does not continue the delete. If the server returns non-success, including a 502 with `failed_item_ids`, the Firebase user is not deleted and the phone does not erase its copy. Banks the server already removed stay removed. If Firebase deletion fails after the server call succeeded, the sign-in remains and the message says server bank data may already be gone.

Backend recovery commit `afc04829` (PR 15) is not integrated. A Play token that another uid already owns still stops at 409 `purchase_in_use`. This app does not grant that entitlement.

## Subscription manage and cancel

Checked against backend `a91ab31` before adding the screen. `BILLING_LIVE` stays false. No purchase was started and no production portal was configured.

- `POST /api/billing/stripe/portal` (`src/stripeBilling.js`) is signed in with the Firebase token. It loads the Stripe customer id with `store.getStripeCustomer(req.userId)`. The phone does not send a customer id or an email. A missing customer is 404 `NO_STRIPE_CUSTOMER`. Missing Stripe env is 503 `STRIPE_NOT_CONFIGURED`. The response url is opened only when it is `https://billing.stripe.com/...`. `test/stripe.test.js` covers the 404 and the session created for that same user.
- Google Play management uses the public subscriptions page. The package is this app's `applicationId`, `com.payaviator.app`. The sku is added only when `GET /api/billing/status` returns a `productId` for `source:"play"`. Backend tests use package fixture `app.payaviator` and product fixture `payaviator_premium`. Those strings are not the app id, and production `ANDROID_PACKAGE_NAME` / `GOOGLE_PLAY_PRODUCT_IDS` were not read. If the Play Console package is not `com.payaviator.app`, this deep link will not match until that env is confirmed.
- `cancelAtPeriodEnd` and `periodEnd` are Stripe-only in `billingSummary`. Play `cancelAtPeriodEnd` is always false there. A Play state `SUBSCRIPTION_STATE_CANCELED` can still leave `plan:"premium"` until `expiresAt` (`test/billing.test.js`, "canceled-but-unexpired keeps premium"). The screen repeats those fields when they are present. It does not show Cancelled because the person opened Play or Stripe.
- Account deletion still has one confirmation, no reason, and no requirement to cancel first. The confirmation says deletion does not cancel Google Play or Stripe billing and a new sign-in does not take over the old subscription.

Restore, added after that gap was authorized, queries Play Billing for subscriptions this install already owns and posts each purchased token to the existing `POST /api/billing/google-play/verify` route. It does not call `launchBillingFlow`. A 409 `purchase_in_use` is shown as a conflict and does not start checkout or grant Plus. There is still no server route that moves a purchase onto a new uid, so a deleted account is not recovered here. Empty Play results do not restore Stripe. Server `ANDROID_PACKAGE_NAME` is still an unread production setting; backend tests use `app.payaviator`, while this app's id is `com.payaviator.app`.

Deleting and creating another account does not move Plus. Entitlements stay on the old Firebase uid: `deleteUserData` does not delete `billing_entitlements` or `stripe_customers`. The same Play purchase token verified by a second uid returns 409 `purchase_in_use` (`test/billing.test.js`). The app's Restore only sends purchases from `AndroidBridge.billingGetPurchases`, and `MainActivity` does not implement that method, so Restore currently finds nothing. There is no email or customer-id transfer. A new free account can be charged again if the person subscribes while the old store subscription is still renewing. That restore gap is documented here and is not implemented.

Stripe portal setup that is still outside this repo: the four Stripe env vars, and the Stripe Dashboard customer portal with cancel enabled. Until those exist the app shows `stripe_not_configured` or `no_stripe_customer` and does not pretend the subscription was cancelled.

## What the current app actually does

Checked in this repo unless a backend path is named.

### Accounts and sign-in
- Optional. Bills, income, spending, reminders and backups work without an account (`docs/FIREBASE_SIGNIN.md`).
- Android sign-in is Firebase Authentication: Google (Credential Manager) and email/password. Phone buttons are hidden (`PHONE_SIGNIN=false` in `index.html`). There is no working fingerprint sign-in; the screen says it is a later update (`index.html` around the `biometricSignIn` hook).
- The WebView does not receive Firebase ID tokens. Native code attaches `Authorization: Bearer` on backend calls (`app/src/main/java/com/payaviator/app/auth/AuthedRequest.java`, `MainActivity.java` `apiRequest`).
- A new bank link is refused by the backend unless the Firebase token has `email_verified === true` (`PayAviator-Backend/src/app.js` around the link gate). Google sign-in is treated as verified in `FirebaseSignIn.isVerified`.
- Password reset and email verification are Firebase flows. PayAviator servers are not given the password (`docs/FIREBASE_SIGNIN.md`).

### Bank linking (Plaid)
- Optional. Read-only Link via the native Plaid SDK (`com.plaid.link:sdk-core:6.2.2`) or a hosted HTTPS link. The public token is exchanged on the backend, not stored as a bank password in the app.
- Before Link opens, a consent sheet is shown. Continue writes a local record only (`payaviator_plaid_consent_v1`): time, `policyVersion`, `connect` or `reconnect`, and app version. It is not posted to the backend (`index.html`, consent script).
- Backend stores the Plaid access token encrypted with AES-256-GCM (`PayAviator-Backend/src/crypto.js`). Legacy plaintext rows are tolerated until a boot migration. Tokens are not returned to the phone in the routes reviewed.
- Transactions are stored as the Plaid payload JSON (`plaid_transactions.payload`). This review did not find a field filter that strips values if Plaid included them. Do not claim a field-by-field redaction of that payload without checking Plaid's current schema.
- Last-known balances are cached per item (`plaid_item_balances`). The website policy's "cached last-known balance" sentence matches that table.
- Disconnect is `DELETE /api/plaid/items/:itemId`. If Plaid `/item/remove` fails, the row is kept (`src/app.js` `removeItem`).
- One free bank (all of its accounts) is the coded limit. Extra banks are paused without an active Plus or comp entitlement (`src/billing.js` pause rule). Comp and founder plans are display states from `/api/billing/status`, not a purchase.

### Cloud sync
- When a verified user is signed in, `index.html` script `pa414-cloud-sync` pushes and pulls bills, income, spending, goals, budgets, categories and cushion through `/api/sync/push` and `/api/sync/changes`.
- Signed-out use does not call those routes.
- `DELETE /api/plaid/user` also deletes that user's `sync_items` (`store.deleteUserData` calls `syncDeleteAll`). Individual deletes while the account still exists can leave tombstones; the backend default purge is 90 days (`src/cloudSync.js` `tombstoneDays: 90`). Account deletion removes the rows immediately rather than waiting for that purge.
- Guest copy in the app used to say data stays on the phone without saying a signed-in copy can sync. That sentence was updated in this branch.

### Subscriptions
- Documented prices in this source: **$3.99 per month** and **$29.99 per year** (`index.html` `setPrice('$3.99','mo')` and `setPrice('$29.99','yr')`). The yearly "Save N%" label is computed in the page (`$29.99` vs `$3.99 × 12` floors to 37). The same numbers are on the website pricing page.
- **Purchases are off in this source.** `const BILLING_LIVE=false` disables the subscribe button (label "Upgrade") and the agreement checkbox, and the note says "Plus is coming soon."
- `app/build.gradle` does not depend on Play Billing. There is no Stripe SDK in the app.
- The app can still call `GET /api/billing/status` and `POST /api/billing/google-play/verify` if a native purchase token is ever handed in. Nothing in this source starts a Play purchase.
- The backend contains Google Play verification and Stripe Checkout code (`src/billing.js`, `src/stripeBilling.js`). Whether production Railway has those credentials set was **not** checked. A missing Stripe config returns 503 `stripe_not_configured` (`docs/BILLING-CONTRACT.md`). Do not describe Android Play billing as available today. Do not describe Stripe as confirmed live in production from this review alone. The website pricing page does call `/api/billing/stripe/checkout` when someone presses Subscribe (`assets/billing.js`).

### Notifications, diagnostics, permissions
- Bill and custom reminders are **local alarms** (`NotificationScheduler.java`, `AlarmManager.setAndAllowWhileIdle`). That is not an exact alarm. Android can defer it. There is no `SCHEDULE_EXACT_ALARM` permission. The plan is capped (`MAX_ALARMS = 450`). Default `notificationsEnabled` is false until the person turns bill notifications on.
- Firebase Cloud Messaging is used for **bank reconnect** pushes only (`PushService.java` returns unless `type` is `bank_reconnect`). The token is registered with `POST /api/devices/fcm` while signed in and removed with `DELETE` before sign-out. Account deletion deletes `fcm_tokens` for that user.
- The published privacy page says FCM is used "to send bill reminders and alerts such as when a bank connection needs to be reconnected." The second half matches the app. Bill reminders do not go through FCM. The same page later says bill reminders on the phone do not need a push token, which is the accurate part. The first sentence should be corrected.
- No `firebase-analytics` or `firebase-crashlytics` dependency. README "no ads or analytics SDK" matches this Gradle file. Play Integrity is a dependency, but `PlayIntegrity.CLOUD_PROJECT_NUMBER` is `0`, so the app sends no integrity token (`PlayIntegrity.java`). The server ignores the header unless `PLAY_INTEGRITY_ENFORCE=true` (`src/integrity.js` comments and `docs/PRIVACY-DATA-NOTES.md`). The privacy page lists Play Integrity as a provider that checks devices. That is not true of this app build until the project number is set and enforcement is on.
- Permissions in `app/src/main/AndroidManifest.xml`: `INTERNET`, `POST_NOTIFICATIONS`, `VIBRATE`, `RECEIVE_BOOT_COMPLETED`, `USE_BIOMETRIC`, `USE_FINGERPRINT`. `android:allowBackup="false"`. Cleartext HTTP is off.
- A local link counter stores event counts and Plaid error codes on the phone only (comment in `index.html` near `PayAviatorLinkStats`). It is not a network analytics SDK.
- Support email opens `mailto:support@payaviator.app` with subject "PayAviator support" and a body of app version plus Android version only (`MainActivity.SUPPORT_EMAIL`, `supportBody`).

### Deletion, sign-out, and what remains

In-app path (`MainActivity.deleteAccountFlow`, then `FirebaseSignIn.deleteFirebaseUser`):

1. If nobody is signed in, deletion does not run.
2. If the Firebase last sign-in is 4 minutes old or older (`RECENT_LOGIN_MS` in `FirebaseSignIn.java`), the app returns `REQUIRES_RECENT_LOGIN` and does **not** call Plaid yet. The page then signs the person out and asks them to sign in again. Sign-out clears the phone's bank cache (`clearBankCache` in `index.html`) and asks the server to drop that phone's FCM token. The server account and Plaid items stay until a later delete succeeds.
3. Otherwise the app calls `DELETE /api/plaid/user` and deletes the Firebase user only when that call returns success.
4. Backend (`src/app.js` around line 691, `store.deleteUserData` around line 373): each item is removed at Plaid. Items that fail are kept, the handler returns **502** with `failed_item_ids`, and the app does not delete the Firebase user. On the rows that are removed, the server deletes transactions, pending links, exchanged-token hashes, sync items, FCM tokens, and cached balances that no longer have an item. Free-tier fingerprints are marked released, not deleted immediately.

**Not deleted by `deleteUserData`:**

- `live_balance_calls` (user id, item id, plan, time, outcome, error code). The table comment says it is kept after account deletion. No purge job was found. The privacy page says this, and that part matches the code. There is no coded retention length.
- `billing_entitlements` (product id, platform, state, expiry, SHA-256 of a Play purchase token).
- `stripe_customers` (Firebase user id and Stripe customer id). `docs/PRIVACY-DATA-NOTES.md` in the backend says this is "not yet auto-deleted" and marks it TODO.
- `stripe_events` (event id and type). Backend docs say those ids are kept 30 days and purged hourly. That is code-documented, not confirmed against production logs.
- Railway stdout logs. The backend doc says Railway keeps them for whatever the plan retains. This review did not read the Railway plan.
- Firebase Authentication still holds the account until step 3 succeeds. Firebase may keep its own auth logs under Google's terms. Those terms were not reviewed.
- Phone-local bills, income, spending, reminders, consent records and backups. Uninstall does not delete a backup the person saved through the file picker.
- Free-tier HMAC fingerprints after release. Code default is `FREE_TIER_COOLDOWN_DAYS` or **30** (`src/config.js` line 160). The deployed value was not read. Do not print "30 days" as a production fact until that env var is confirmed. The privacy page currently states 30 days. That matches the code default only.

The old in-app confirm text said deletion removes the bank data and the sign-in, and that phone-entered bills stay. It did not say that a failed Plaid removal aborts the whole delete, or that some server rows remain. This branch changes that confirm text. It does not change the delete code.

The public `delete-account.html` says a request is completed "within 30 days" and "We keep only what the law requires." No email-request queue or 30-day deletion job was found in the app or backend. In-app deletion is immediate when it succeeds, and the tables above are still kept. "Only what the law requires" is a legal conclusion this review cannot make. Please do not leave that sentence as written.

### Local data the phone keeps
WebView `localStorage` (bills, income, spending, settings, sync outbox, consent, saved email if the person opts in) plus Android private prefs for the bill snapshot, notification plan, FCM token and app lock. Bank cache keys are cleared on sign-out, account deletion, session expiry, or a different user signing in. Budget data is not cleared by those events.

## Published pages vs this evidence

Do not treat the list as a rewrite. It is the set of sentences that should change or be confirmed before they are left up. Suggested direction only. A lawyer should decide statutory wording, refunds, age rules and any liability text. This review did **not** add an arbitration clause, a class-action waiver, or a broader liability limit.

| Published claim (website `1ca81c4` / live page) | Evidence | What to do |
|---|---|---|
| Privacy version **2026-10g**, effective 2026-10-17 | App consent records `2026-10g`. Website commit `0e6cf2cc376c9fc42ec23099d74bb779d26fbec4` is an unpublished draft marked **2026-11a-draft** and **not effective**. The live page remains 2026-10g. | Do not point the app at `2026-11a-draft`. The later approved release, if the owner publishes it, prints **2026-11a** on the website and sets Android `POLICY_VERSION` to `2026-11a` in that same release. Until that publication is approved, consent stays `2026-10g`. |
| FCM sends bill reminders and reconnect alerts | FCM path is reconnect only. Bill reminders are local alarms. | Say FCM is for bank-reconnect alerts. Say bill reminders are on-device and can be delayed or skipped. |
| Play Integrity checks the device for the free bank | App project number is 0, so no token is sent. Enforcement is a server flag that was not read. | Say the check exists in code and is off in this app build until configured. Or leave it out until it is on. |
| You can subscribe in the Android app through Google Play | This source cannot start a purchase (`BILLING_LIVE=false`, no BillingClient). | Say the app shows $3.99/mo and $29.99/yr and that buying in the app is not available in the current source. Re-check the Play binary before saying otherwise. |
| Stripe sells Plus on payaviator.app | Website `pricing.html` and `assets/billing.js` call Stripe checkout. Backend implements it and returns 503 if unset. Production env not read. | Keep the Stripe description only if checkout is actually enabled in production. If it 503s, say it is not available yet. |
| Terms: Plus renews until you cancel in Google Play or your account | True only after a real subscription exists. The app's live purchase path does not. | Same as the row above. Do not describe an in-app cancel path that this source does not have. |
| Account deletion removes all server data, then Firebase; fingerprints wait 30 days; balance-refresh log may remain | Mostly matches, with the gaps in the deletion section. 30 days is the code default, not a confirmed env value. Entitlements and Stripe customer ids are not deleted. | Describe the gaps. Do not say "all of your data" without the exceptions. Confirm `FREE_TIER_COOLDOWN_DAYS` before keeping "30 days." |
| `delete-account.html`: deleted within 30 days; keep only what the law requires | No such job found. In-app success is immediate and incomplete in the ways above. | Replace with the actual in-app behavior and the actual leftovers. "What the law requires" needs a lawyer if you keep any version of it. |
| Servers do not store email, name or photo | PayAviator tables reviewed key off Firebase uid. Email is in the Firebase token and is passed to Stripe as `customer_email` when a Stripe customer is created (`src/stripeBilling.js`). The Stripe customer id is stored. | The short line "your email is used for sign-in and receipts" is fair. The flat "servers do not store your email" should mention Firebase (Google) stores the account email and Stripe receives it for a web subscription. |
| Age 18 and "we will delete" a child's information | No age check in the app. No automated under-18 deletion flow was found. | Product and lawyer decision. Do not claim an age gate or an automatic deletion the code does not do. |
| Cloudflare, Zoho Mail, GitHub Pages, Railway log retention, Plaid/Google/Stripe contract terms | Named on the privacy page. This review did not read vendor contracts, DNS, or the mailbox host. Railway and Postgres match the backend's own docs. GitHub Pages matches how the site is hosted. | Keep a provider only if the owner confirms it is actually in the path. Do not invent retention periods from a vendor marketing page. |
| "We don't sell or share your personal information" | No ad SDK and no sale code was found. Service providers above do process data. | "We do not sell" can stay if the owner confirms there is no sale. Do not add a "share" definition that picks a statute. A lawyer should decide CCPA/GDPR "share" wording. This review found no evidence to add or remove a statutory category. |

These pages already avoid a guarantee of perfect security ("No electronic storage or transmission method can be guaranteed to be completely secure") and say the app is not financial advice. Keep those. Do not replace them with a promise of complete security, complete accuracy, or legal immunity.

Terms already say calculations are estimates and that operation is not guaranteed. Keep that. The Android app had stronger marketing than the terms ("Never miss a due date", "exact closed-app alerts"). Those app strings were softened in this branch. The website home and feature pages were not edited here; search them for the same promise before the next site publish.

Operator: the owner is forming a company alone. These records do not show a completed registration, a jurisdiction, a legal address, a co-owner, or an effective date. Do not add a registered-entity name or another person to the app or the public pages. The public contact remains `support@payaviator.app`.

AI is undecided. This source has no assistant. This update does not design one, and it does not set a launch date or policy text for one.

## In-app edits on this branch (behavior unchanged)

Purchases stay off. Delete still calls the same API. Consent is still stored only on the phone. No screen flow was removed.

| Place | Before | After |
|---|---|---|
| `POLICY_VERSION` | `2026-10e` while the live page says `2026-10g` | `2026-10g` |
| Settings, sign-in, consent, account creation | Privacy link only, or "Terms & Privacy Policy" pointing only at `privacy.html` | Real links to `https://payaviator.app/privacy.html` and `https://payaviator.app/terms.html` |
| Upgrade checkbox | One link labeled as both documents. Checkbox stays disabled while `BILLING_LIVE` is false. | Separate Terms and Privacy links. Still disabled while billing is off. Account creation still says the person agrees to the Privacy Policy, and adds a read link for the Terms. It does not add a new acceptance checkbox. |
| Delete confirm and success toast | Said bank data and the sign-in are deleted, and phone-entered data stays | Also says a failed bank removal cancels the delete, a fresh sign-in may be required, backups are not deleted, and some technical records can remain |
| Bank consent "You're in control" | "That removes the data stored for it." | Removal when it succeeds, plus the same limits |
| Welcome | "Never miss a due date" | "Due dates in one place", reminders optional and can be delayed |
| Guest "Nothing is lost" | Data stays on the phone | Also says a signed-in account can sync a copy |
| Safe to Spend help | Formula only | Also says it is an estimate, not a bank balance and not financial advice |
| Reminder settings copy | "exact closed-app alerts" | Local reminders can be delayed or skipped and do not pay a bill |
| `docs/PRIVACY_POLICY_DRAFT.md` | September 6, 2026 text: no Internet permission, no accounts, no cloud sync | Withdrawn. Points here. |
| `docs/PLAY_STORE_LISTING_DRAFT.md` | "does not require an Internet connection" | Draft corrected so it is not copied into Play Console by mistake. Not submitted. |

`app/src/main/assets/index.html` is a committed mirror of the root `index.html`. Gradle packages the root file, not that folder (`app/build.gradle`). Both copies were updated so they stay identical.

## Unknowns that need the owner, a vendor, or a lawyer

1. Which APK or AAB is the one in Play testing or production, and whether its `BILLING_LIVE` value matches this source.
2. Production values of `FREE_TIER_COOLDOWN_DAYS`, `PLAY_INTEGRITY_ENFORCE`, Stripe keys, and Google Play billing keys. Not read, because they are secrets.
3. Whether legacy pre-Firebase Plaid items were removed with `scripts/cleanup-legacy-items.js`. The script is manual. The privacy page says those connections will be removed after the sign-in update. This review cannot see production rows.
4. Railway log retention, Cloudflare, Zoho, and the privacy terms of Plaid, Google, and Stripe. Not reviewed.
5. Company formation. The owner is forming a company alone. Do not state that a company is already registered, and do not name a co-owner. Jurisdiction, address, and governing law are not in these records.
6. Whether an age rule should be enforced, and what an email deletion request must promise. The current "30 days" and "only what the law requires" lines are not backed by code.
7. How long `live_balance_calls`, `billing_entitlements` and `stripe_customers` should be kept after account deletion. The code keeps them. A lawyer has to decide if that is acceptable. Do not "fix" the backend only so a policy sentence becomes true; change the product decision first.
8. Whether the stored Plaid transaction payload can contain fields the policy says are absent. No stripper was found in `store.applySync`.
9. AI. Undecided. Not in this build. Do not treat it as a planned feature.

## Release candidate 4.2.9 (not merged)

Version name `4.2.9`. Android versionCode floor `420900`. `BUNDLED_VERSION` is `4.2.9` in both `index.html` copies. Package remains `com.payaviator.app`. The prior candidate `f02bc00` was 4.2.8, floor `420800`, Actions run 135 (`42719635497`).

`POLICY_VERSION` in this candidate is `2026-11a`. Website branch `cursor/privacy-terms-review-7701` at `5a32230` still marks the pages as unpublished draft `2026-11a-draft` and not effective. Live `https://payaviator.app/privacy.html` was still `2026-10g`. Do not merge this app until that live page prints `2026-11a` and the draft notice is gone. Do not record `2026-11a-draft`.

The 4.2.8 AAB certificate SHA-1 is `9E:93:4C:92:BE:E0:38:90:9B:29:B5:4F:6E:E0:F1:E7:0B:70:B6:9C` and SHA-256 begins `96:76:9C:CD`. That is the upload key. It is not proof of the Play app-signing certificate. Install over a Play copy by uploading the AAB. Do not sideload the CI APK onto that install.

In-app purchase launch is off (`BILLING_LIVE=false`, no `launchBillingFlow`). The Billing library is present only to query an existing purchase and send it to verify. A 409 grants nothing. Backend purchase-ownership transfer is not in this app.

The owner is forming a solo Ohio company. It is not recorded as registered. No co-owner is named. AI is undecided and is not in this build.

## Review build 4.2.8 (superseded by 4.2.9, not merged)

Version name `4.2.8`. Android versionCode floor `420800` in `ANDROID_VERSION_CODE.txt`. Display string `BUNDLED_VERSION` in `index.html` and `app/src/main/assets/index.html`. Package remains `com.payaviator.app`.

`4.2.7` is already used by tag `v4.2.7-test` (`f148cb87`, versionCode `420700`) and a successful Actions run on `release-4.2.7` (run 134). That tag is not on `main`. This review build does not include its R8 or edge-to-edge changes.

Play baseline named by the owner is 4.2.6. The 4.2.6 Actions run on `main` is run 132. The workflow uses `max(400000 + run number, ANDROID_VERSION_CODE.txt)`. Run 132 is below the 4.2.6 floor `420600`, so that build's versionCode is the floor `420600`. Floor `420800` is above both `420600` and `420700`.

The 4.2.8 candidate recorded `POLICY_VERSION='2026-10g'`. The 4.2.9 candidate moves that to `2026-11a` and still must not merge while the live page prints `2026-10g`. The 72-hour first-response aim belongs on the website support page. This app does not wait 72 hours and does not make support a gate for disconnect or deletion.

## Counsel checklist

AI: undecided. Not in this build. Not a committed feature.

Company: the owner is forming it alone. Not recorded here as registered. No co-owner is named.

## Features in this review build vs not included

In the 4.2.9 candidate: consent version `2026-11a` (not yet the live page), one-confirmation account deletion, optional Manage subscription, one-bank disconnect after server confirmation, same-phone Play restore that stops on HTTP 409, and visible Google sign-in and verification-email results. In-app buying stays off.

Not included: backend purchase-ownership transfer after account deletion, client-side Plus, a new purchase, and a public production release.

## Check that was run

`python3 tools/test-privacy-disclosures.py` checks the in-app strings, the withdrawn draft, the prices, `BILLING_LIVE=false`, no purchase launch, and whether the live privacy page prints final `2026-11a`. A file pass does not mean the product complies with a privacy statute. A live-page failure means do not merge yet.
