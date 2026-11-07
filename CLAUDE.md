# CLAUDE.md - fieldpro (backend)

Teaching project for UPEO Academy's "ERPNext as a Platform" course: learners read this code, so
endpoints stay thin, rules live in `fieldpro/services/`, and comments explain why.

- Bench: `/home/karani/projects/teaching/fieldpro-bench` (Frappe 16.23.0, ERPNext 16.23.1), site
  `fieldpro.localhost`, ports 8030/9030/11030/13030. Start with `/home/karani/projects/teaching/start-backend.sh`.
- Tests: `bench --site fieldpro.localhost run-tests --app fieldpro` (needs the demo company: run
  `bench --site <site> fieldpro-demo` once on a new site). Lint: `ruff check fieldpro && ruff format fieldpro`.
- Python 3.14: ruff writes PEP 758 `except A, B:` without parentheses. That is valid here.
- Repos are public: karani-gk/fieldpro-frappe (this app) and karani-gk/fieldpro-nextjs (renamed
  2026-11-04 from fieldpro and fieldpro-app; GitHub redirects the old names). MIT, (c) Upeosoft.
- Activation (2026-11-04, owner's decision): nobody signs in until the installation is activated
  ONCE with the access code UPEO Academy emails to course buyers (`services/activation.py`).
  Codes are Ed25519-signed by the academy (`academy/catalogue/system_access.py`, private key in
  its site_config `system_access_signing_key`, owner's copy at ~/.config/upeo/); only the public
  key is here. Changing the key pair means shipping the new public key here. The local site is
  activated with a test code for e2e-learner@example.com.

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
- `frappe.Redirect` defaults to 301, which browsers cache: a redirect that must stop later (the
  /login to /activate one) raises `frappe.Redirect(302)`.
- Frappe's Desk login page shows "Invalid Login" for any error, whatever the message: send people
  elsewhere before the form (update_website_context redirect) rather than relying on the message.
- An `on_login` hook must raise a Frappe exception (AuthenticationError); fieldpro's ApiError
  inside Frappe's own login becomes a 500.
- Moving the bench folder breaks absolute paths in files AND symlinks: `sites/assets/<app>` and
  `apps/*/<app>/public/node_modules` pointed at the old place, so every /assets URL was a 404 and
  job card PDFs failed ("broken image links": wkhtmltopdf could not load print.bundle.css). After a
  move, check `find . -xtype l` and `grep -rIl <old path>` (the shell's grep is a function that
  skips env/; use `find ... -exec grep`).

## Field Service desk (2026-11-05)

- The Desk home icon, sidebar, workspace, number cards and charts are standard files: edit them in
  Desk with developer_mode on and Frappe rewrites the files. Migrate deletes a standard Desktop Icon
  or Workspace Sidebar that has no file (`remove_orphan_entities`), so never keep one only in the DB.
- In Frappe 16.23 the Desktop Icon `roles` table is not checked. A sidebar icon shows when the user
  can see at least one item in its Workspace Sidebar, so that sidebar lists only fieldpro DocTypes:
  adding Customer or Sales Invoice there would give the icon to every accountant. The workspace
  itself is limited to Field Manager and System Manager by its roles.
- The icon image is found by name: `public/icons/desktop_icons/{solid,subtle}/field_service.svg`
  (scrubbed label), one per Desk icon style. `logo_url` is only a fallback.
- Kanban Boards have no standard form; `services/job_board.py` creates the Job Board once
  (after_install, after_migrate) and never overwrites it.
- A shortcut's `stats_filter` with 5-element filters loses its last filter (`cleanup_filters` in
  Frappe's utils.js): write 4-element filters.
- The Desk home logs one 404 for `/undefined` with or without the Field Service icon: it is
  Frappe's, not ours.

## Manager app in Vue (2026-11-05)

- The owner asked for the manager interface in Vue.js: `frontend/` (Vue 3, vue-router 4, Vite 8,
  plain CSS with the Next.js app's palette; no UI kit) served at `/manage` by `www/manage.py`.
  The Desk workspace stays as it is. API: `api/v1/manage.py` over `services/dispatch.py`.
- `bench build` runs the root package.json `build` (`cd frontend && yarn build`); output goes to
  `fieldpro/public/manage/` (gitignored) and `www/manage.py` finds the hashed files in Vite's
  `.vite/manifest.json`. Vite 8 calls the input option `rolldownOptions`, not `rollupOptions`.
- The workflow's Assign transition has the condition `doc.technician`, so `get_transitions`
  never offers Assign for a job without one: the board treats Booked to Assigned as "open the
  assign dialog" (`frontend/src/lib/board.js` dropAction).
- Field Manager alone cannot read Customer; the booking picker uses `get_all` behind ManagerOnly.
- Dashboard counts come from the workspace's Number Cards (`get_result` with the card's own
  `filters_json`): change a card in Desk and both screens follow.
- Field managers opening a Desk page the app replaces (home, Field Service workspace, Service Job
  list/board/form, Technician list) are redirected to /manage by a `before_request` hook
  (`landing_hooks.py`, rules in `services/manager_landing.py`). `?desk=1` on a Desk URL sets a
  browser-session cookie that stops it ("Switch to Desk"); opening /manage, signing in and
  signing out clear it (on_login/on_logout), or the choice outlived the sign-in. System
  Managers and Administrator are never redirected on page loads or sign-in (only the Field
  Service icon below). Setting: Fieldpro Settings "Keep Field Managers
  in Desk" (worded so blank means on: a Single's Check that was never saved reads 0, not its default).
- `frappe.Redirect` is only handled while a web page renders; in `before_request` raise a werkzeug
  `HTTPException(response=redirect(url, 302))`.
- Never put a URL item in the Field Service Workspace Sidebar: every Desk user can see it, so all
  of them get the Field Service icon (test_desk catches it). The way back lives in the workspace.
  Desk opens URL shortcuts in a new tab. Frappe's apps screen (`add_to_apps_screen`) shows nothing
  in v16 Desk for these users, so it is not used.
- Migrate only syncs a standard file whose `modified` is newer than the DB copy. To undo a change
  after migrating it, reload by absolute path with `import_file_by_path(path, force=True)`.
- Forms in the manager app are dialogs (`BaseModal`): it emits `close` only after its leave
  animation, so close it through the `close` slot prop or `modal.close()` (template ref), never by
  unmounting it with v-if directly, or the closing animation is skipped. /manage/jobs/new opens
  the New job dialog over the list (Desk's new Service Job redirects there).
- Desk opens a workspace (home icon, sidebar, search) inside its single-page app: no request
  reaches before_request. For every manager (Administrator and System Managers too: owner's
  choice 2026-11-05, they click Field Service to get the app) `public/js/manager_app.js`
  (app_include_js, a plain file, no bundle) sends the Field Service workspace route to /manage,
  except with ?desk=1 (/desk/field-service?desk=1 opens the workspace, e.g. to edit it). Told who by the boot
  (`boot_session` -> `fieldpro_manager_app`). The boot is cached per user: `clear-cache` after
  changing the rule. "Switch to Desk" therefore lands on the Desk home, not that workspace. An
  "External" Desktop Icon would also work but Desk opens it in a new tab.

## Manager app: customers, invoices, settings (2026-11-07)

- Owner asked for settings, invoices "and other things" in the Vue app: added Customers,
  Invoices and Settings screens over `services/customer_directory.py`, `invoice_desk.py` and
  `settings_desk.py` (endpoints in `api/v1/manage.py`).
- Invoices follow ERPNext's permissions, not ManagerOnly alone: a Field Manager without an
  accounts role (Accounts User) gets a 403 with that reason, and the Customers "Owed" column is
  null for them. The dashboard's "Done but Not Invoiced" card still opens the Jobs list for
  that reason. Only invoices with `service_job` set appear or can be submitted from the app.
- "Draft invoice" calls `InvoiceService.create_for_job` directly (idempotent), the same code the
  background job runs. Submit asks first: it posts the ledger and takes the van's stock.
- Settings screen edits only `EDITABLE_SETTINGS`; push key, webhook secrets and activation never
  leave the server and stay in Desk ("All settings in Desk").
- Frappe 16 `get_list` refuses SQL functions as strings: write aggregates as
  `{"COUNT": "name", "as": "count"}`.
