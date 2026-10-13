package com.payaviator.app.auth;

import android.app.Activity;
import android.os.CancellationSignal;
import android.os.Handler;
import android.os.Looper;
import android.util.Log;

import androidx.credentials.ClearCredentialStateRequest;
import androidx.credentials.Credential;
import androidx.credentials.CredentialManager;
import androidx.credentials.CredentialManagerCallback;
import androidx.credentials.CustomCredential;
import androidx.credentials.GetCredentialRequest;
import androidx.credentials.GetCredentialResponse;
import androidx.credentials.exceptions.ClearCredentialException;
import androidx.credentials.exceptions.GetCredentialCancellationException;
import androidx.credentials.exceptions.GetCredentialException;
import androidx.credentials.exceptions.NoCredentialException;

import com.google.android.gms.tasks.Task;
import com.google.android.gms.tasks.Tasks;
import com.google.android.libraries.identity.googleid.GetSignInWithGoogleOption;
import com.google.android.libraries.identity.googleid.GoogleIdTokenCredential;
import com.google.firebase.FirebaseNetworkException;
import com.google.firebase.FirebaseTooManyRequestsException;
import com.google.firebase.auth.FirebaseAuth;
import com.google.firebase.auth.FirebaseAuthException;
import com.google.firebase.auth.FirebaseAuthInvalidCredentialsException;
import com.google.firebase.auth.FirebaseAuthInvalidUserException;
import com.google.firebase.auth.FirebaseAuthRecentLoginRequiredException;
import com.google.firebase.auth.FirebaseAuthUserCollisionException;
import com.google.firebase.auth.FirebaseAuthWeakPasswordException;
import com.google.firebase.auth.FirebaseUser;
import com.google.firebase.auth.GetTokenResult;
import com.google.firebase.auth.GoogleAuthProvider;
import com.google.firebase.auth.UserInfo;

import org.json.JSONObject;

import java.util.concurrent.ExecutionException;
import java.util.concurrent.Executor;
import java.util.concurrent.TimeUnit;

/**
 * Native Firebase Auth for PayAviator: Google (Credential Manager) and Email/Password.
 * The WebView never sees an ID token; MainActivity attaches it natively to /api/plaid/* calls.
 */
public final class FirebaseSignIn implements AuthedRequest.TokenSource {

    private static final String TAG = "PayAviatorAuth";
    /** Firebase requires a sign-in within the last ~5 minutes before deleting a user. */
    private static final long RECENT_LOGIN_MS = 4 * 60 * 1000L;

    public interface Callback {
        void done(boolean ok, String code, String message);
    }

    private final Activity activity;
    private final String googleServerClientId;
    /** Main-thread executor that also works on API 26/27 (Activity.getMainExecutor is API 28+). */
    private final Executor mainExecutor = new Handler(Looper.getMainLooper())::post;
    private FirebaseAuth auth;

    public FirebaseSignIn(Activity activity, String googleServerClientId) {
        this.activity = activity;
        this.googleServerClientId = googleServerClientId == null ? "" : googleServerClientId.trim();
        try {
            this.auth = FirebaseAuth.getInstance();
        } catch (Exception e) {
            // Missing/invalid google-services.json: banking stays unavailable, local tracking still works.
            Log.w(TAG, "Firebase Auth unavailable", e);
            this.auth = null;
        }
    }

    public boolean isAvailable() { return auth != null; }

    public FirebaseUser currentUser() { return auth == null ? null : auth.getCurrentUser(); }

    public void addStateListener(FirebaseAuth.AuthStateListener listener) {
        if (auth != null) auth.addAuthStateListener(listener);
    }

    public void removeStateListener(FirebaseAuth.AuthStateListener listener) {
        if (auth != null) auth.removeAuthStateListener(listener);
    }

    /** A Google-provider account counts as a verified email. */
    public static boolean isVerified(boolean firebaseVerified, String provider) {
        return firebaseVerified || "google".equals(provider);
    }

