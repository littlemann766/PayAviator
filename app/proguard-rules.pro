# PayAviator 4.2.7 R8 keep rules
-keepattributes *Annotation*,Signature,InnerClasses,EnclosingMethod,SourceFile,LineNumberTable
-renamesourcefileattribute SourceFile

# WebView JavaScript bridges (@JavascriptInterface methods must keep their names)
-keepclassmembers class * { @android.webkit.JavascriptInterface <methods>; }
-keep class com.payaviator.app.** { *; }

# Plaid Link SDK
-keep class com.plaid.** { *; }
-dontwarn com.plaid.**
-keep class com.squareup.moshi.** { *; }
-dontwarn com.squareup.moshi.**
-dontwarn okio.**
-dontwarn okhttp3.**
-dontwarn retrofit2.**
-dontwarn kotlinx.**

# Firebase / Google Play services / Credential Manager / Play Integrity
-keep class com.google.firebase.** { *; }
-keep class com.google.android.gms.** { *; }
-keep class com.google.android.libraries.identity.googleid.** { *; }
-keep class androidx.credentials.** { *; }
-keep class com.google.android.play.core.integrity.** { *; }
-dontwarn com.google.firebase.**
-dontwarn com.google.android.gms.**

# Capacitor (not used in this app, kept for safety if plugins are added later)
-keep class com.getcapacitor.** { *; }
-dontwarn com.getcapacitor.**
