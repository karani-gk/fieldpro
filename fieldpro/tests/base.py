import frappe
from frappe.tests import IntegrationTestCase

from fieldpro.tests import factories


class FieldproTestCase(IntegrationTestCase):
	"""Two technicians and two customers, each seeing only their own world."""

	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		factories.ensure_company()
		cls.tech_a, cls.tech_a_user = factories.technician()
		cls.tech_b, cls.tech_b_user = factories.technician()
		cls.cust_x, cls.cust_x_user = factories.customer()
		cls.cust_y, cls.cust_y_user = factories.customer()
		cls.manager = factories.manager()

	def tearDown(self):
		frappe.set_user("Administrator")
