# fieldpro (backend)

Field service from booking to invoice, on top of the ERPNext a business already uses. This Frappe
app is the backend for three clients: the technician app and the customer portal (the Next.js
`fieldpro-app`) and ERPNext Desk for managers.

Customers book jobs and approve finished work. Technicians sign in with a code sent to their
phone, record visits, parts, photos and the customer's signature, and keep working with no
signal. Managers assign and approve in Desk. Accounts gets a draft invoice for every finished job.

## Install

Needs Frappe and ERPNext v16.

```bash
bench get-app <this repo>
bench --site <site> install-app fieldpro
bench --site <site> fieldpro-demo        # optional: Baridi Services Ltd demo data, one command
bench --site <site> run-tests --app fieldpro
```

## Where things are

| | |
|---|---|
| `fieldpro/fieldpro/doctype/` | Technician, Service Job, Job Visit (+ Parts Used), Device Token, Partner Delivery, Callback Event, Fieldpro Settings |
| `fieldpro/fixtures/` | Roles, the Service Job workflow (states, actions, transitions), custom fields on Sales Invoice, Desk notifications |
| `fieldpro/permissions.py`, `access.py` | Row-level security: a technician sees only their jobs, a customer only their company's |
| `fieldpro/services/` | All business rules. Endpoints, controllers and background jobs call these |
| `fieldpro/api/` | The versioned API: `api/v1/*.py` endpoints, `endpoint.py` (one decorator), `errors.py` (one error format), `shapes.py` (response shapes), `pagination.py` (cursors) |
| `fieldpro/tasks.py`, `hooks.py` | Scheduled work and wiring |
| `fieldpro/fieldpro/print_format/job_card/` | The job card PDF |
| `fieldpro/fieldpro/report/technician_performance/` | Jobs and hours by technician in Desk |
| `fieldpro/demo.py`, `commands.py` | `bench fieldpro-demo` |
| `fieldpro/tests/` | Permission, workflow, sync, invoicing, webhook, OTP and API-contract tests |
| `docs/` | [API.md](docs/API.md) (the contract), [AUTH.md](docs/AUTH.md) (signing in, per client), `bruno/` (a request collection) |

## Course map

| Lesson | Read |
|---|---|
| Data model for API consumers | the DocType JSON files; `service_job.py` `on_doctype_update` (indexes) |
| Extending ERPNext from your app | `fixtures/custom_field.json`, `patches/v1_0/`, `services/invoicing.py` |
| A versioned API | `api/endpoint.py`, `api/errors.py`, `api/shapes.py`, `api/pagination.py`, `api/v1/` |
| Authentication | `services/otp.py`, `api/v1/auth.py`, `docs/AUTH.md` |
| Permissions as API security | `access.py`, `permissions.py`, `services/job_rules.py` (edit guard) |
| Jobs, visits and parts | `services/jobs.py`, `services/visits.py`, `services/visit_rules.py` |
| Workflows as state machines | `fixtures/workflow.json`, `services/job_flow.py`, `services/job_rules.py` |
| Realtime and push | `services/realtime.py`, `services/push.py`, `fixtures/notification.json` |
| Background jobs | `services/job_events.py`, `services/invoicing.py`, `tasks.py` |
| Webhooks in and out | `services/partner_webhooks.py`, `services/callbacks.py`, `api/v1/webhooks.py` |
| Photos and PDFs | `services/visits.py` (`add_photo`), `services/job_flow.py` (`SignatureStore`), `api/v1/files.py`, the Job Card print format, `jinja.py` |
| Reports | `services/reports.py`, the Technician Performance report, `api/v1/reports.py` |
| Offline sync | `services/sync.py`, `api/v1/sync.py` |
| Testing and versioning | `tests/`, `api/v1/__init__.py`, `.github/workflows/ci.yml` |

## License

MIT