    /** Sign-in state for the WebView. Never includes tokens. */
    public JSONObject stateJson() {
        JSONObject o = new JSONObject();
        try {
            FirebaseUser u = currentUser();
            o.put("available", isAvailable());
            o.put("googleAvailable", isAvailable() && !googleServerClientId.isEmpty());
            o.put("signedIn", u != null);
            if (u != null) {
                o.put("uid", u.getUid());
                o.put("email", u.getEmail() == null ? "" : u.getEmail());
                o.put("name", u.getDisplayName() == null ? "" : u.getDisplayName());
                String provider = "password";
                for (UserInfo info : u.getProviderData()) {
                    if (GoogleAuthProvider.PROVIDER_ID.equals(info.getProviderId())) provider = "google";
                }
                // 4.1.1: Google already verified the address, so a Google account counts as verified email.
                o.put("emailVerified", isVerified(u.isEmailVerified(), provider));
                o.put("provider", provider);
            }
        } catch (Exception ignored) { }
        return o;
    }

    // ---- Token contract (AuthedRequest.TokenSource) -----------------------------------------

    /** Blocking; call only from a background thread. Returns null when nobody is signed in. */
    @Override
    public String getToken(boolean forceRefresh) throws Exception {
        FirebaseUser u = currentUser();
        if (u == null) return null;
        try {
            GetTokenResult r = Tasks.await(u.getIdToken(forceRefresh), 20, TimeUnit.SECONDS);
            return r == null ? null : r.getToken();
        } catch (ExecutionException e) {
            Throwable c = e.getCause();
            if (c instanceof FirebaseAuthInvalidUserException) {
                throw new AuthedRequest.SessionExpiredException("Firebase session is no longer valid", c);
            }
            throw (c instanceof Exception) ? (Exception) c : e;
        }
    }

    // ---- Email / Password --------------------------------------------------------------------

    public void signInWithEmail(String email, String password, Callback cb) {
        if (!checkReady(cb)) return;
        String e = email == null ? "" : email.trim();
        if (e.isEmpty() || password == null || password.isEmpty()) {
            cb.done(false, "MISSING_FIELDS", "Enter your email and password.");
            return;
        }
        complete(auth.signInWithEmailAndPassword(e, password), cb);
    }

    public void createAccount(String email, String password, Callback cb) {
        if (!checkReady(cb)) return;
        String e = email == null ? "" : email.trim();
        if (e.isEmpty() || password == null || password.isEmpty()) {
            cb.done(false, "MISSING_FIELDS", "Enter your email and a password.");
            return;
        }
        // 4.1.0: linking a bank needs a verified email, so send the link right after sign-up.
        auth.createUserWithEmailAndPassword(e, password).addOnCompleteListener(activity, t -> {
            if (t.isSuccessful()) {
                FirebaseUser u = currentUser();
                if (u != null) sendVerificationWithWebKey(u, null);
                cb.done(true, "", "");
            } else cb.done(false, codeFor(t.getException()), messageFor(t.getException()));
        });
    }

    /** Sends (or re-sends) the Firebase email verification link to the signed-in user. */
    public void sendEmailVerification(Callback cb) {
        if (!checkReady(cb)) return;
        FirebaseUser u = currentUser();
        if (u == null) { cb.done(false, "SIGN_IN_REQUIRED", "Sign in first."); return; }
        boolean google = false;
        for (UserInfo info : u.getProviderData()) if (GoogleAuthProvider.PROVIDER_ID.equals(info.getProviderId())) google = true;
        if (isVerified(u.isEmailVerified(), google ? "google" : "password")) { cb.done(true, "", ""); return; }
        sendVerificationWithWebKey(u, cb);
    }

