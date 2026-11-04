# Signing in, per kind of client

| Client | Method | On every request |
|---|---|---|
| Technician app (mobile pattern; same for Flutter or React Native) | password or one-time code, then a token | `Authorization: token <api_key>:<api_secret>` |
| Customer portal (browser) | email and password, session cookie | the cookie (automatic) + `X-Frappe-CSRF-Token` on POST |
| Partner system | OAuth2 (Frappe is the provider) | `Authorization: Bearer <access_token>` |
| Scripts and integrations you control | a user's API key | `Authorization: token <key>:<secret>` |

## Activation, once per installation

Before anything else, the installation is activated with the access code from the course email
(`activation.activate {"code": "UA1...."}`, the `/activate` page, or
`bench --site <site> fieldpro-activate <code>`). Until then every sign-in is refused: Desk and
portal logins (an `on_login` hook), the technician's `request_otp` and `verify_otp`
(`not_activated`, 403), and `/login` redirects to `/activate`. `activation.status` tells a client
which to show. API tokens issued earlier keep working: the gate is at sign-in only.

The code is signed by UPEO Academy (Ed25519) and checked here against the public key in
`services/activation.py`, with no network call.

## Technician: password or a code by email or SMS, then a token

1. `POST auth.request_otp {"mobile_no": "+254700100001"}`. **Fieldpro Settings > Send Sign-in
   Codes By** decides where the code goes:
   - **Email** (the default): to the email of the technician's user, through the outgoing Email
     Account. It works in every country with no SMS gateway to pay for.
   - **SMS**: through the gateway in SMS Settings.

   With no Email Account or SMS gateway configured (local development) nothing is sent: the code
   is saved as an **SMS Log** in Desk either way.
2. `POST auth.verify_otp {"mobile_no": "...", "code": "123456"}` returns `token`.
3. Send `Authorization: token <token>` on every call. No cookies, no CSRF.

Or with a password: `POST auth.sign_in_with_password {"login": "achieng@fieldpro.test", "password": "..."}`
returns the same token. `login` is the technician's email or mobile number. Frappe checks the
password and locks the account after the failed attempts System Settings allows, as Desk does. A
wrong email and a wrong password get the same `wrong_password` answer.

Codes expire in 5 minutes, allow 5 guesses, and 3 codes per number per 10 minutes. Signing in on a
new phone issues a new secret, which signs the old phone out. `auth.sign_out_device` does the same.

## Customer portal: session and CSRF

1. `POST /api/method/login {"usr": "...", "pwd": "..."}` sets the `sid` cookie.
2. `GET auth.session` returns `csrf_token`.
3. Every POST carries `X-Frappe-CSRF-Token`. A cookie is sent by the browser on its own, even to
   requests another site triggers; the CSRF token proves the request came from our pages.

Serve the portal and the API from one origin (the Next.js app proxies `/api`) and the cookie is
first-party, with no CORS. If the API must be on another origin, set `allow_cors` in site_config
and use `SameSite=None; Secure` cookies.

## Partner systems: OAuth2

The demo seed creates an **OAuth Client** "Partner Accounting" (Desk > OAuth Client). A partner:

1. sends the user to `/api/method/frappe.integrations.oauth2.authorize?client_id=<id>&response_type=code&scope=all&redirect_uri=http://localhost:4000/callback`,
2. exchanges the returned `code` at `POST /api/method/frappe.integrations.oauth2.get_token`
   (`grant_type=authorization_code`, `code`, `redirect_uri`, `client_id`),
3. calls the API with `Authorization: Bearer <access_token>`, as that user, with that user's permissions.

Refresh with `grant_type=refresh_token`. Revoke in Desk (OAuth Bearer Token).
