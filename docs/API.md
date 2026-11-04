# fieldpro API v1

Base: `/api/method/fieldpro.api.v1.<module>.<function>`. GET reads, POST changes. JSON in, JSON out.

## The contract

**Success:** `{"message": {"data": ...}}`. Lists add paging fields:
`{"message": {"data": [...], "next_cursor": "eyJ...", "has_more": true}}`.

**Failure:** an HTTP status that means something, and one body shape:

```json
{"error": {"code": "invalid", "message": "Say what is wrong with the work.", "fields": {"reason": "required"}}}
```

| Status | `code` | When |
|---|---|---|
| 401 | `unauthorized`, `code_expired`, `wrong_code` | not signed in, or a bad sign-in code |
| 403 | `forbidden` | signed in, but this is not yours to do |
| 404 | `not_found` | it does not exist, **or it is not yours** (we do not confirm it exists) |
| 409 | `conflict`, `invalid_transition`, `visit_open`, `visit_closed`, `job_not_startable` | the state does not allow it now |
| 422 | `invalid` | the input is wrong; `fields` says which |
| 429 | `rate_limited` | too many requests |
| 500 | `server_error` | a bug; the message carries an Error Log reference |

Requests Frappe refuses before fieldpro's code runs (no session, a bad CSRF token, an unknown
method) arrive in Frappe's own format (`exc_type`, `_server_messages`). Clients normalise both;
see `fieldpro-app/src/lib/errors.ts`.

**Dates and money.** Datetimes are ISO 8601 in UTC (`2026-11-04T06:00:00Z`); send them the same way,
with a zone. Dates are `YYYY-MM-DD`. Money is `{"amount": "1500.00", "currency": "KES"}`: a decimal
string, because floats lose cents.

**Paging.** Pass `next_cursor` back as `cursor`. Cursors are opaque; a new job arriving between pages
never repeats or skips a row (offsets would). `limit` defaults to 20, at most 100.

**Versioning.** Adding a field or an endpoint is safe in v1. Renaming or removing one, or changing
what it means, goes into `fieldpro.api.v2` beside v1. `meta.info` tells clients the oldest version
they may be.

## Endpoints

| Endpoint | Method | Who | |
|---|---|---|---|
| `meta.info` | GET | anyone | API version, minimum client version, server time, currency |
| `auth.request_otp` `mobile_no` | POST | anyone | sends a sign-in code (same answer for unknown numbers) |
| `auth.verify_otp` `mobile_no, code` | POST | anyone | returns `token` (`key:secret`), user and technician |
| `auth.session` | GET | signed in | who am I, my kind, my customers, the CSRF token (cookie sessions) |
| `auth.sign_out_device` | POST | technician | revokes the token on every device |
| `jobs.list_jobs` `scope=today\|open\|all, cursor, limit` | GET | technician | my jobs |
| `jobs.get_job` `job` | GET | anyone who may see it | job with visits, parts, photos and `actions` |
| `visits.start_visit` `job, client_id?, started_at?` | POST | technician | starts a visit; the first one moves the job to In Progress |
| `visits.end_visit` `visit, ended_at?, notes?` | POST | technician | |
| `visits.add_part` `visit, item_code, qty, client_id?` | POST | technician | priced from the Standard Selling list, taken from my van |
| `visits.add_photo` `visit, file_name, content` | POST | technician | base64 image, stored as a private file |
| `visits.van_stock` `search?` | GET | technician | parts in my van |
| `workflow.actions` `job` | GET | anyone who may see it | the actions I may take now |
| `workflow.apply` `job, action, signature?, signed_by?, reason?` | POST | per action | returns the job |
| `portal.book_job` `issue, description?, site_address?, contact_phone?, preferred_date?` | POST | customer | |
| `portal.my_jobs` `status?, cursor, limit` | GET | customer | newest first |
| `files.job_card` `job` | GET | anyone who may see it | PDF |
| `devices.register` / `devices.unregister` `token, platform?` | POST | signed in | push tokens |
| `reports.my_week` | GET | technician | last 7 days, cached |
| `sync.pull` `cursor?` | GET | technician | jobs changed since the cursor |
| `sync.push` `operations` | POST | technician | offline work; per-operation results |
| `webhooks.receive` `?source=sms\|payment` | POST | providers | signed with the inbound secret |

`client_id` makes a call safe to repeat: the same id twice does the work once.

## Live updates

Socket.io event `fieldpro_job` with `{id, status, technician, updated_at}`, published to the job's
technician and the customer's portal users. Connect to namespace `/<site name>` with the session
cookie or `Authorization: token <key>:<secret>`.

## Webhooks out

Set the URL and secret in Fieldpro Settings. Events `job.done` and `invoice.created` are POSTed as
`{"event", "id", "data"}` with headers `X-Fieldpro-Event`, `X-Fieldpro-Idempotency-Key` and
`X-Fieldpro-Signature: t=<unix time>,v1=<hex HMAC-SHA256 of "<t>.<body>">`. Answer 2xx; anything else
is retried after 1, 2, 4, 8 and 16 minutes, then marked Failed. Inbound callbacks are signed the same
way, and an event `id` seen before is answered `{"status": "duplicate"}`.