    /**
     * 4.1.2: send the verification email with the web API key so the link's apiKey is not empty
     * (see VerifyEmailRequest). Falls back to the SDK's sendEmailVerification() if the REST call fails.
     */
    private void sendVerificationWithWebKey(final FirebaseUser u, final Callback cb) {
        u.getIdToken(false).addOnCompleteListener(t -> {
            final String token = t.isSuccessful() && t.getResult() != null ? t.getResult().getToken() : null;
            new Thread(() -> {
                int status = 0;
                try { if (token != null) status = VerifyEmailRequest.send(token); } catch (Exception e) { status = 0; }
                final int st = status;
                activity.runOnUiThread(() -> {
                    if (st == 200) { if (cb != null) cb.done(true, "", ""); return; }
                    Log.w("PayAviatorAuth", "sendOobCode status " + st + "; falling back to SDK");
                    Task<Void> sdk = u.sendEmailVerification();
                    if (cb != null) complete(sdk, cb);
                });
            }, "PayAviatorVerifyEmail").start();
        });
    }

    /**
     * After the user opens the verification link: reload the profile, then force-refresh the ID token
     * so the backend sees email_verified=true on the next call.
     */
    public void reloadAndRefreshToken(Callback cb) {
        if (!checkReady(cb)) return;
        FirebaseUser u = currentUser();
        if (u == null) { cb.done(false, "SIGN_IN_REQUIRED", "Sign in first."); return; }
        u.reload()
                .continueWithTask(t -> {
                    if (!t.isSuccessful() && t.getException() != null) throw t.getException();
                    FirebaseUser fresh = currentUser();
                    if (fresh == null) throw new IllegalStateException("signed out");
                    return fresh.getIdToken(true);
                })
                .addOnCompleteListener(activity, t -> {
                    if (t.isSuccessful()) cb.done(true, "", "");
                    else cb.done(false, codeFor(t.getException()), messageFor(t.getException()));
                });
    }

    public void sendPasswordReset(String email, Callback cb) {
        if (!checkReady(cb)) return;
        String e = email == null ? "" : email.trim();
        if (e.isEmpty()) {
            cb.done(false, "MISSING_FIELDS", "Enter your email first.");
            return;
        }
        complete(auth.sendPasswordResetEmail(e), cb);
    }

    // ---- Google via Credential Manager --------------------------------------------------------

    public void signInWithGoogle(Callback cb) {
        if (!checkReady(cb)) return;
        if (googleServerClientId.isEmpty()) {
            cb.done(false, "GOOGLE_NOT_CONFIGURED", "Google sign-in isn't set up yet. Use email and password.");
            return;
        }
        GetSignInWithGoogleOption option = new GetSignInWithGoogleOption.Builder(googleServerClientId).build();
        GetCredentialRequest request = new GetCredentialRequest.Builder().addCredentialOption(option).build();
        CredentialManager cm = CredentialManager.create(activity);
        cm.getCredentialAsync(activity, request, new CancellationSignal(), mainExecutor,
                new CredentialManagerCallback<GetCredentialResponse, GetCredentialException>() {
                    @Override
                    public void onResult(GetCredentialResponse response) {
                        Credential c = response.getCredential();
                        if (c instanceof CustomCredential
                                && GoogleIdTokenCredential.TYPE_GOOGLE_ID_TOKEN_CREDENTIAL.equals(c.getType())) {
                            try {
                                String idToken = GoogleIdTokenCredential.createFrom(c.getData()).getIdToken();
                                complete(auth.signInWithCredential(GoogleAuthProvider.getCredential(idToken, null)), cb);
                            } catch (Exception e) {
                                Log.w(TAG, "Bad Google credential", e);
                                cb.done(false, "GOOGLE_FAILED", "Google sign-in failed. Please try again.");
                            }
                        } else {
                            cb.done(false, "GOOGLE_FAILED", "Google sign-in returned an unexpected credential.");
                        }
                    }

                    @Override
                    public void onError(GetCredentialException e) {
                        Log.w(TAG, "Google sign-in error: " + e.getType() + " " + e.getMessage());
                        if (e instanceof GetCredentialCancellationException) {
                            cb.done(false, "CANCELLED", "");
                        } else if (e instanceof NoCredentialException) {
                            cb.done(false, "NO_GOOGLE_ACCOUNT", "No Google account is available on this phone. Add one in Android Settings or use email and password.");
                        } else {
                            String msg = String.valueOf(e.getMessage());
                            if (msg.contains("28444") || msg.contains("10:") || msg.toLowerCase().contains("developer")) {
                                // DEVELOPER_ERROR: this build's signing SHA-1 is not registered in Firebase.
                                cb.done(false, "GOOGLE_NOT_CONFIGURED", "Google sign-in isn't enabled for this build yet. Use email and password.");
                            } else {
                                cb.done(false, "GOOGLE_FAILED", "Google sign-in failed. Please try again.");
                            }
                        }
                    }
                });
    }

