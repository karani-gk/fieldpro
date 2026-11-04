import frappe
from frappe.model.document import Document

from fieldpro.services.job_events import JobEvents
from fieldpro.services.job_rules import JobRules


class ServiceJob(Document):
	def validate(self):
		JobRules(self).validate()

	def on_update(self):
		JobEvents(self).after_save()


def on_doctype_update():
	# The API's hot queries: a technician's jobs by date, a customer's jobs newest first, and
	# offline sync by modified. Without these, every phone refresh scans the whole table.
	frappe.db.add_index("Service Job", ["technician", "scheduled_date"])
	frappe.db.add_index("Service Job", ["technician", "modified"])
	frappe.db.add_index("Service Job", ["customer", "creation"])
