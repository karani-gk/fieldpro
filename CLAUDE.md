# CLAUDE.md - fieldpro (backend)

Teaching project for UPEO Academy's "ERPNext as a Platform" course: learners read this code, so
endpoints stay thin, rules live in `fieldpro/services/`, and comments explain why.

- Bench: `/home/karani/projects/teaching/fieldpro-bench` (Frappe 16.23.0, ERPNext 16.23.1), site
  `fieldpro.localhost`, ports 8030/9030/11030/13030. Start with `/home/karani/projects/teaching/start-backend.sh`.
- Tests: `bench --site fieldpro.localhost run-tests --app fieldpro` (needs the demo company: run
  `bench --site <site> fieldpro-demo` once on a new site). Lint: `ruff check fieldpro && ruff format fieldpro`.
- Python 3.14: ruff writes PEP 758 `except A, B:` without parentheses. That is valid here.
- No GitHub remote yet: ask the owner before creating one.

## Traps found while building (2026-11-04)

- In Frappe v16 a `has_permission` hook returning `None` DENIES (`if not result`). Return True to allow.
- `apply_workflow` reloads the document from the database: save any fields the action needs first
  (job_flow.py).
- A queued job runs as the user who queued it (often a customer): system work such as invoicing sets
  `frappe.set_user("Administrator")` in its entry point.
- `bench start` kills the daemon redis the setup scripts started (`shutdown nosave`), losing queued
  jobs; the hourly `tasks.invoice_finished_jobs` sweep is the safety net.
- ERPNext caches warehouse accounts per run (`frappe.flags.warehouse_account_map`): pop it after
  creating warehouses in the same run.
- Print formats have no `frappe.defaults` in Jinja; add a helper in `jinja.py`.
- A new Service Job carries DocType defaults (payment_status "Unpaid"); the booking guard compares
  with the default, not with empty.
- A JSON request body becomes the whole `form_dict`: Frappe drops the query string, so `?source=`
  never reaches a whitelisted method's arguments. Read URL parameters from `frappe.request.args`,
  and test webhook endpoints through `make_form_dict`, not by calling the service directly.
- `frappe.sendmail` raises OutgoingEmailError when no outgoing Email Account exists (it only queues
  with one, a site_config account, or `mute_emails`). Check `EmailAccount.find_outgoing()` first,
  as `otp.default_email_sender` does; that lookup is cached on `frappe.local` per request.
