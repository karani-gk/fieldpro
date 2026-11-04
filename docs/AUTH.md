# Signing in, per kind of client

| Client | Method | On every request |
|---|---|---|
| Technician app (mobile pattern; same for Flutter or React Native) | phone code, then a token | `Authorization: token <api_key>:<api_secret>` |
| Customer portal (browser) | email and password, session cookie | the cookie (automatic) + `X-Frappe-CSRF-Token` on POST |
| Partner system | OAuth2 (Frappe is the provider) | `Authorization: Bearer <access_token>` |
| Scripts and integrations you control | a user's API key | `Authorization: token <key>:<secret>` |

## Technician: code by SMS, then a token

1. `POST auth.request_otp {"mobile_no": "+254700100001"}`. The code is sent by the gateway in SMS
   Settings; with none configured (local development) it is saved as an **SMS Log** in Desk.
2. `POST auth.verify_otp {"mobile_no": "...", "code": "123456"}` returns `token`.
3. Send `Authorization: token <token>` on every call. No cookies, no CSRF.

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