    // ---- Sign out / delete ---------------------------------------------------------------------

    public void signOut() {
        if (auth != null) auth.signOut();
        try {
            CredentialManager.create(activity).clearCredentialStateAsync(
                    new ClearCredentialStateRequest(), new CancellationSignal(), mainExecutor,
                    new CredentialManagerCallback<Void, ClearCredentialException>() {
                        @Override public void onResult(Void unused) { }
                        @Override public void onError(ClearCredentialException e) { }
                    });
        } catch (Exception ignored) { }
    }

    /** True when Firebase will accept user.delete() without a fresh sign-in. */
    public boolean hasRecentLogin() {
        FirebaseUser u = currentUser();
        if (u == null || u.getMetadata() == null) return false;
        return System.currentTimeMillis() - u.getMetadata().getLastSignInTimestamp() < RECENT_LOGIN_MS;
    }

    /** Deletes the Firebase user. The caller must already have called DELETE /api/plaid/user. */
    public void deleteFirebaseUser(Callback cb) {
        FirebaseUser u = currentUser();
        if (u == null) { cb.done(false, "SIGN_IN_REQUIRED", "Sign in first."); return; }
        u.delete().addOnCompleteListener(activity, t -> {
            if (t.isSuccessful()) {
                signOut();
                cb.done(true, "", "");
            } else {
                Exception e = t.getException();
                if (e instanceof FirebaseAuthRecentLoginRequiredException) {
                    cb.done(false, "REQUIRES_RECENT_LOGIN", "For your security, sign in again, then delete your account.");
                } else {
                    cb.done(false, codeFor(e), messageFor(e));
                }
            }
        });
    }

    // ---- helpers ------------------------------------------------------------------------------

    private boolean checkReady(Callback cb) {
        if (auth != null) return true;
        cb.done(false, "AUTH_UNAVAILABLE", "Sign-in isn't available in this build.");
        return false;
    }

    private <T> void complete(Task<T> task, Callback cb) {
        task.addOnCompleteListener(activity, t -> {
            if (t.isSuccessful()) cb.done(true, "", "");
            else cb.done(false, codeFor(t.getException()), messageFor(t.getException()));
        });
    }

    static String codeFor(Exception e) {
        if (e instanceof FirebaseAuthException) return ((FirebaseAuthException) e).getErrorCode();
        if (e instanceof FirebaseNetworkException) return "NETWORK";
        if (e instanceof FirebaseTooManyRequestsException) return "TOO_MANY_REQUESTS";
        return "AUTH_FAILED";
    }

    static String messageFor(Exception e) {
        if (e instanceof FirebaseAuthWeakPasswordException) return "Choose a stronger password (at least 6 characters).";
        if (e instanceof FirebaseAuthUserCollisionException) return "An account already exists for that email. Sign in instead.";
        if (e instanceof FirebaseAuthInvalidUserException) return "No account matches that email, or it was disabled.";
        if (e instanceof FirebaseAuthInvalidCredentialsException) {
            String code = ((FirebaseAuthException) e).getErrorCode();
            if ("ERROR_INVALID_EMAIL".equals(code)) return "That email address doesn't look right.";
            return "Email or password is incorrect.";
        }
        if (e instanceof FirebaseNetworkException) return "No internet connection. Check your connection and try again.";
        if (e instanceof FirebaseTooManyRequestsException) return "Too many attempts. Wait a minute and try again.";
        return "Sign-in failed. Please try again.";
    }
}
