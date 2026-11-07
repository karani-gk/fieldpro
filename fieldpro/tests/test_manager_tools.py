"""The manager app's invoices, settings and customers screens (invoice_desk.py, settings_desk.py,
customer_directory.py): managers only, ERPNext's own permissions for invoices, and no secrets."""

import frappe

from fieldpro.api.errors import Forbidden, Invalid, InvalidTransition
from fieldpro.api.v1 import manage as endpoints
from fieldpro.services.customer_directory import CustomerDirectory
from fieldpro.services.dispatch import JobQueue
from fieldpro.services.invoice_desk import InvoiceDesk
from fieldpro.services.job_flow import COMPLETE, SIGN_OFF, JobFlow
from fieldpro.services.settings_desk import EDITABLE_SETTINGS, SettingsDesk
from fieldpro.tests import factories
from fieldpro.tests.base import FieldproTestCase


class ManagerToolsTestCase(FieldproTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		# The demo manager's roles: a field manager who also does the accounts.
		cls.accounts_manager = factories.user(["Field Manager", "Accounts User"], website=False)

	def as_accounts(self, fn):
		return factories.as_user(self.accounts_manager, fn)

	def done_job(self) -> str:
		"""A signed-off job with hours and a part, and (in tests) no invoice yet."""
		job = factories.job(self.cust_x, technician_name=self.tech_a, estimated=1000)
		factories.finished_visit(job, self.tech_a_user, hours=2, parts=((factories.PART, 1),))
		factories.as_user(self.tech_a_user, lambda: JobFlow().apply(job, COMPLETE))
		factories.as_user(
			self.tech_a_user,
			lambda: JobFlow().apply(job, SIGN_OFF, signature=factories.SIGNATURE, signed_by="X"),
		)
		return job


class TestOnlyManagers(ManagerToolsTestCase):
	def test_technicians_and_customers_are_refused(self):
		for user in (self.tech_a_user, self.cust_x_user):
			for make in (InvoiceDesk, SettingsDesk, CustomerDirectory):
				with self.assertRaises(Forbidden, msg=f"{user} {make.__name__}"):
					factories.as_user(user, make)

	def test_invoices_need_an_accounts_role(self):
		with self.assertRaises(Forbidden):
			factories.as_user(self.manager, InvoiceDesk)

	def test_the_endpoint_answers_403_in_the_one_error_format(self):
		def call():
			frappe.local.response = frappe._dict()
			endpoints.invoice_summary()
			return frappe.local.response

		response = factories.as_user(self.manager, call)
		self.assertEqual(response.http_status_code, 403)
		self.assertEqual(response["error"]["code"], "forbidden")


class TestInvoiceDesk(ManagerToolsTestCase):
	def test_a_finished_job_without_an_invoice_is_listed_and_made_once(self):
		job = self.done_job()
		waiting = self.as_accounts(lambda: InvoiceDesk().summary())["uninvoiced_jobs"]
		self.assertIn(job, [j["id"] for j in waiting])

		first = self.as_accounts(lambda: InvoiceDesk().make_for_job(job))
		second = self.as_accounts(lambda: InvoiceDesk().make_for_job(job))
		self.assertEqual(first, second)
		self.assertEqual(frappe.db.count("Sales Invoice", {"service_job": job}), 1)
		waiting = self.as_accounts(lambda: InvoiceDesk().summary())["uninvoiced_jobs"]
		self.assertNotIn(job, [j["id"] for j in waiting])

	def test_an_unfinished_job_is_not_invoiced(self):
		job = factories.job(self.cust_x, technician_name=self.tech_a)
		with self.assertRaises(InvalidTransition):
			self.as_accounts(lambda: InvoiceDesk().make_for_job(job))

	def test_the_list_filters_by_status_customer_and_search(self):
		job = self.done_job()
		invoice = self.as_accounts(lambda: InvoiceDesk().make_for_job(job))

		def ids(**filters):
			return [r.name for r in self.as_accounts(lambda: InvoiceDesk().page(**filters, limit=100)).rows]

		self.assertIn(invoice, ids(status="Draft", customer=self.cust_x))
		self.assertNotIn(invoice, ids(status="Paid"))
		self.assertNotIn(invoice, ids(customer=self.cust_y))
		self.assertEqual(ids(search=job), [invoice])
		with self.assertRaises(Invalid):
			ids(status="Lost")

	def test_submitting_a_draft_makes_it_owed(self):
		job = self.done_job()
		invoice = self.as_accounts(lambda: InvoiceDesk().make_for_job(job))
		row = self.as_accounts(lambda: (InvoiceDesk().submit(invoice), InvoiceDesk().row(invoice))[1])
		self.assertFalse(row["is_draft"])
		self.assertEqual(row["job"], job)
		self.assertIn("download_pdf", row["pdf_url"])
		with self.assertRaises(InvalidTransition):
			self.as_accounts(lambda: InvoiceDesk().submit(invoice))

	def test_the_detail_shows_lines_totals_and_the_job(self):
		job = self.done_job()
		invoice = self.as_accounts(lambda: InvoiceDesk().make_for_job(job))
		detail = self.as_accounts(lambda: InvoiceDesk().detail(invoice))
		self.assertEqual(
			(detail["id"], detail["job"], detail["technician"]["id"]), (invoice, job, self.tech_a)
		)
		codes = [line["item_code"] for line in detail["items"]]
		self.assertIn(factories.PART, codes)
		self.assertIn("SVC-LABOUR", codes)
		self.assertEqual(detail["grand_total"], detail["total"])
		self.assertIn("issue", detail)

	def test_the_detail_is_only_for_job_invoices_and_accounts(self):
		with self.assertRaises(Invalid):
			self.as_accounts(lambda: InvoiceDesk().detail("NO-SUCH-INVOICE"))
		with self.assertRaises(Forbidden):
			factories.as_user(self.manager, lambda: InvoiceDesk().detail("NO-SUCH-INVOICE"))

	def test_the_summary_totals_drafts(self):
		job = self.done_job()
		before = self.as_accounts(lambda: InvoiceDesk().summary())["draft"]["count"]
		self.as_accounts(lambda: InvoiceDesk().make_for_job(job))
		after = self.as_accounts(lambda: InvoiceDesk().summary())["draft"]
		self.assertEqual(after["count"], before + 1)
		self.assertTrue(after["amount"]["currency"])


class TestSettingsDesk(ManagerToolsTestCase):
	def setUp(self):
		doc = frappe.get_doc("Fieldpro Settings")
		self.saved = {f: doc.get(f) for f in EDITABLE_SETTINGS}

	def tearDown(self):
		doc = frappe.get_doc("Fieldpro Settings")
		doc.update(self.saved)
		doc.save(ignore_permissions=True)
		super().tearDown()

	def test_no_secret_reaches_the_screen(self):
		data = factories.as_user(self.manager, lambda: SettingsDesk().read())
		for secret in (
			"fcm_service_account",
			"partner_webhook_secret",
			"inbound_webhook_secret",
			"access_code",
		):
			self.assertNotIn(secret, data)
		self.assertTrue(data["can_edit"])
		self.assertIn("Email", data["choices"]["sign_in_code_channel"])

	def test_a_manager_changes_the_everyday_settings(self):
		labour = frappe.db.get_value("Item", {"is_stock_item": 0, "disabled": 0}, "name")
		changes = {"approval_threshold": 12345, "labour_rate": 900, "labour_item": labour}
		data = factories.as_user(
			self.manager, lambda: (SettingsDesk().update(changes), SettingsDesk().read())[1]
		)
		self.assertEqual(
			(data["approval_threshold"], data["labour_rate"], data["labour_item"]), (12345, 900, labour)
		)

	def test_secrets_and_bad_values_are_refused(self):
		stock_item = frappe.db.get_value("Item", {"is_stock_item": 1}, "name")
		for changes in (
			{"partner_webhook_secret": "x"},
			{"approval_threshold": -1},
			{"labour_rate": ""},
			{"labour_item": stock_item},
			{"sign_in_code_channel": "Pigeon"},
		):
			with self.assertRaises(Invalid, msg=str(changes)):
				factories.as_user(self.manager, lambda: SettingsDesk().update(changes))


class TestCustomerDirectory(ManagerToolsTestCase):
	def test_customers_show_open_jobs_and_only_accounts_see_what_is_owed(self):
		factories.job(self.cust_x, technician_name=self.tech_a)
		name = frappe.db.get_value("Customer", self.cust_x, "customer_name")

		plain = factories.as_user(self.manager, lambda: CustomerDirectory().search(name))
		self.assertEqual([c["id"] for c in plain], [self.cust_x])
		self.assertGreaterEqual(plain[0]["open_jobs"], 1)
		self.assertIsNone(plain[0]["owed"])

		accounts = self.as_accounts(lambda: CustomerDirectory().search(name))
		self.assertIsNotNone(accounts[0]["owed"])

	def test_the_job_list_filters_by_customer(self):
		mine = factories.job(self.cust_x)
		other = factories.job(self.cust_y)
		rows = factories.as_user(self.manager, lambda: JobQueue().page(customer=self.cust_x, limit=100)).rows
		names = [r.name for r in rows]
		self.assertIn(mine, names)
		self.assertNotIn(other, names)
