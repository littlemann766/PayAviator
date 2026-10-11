# PayAviator signing security

PayAviator 3.9.6 introduced the current release signing key (certificate CN=PayAviator). Every later release must be signed with this same key.

- Application ID: `com.payaviator.app`
- Key alias: `payaviator` (the CI workflows accept any alias and rename it in a temporary copy)
- GitHub secret: `PAYAVIATOR_KEYSTORE_HEX`
- GitHub secret: `PAYAVIATOR_KEYSTORE_PASSWORD`

The private keystore is NOT stored in this repository.

Keep the current release keystore (`.jks`) and its password in a secure offline backup.
Losing this key means future APKs cannot update installs signed by this key.
