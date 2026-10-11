# PayAviator versioning and in-place Android updates

Current release: **3.9.6**. A display version advances from `.0` to `.9`, then rolls to the next minor: `3.9.6` → ... → `3.9.9` → `3.10.0`.

**Do not derive Android's versionCode from the display version.** The app has undergone earlier major-version resets, so deriving it from semantic versions risks a downgrade.

- `VERSION.txt`: visible release version (`3.9.6`); `index.html` `BUNDLED_VERSION` must match (checked by `tools/verify-foundation.py`)
- `ANDROID_VERSION_CODE.txt`: stable Android install/upgrade code floor (`400000`)
- GitHub Actions (`.github/workflows/build-payaviator.yml` and `payaviator-signed-update.yml`): set `PAYAVIATOR_ANDROID_VERSION_CODE = 400000 + GITHUB_RUN_NUMBER` (never below the floor) so each new run has a higher Android version code. Run numbers are per workflow, so install APKs from one workflow consistently.
- `app/build.gradle`: uses that workflow code while retaining `versionName` from `VERSION.txt`.

Never change the Android app ID `com.payaviator.app`, and always reuse the signing key that signed the installed app. See [UPDATE_WITHOUT_UNINSTALL.md](UPDATE_WITHOUT_UNINSTALL.md).
