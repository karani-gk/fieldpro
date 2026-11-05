app_name = "fieldpro"
app_title = "Fieldpro"
app_publisher = "Upeosoft Limited"
app_description = "Field service from booking to invoice: a technician app, a customer portal and ERPNext Desk on one Frappe backend."
app_email = "upeosoft@gmail.com"
app_license = "mit"

required_apps = ["erpnext"]

# Fixtures: records the app needs on every site, kept in fieldpro/fixtures and loaded on migrate.
# Change them in Desk, then `bench --site <site> export-fixtures --app fieldpro`.
fixtures = [
	{"dt": "Role", "filters": [["name", "in", ["Field Technician", "Field Manager"]]]},
	{"dt": "Custom Field", "filters": [["module", "=", "Fieldpro"]]},
	{
		"dt": "Workflow State",
		"filters": [
			[
				"name",
				"in",
				[
					"Booked",
					"Assigned",
					"In Progress",
					"Pending Approval",
					"Awaiting Sign-off",
					"Done",
					"Rework",
					"Cancelled",
				],
			]
		],
	},
	{
		"dt": "Workflow Action Master",
		"filters": [
			[
				"name",
				"in",
				[
					"Assign",
					"Start",
					"Complete",
					"Approve",
					"Send Back",
					"Sign Off On Site",
					"Accept",
					"Reject",
					"Cancel",
				],
			]
		],
	},
	{"dt": "Workflow", "filters": [["name", "=", "Service Job"]]},
	{"dt": "Notification", "filters": [["module", "=", "Fieldpro"]]},
]

# The Job Board (Kanban) has no standard-file form, so it is created in code, once (job_board.py).
after_install = ["fieldpro.services.job_board.ensure_job_board"]
after_migrate = ["fieldpro.services.job_board.ensure_job_board"]

# Row-level security (permissions.py): technicians see their jobs, customers their company's.
permission_query_conditions = {
	"Service Job": "fieldpro.permissions.service_job_query",
	"Job Visit": "fieldpro.permissions.job_visit_query",
	"Technician": "fieldpro.permissions.technician_query",
}
has_permission = {
	"Service Job": "fieldpro.permissions.has_job_permission",
	"Job Visit": "fieldpro.permissions.has_job_permission",
	"Technician": "fieldpro.permissions.has_technician_permission",
}

doc_events = {
	"Sales Invoice": {
		"on_cancel": "fieldpro.events.invoice_cancelled",
		"on_trash": "fieldpro.events.invoice_cancelled",
	},
}

scheduler_events = {
	"cron": {
		# Retry partner webhooks that are due (services/partner_webhooks.py).
		"*/5 * * * *": ["fieldpro.services.partner_webhooks.retry_due"],
		# Tell technicians about tomorrow's jobs at 6pm (site time).
		"0 18 * * *": ["fieldpro.tasks.remind_tomorrows_jobs"],
	},
	"daily": ["fieldpro.tasks.send_daily_summary"],
	"hourly": ["fieldpro.tasks.invoice_finished_jobs"],
}

# Nobody signs in until the installation is activated with a course access code.
on_login = ["fieldpro.activation_hooks.refuse_sign_in"]
update_website_context = ["fieldpro.activation_hooks.redirect_login_page"]

# The manager's Vue app owns every path under /manage (www/manage.py serves it).
website_route_rules = [{"from_route": "/manage/<path:app_path>", "to_route": "manage"}]

jinja = {"methods": ["fieldpro.jinja.image_data_url", "fieldpro.jinja.company_name"]}
