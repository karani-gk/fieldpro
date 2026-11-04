from frappe.model.document import Document

from fieldpro.services.reports import WeekStats
from fieldpro.services.visit_rules import JobTotals, VisitRules


class JobVisit(Document):
	def validate(self):
		VisitRules(self).validate()

	def on_update(self):
		JobTotals().refresh(self.service_job)
		WeekStats().clear(self.technician)

	def on_trash(self):
		WeekStats().clear(self.technician)

	def after_delete(self):
		JobTotals().refresh(self.service_job)
