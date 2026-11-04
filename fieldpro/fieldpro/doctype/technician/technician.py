import frappe
from frappe.model.document import Document

from fieldpro.access import TECHNICIAN_ROLE
from fieldpro.utils import normalise_mobile


class Technician(Document):
	def validate(self):
		# One format, so a sign-in code request finds the technician however the number is typed.
		self.mobile_no = normalise_mobile(self.mobile_no)

	def on_update(self):
		user = frappe.get_doc("User", self.user)
		if TECHNICIAN_ROLE not in frappe.get_roles(self.user):
			user.flags.ignore_permissions = True
			user.add_roles(TECHNICIAN_ROLE)
