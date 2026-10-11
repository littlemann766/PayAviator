# Update PayAviator without uninstalling

## Release: 3.9.6

What changed in each release: [CHANGELOG.md](../CHANGELOG.md).

**One-time exception for 3.9.6:** 3.9.6 is signed with the new PayAviator release key, so Android can't install it over an earlier build. Do this once:

1. In the old app, export a backup (Settings → Save & Backup) and save the file somewhere safe.
2. Uninstall the old app.
3. Install 3.9.6 and restore the backup.
4. Reconnect any linked banks.

From 3.9.6 on, every update installs over the existing app as described below.

**Important: Never uninstall PayAviator just to install a new APK.** It can erase local finance data. Back up your data in PayAviator first.

### GitHub build steps (no command line required)

1. Get the new source onto `main` of your existing PayAviator repository by pushing or merging. If you upload by hand, upload the unzipped **contents** (including the `.github` folder) to the repository **root**: never a ZIP file, and the workflows must end up in `.github/workflows/`. Keep the original repository and GitHub secrets.
2. In your repository, check **Settings → Secrets and variables → Actions**. The pre-existing secrets **PAYAVIATOR_KEYSTORE_HEX** and **PAYAVIATOR_KEYSTORE_PASSWORD** must contain the current PayAviator release key (introduced in 3.9.6) and its password. Do **not** generate or swap in a different keystore.
3. Pushing to `main` starts **Actions → Build PayAviator Release** automatically (you can also choose **Run workflow**). It builds the signed **Release** APK and AAB. Don't use a Debug APK or an unrelated old workflow.
4. Open the successful run → Artifacts → **PayAviator-3.9.6**. Download and extract it to get `PayAviator-3.9.6.apk`.
   (Alternative: **PayAviator Signed Update APK → Run workflow** gives artifact **PayAviator-3.9.6-SIGNED-UPDATE**. Pick one workflow and keep using it: each has its own run counter, so switching can produce a lower versionCode.)
5. On your phone, open the APK. Android should offer to update PayAviator **without uninstalling**. Your existing bills, hours, calendar, banking connections, and app data should remain in place.

### How the update is made compatible

- Same installed Android package ID: `com.payaviator.app`.
- Same signing certificate: the workflow reuses the current PayAviator release key from the repository secrets (any alias; it is renamed to `payaviator` in a temporary copy).
- New `versionName` 3.9.6 and Android `versionCode` 400000 plus the workflow run number, which advances with every new run of that workflow. `ANDROID_VERSION_CODE.txt` defines the permanent update-code floor.
- Root `index.html` is the authoritative installed HTML, and it is freshly packaged into the APK.

### If Android says "App not installed", "Conflicting package", or demands uninstall

Stop there; **do not uninstall**. Common cause is that the current APK was signed with a different certificate (for instance, an earlier GitHub-hosted Debug build). **No code change can override that Android security check.** To update without erasing your data, the new APK must be signed with the same key as the installed app. If the installed app is older than 3.9.6, it was signed with the previous key: follow the one-time 3.9.6 steps above. Otherwise, tell us the exact installation error and which Actions workflow produced the installed APK.

A matching signature and higher version code allow an in-place APK installation; they do **not** make it a self-updating app. Full automatic updates require app-store or managed-distribution infrastructure.
