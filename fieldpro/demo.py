"""Demo data in one command: `bench --site fieldpro.localhost fieldpro-demo`.

Baridi Services Ltd, an AC and refrigeration company in Nairobi: three technicians with stocked
vans, three customers with portal users, and jobs in every state of the workflow. Jobs are moved
through the real services as the real users (a customer books, the manager assigns, the
technician visits and completes), so the data is exactly what the apps would have produced.

Safe to run twice: everything is looked up before it is made.

Sign in (password for every demo user: fieldpro-demo):
  Manager (Desk)  manager@fieldpro.test
  Technicians     +254700100001 Achieng, +254700100002 Otieno, +254700100003 Wanjiru (code in SMS Log)
  Customers       clinic@fieldpro.test, apartments@fieldpro.test, supermarket@fieldpro.test
"""

import frappe
from frappe.utils import add_days, add_to_date, get_datetime, now_datetime, today

from fieldpro.access import AccessProfile
from fieldpro.services.job_flow import ACCEPT, COMPLETE, SIGN_OFF, JobFlow
from fieldpro.services.jobs import JobService
from fieldpro.services.visits import VisitService

PASSWORD = "fieldpro-demo"
COMPANY = "Baridi Services Ltd"
ABBR = "BSL"
MANAGER = "manager@fieldpro.test"
# A 1x1 transparent PNG, standing in for a signature drawn on the phone.
SIGNATURE = "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNkYAAAAAYAAjCB0C8AAAAASUVORK5CYII="

ITEMS = [
	# code, name, uom, selling rate, stock per van
	("COMP-1HP", "Compressor 1HP", "Nos", 18500, 2),
	("GAS-R134A", "Refrigerant R134a", "Kg", 2200, 10),
	("THERM-01", "Digital Thermostat", "Nos", 1800, 6),
	("CAP-35UF", "Run Capacitor 35uF", "Nos", 650, 12),
	("FAN-MOTOR", "Condenser Fan Motor", "Nos", 4500, 3),
	("FILTER-DRIER", "Filter Drier", "Nos", 900, 8),
]
LABOUR_ITEM = ("SVC-LABOUR", "Service Labour (hour)", "Hour", 1500)

TECHNICIANS = [
	("Achieng Odhiambo", "achieng@fieldpro.test", "+254700100001"),
	("Otieno Kamau", "otieno@fieldpro.test", "+254700100002"),
	("Wanjiru Njeri", "wanjiru@fieldpro.test", "+254700100003"),
]
CUSTOMERS = [
	("Wanjiku Clinic", "clinic@fieldpro.test", "Grace Wanjiku", "Ngong Road, Nairobi"),
	(
		"Kilimani Heights Apartments",
		"apartments@fieldpro.test",
		"Peter Mwangi",
		"Argwings Kodhek Rd, Kilimani",
	),
	("Mama Pima Supermarket", "supermarket@fieldpro.test", "Halima Ali", "Moi Avenue, Nairobi CBD"),
]


class DemoData:
	def seed(self) -> None:
		frappe.flags.mute_emails = True
		self.setup_company()
		self.items()
		self.warehouses_and_stock()
		self.users_and_technicians()
		self.customers()
		self.settings()
		self.oauth_client()
		frappe.db.commit()
		if not frappe.db.count("Service Job"):
			self.jobs()
			frappe.db.commit()
		frappe.set_user("Administrator")
		print(__doc__.split("Sign in", 1)[1].join(["Sign in", ""]))

	# ---------------------------------------------------------------- ERPNext basics

	def setup_company(self) -> None:
		if frappe.is_setup_complete():
			return
		from frappe.desk.page.setup_wizard.setup_wizard import setup_complete

		year = get_datetime(today()).year
		setup_complete(
			{
				"language": "English",
				"country": "Kenya",
				"timezone": "Africa/Nairobi",
				"currency": "KES",
				"full_name": "Fieldpro Admin",
				"email": "admin@fieldpro.test",
				"password": PASSWORD,
				"company_name": COMPANY,
				"company_abbr": ABBR,
				"chart_of_accounts": "Standard",
				"fy_start_date": f"{year}-01-01",
				"fy_end_date": f"{year}-12-31",
				"setup_demo": 0,
			}
		)
		frappe.db.commit()
		frappe.clear_cache()
		if not frappe.db.exists("Company", COMPANY):
			frappe.throw(f"ERPNext setup did not create {COMPANY}. See the Error Log.")

	def items(self) -> None:
		if not frappe.db.exists("Item Group", "Spares"):
			frappe.get_doc(
				{"doctype": "Item Group", "item_group_name": "Spares", "parent_item_group": "All Item Groups"}
			).insert()
		for uom in ("Kg", "Hour"):
			if not frappe.db.exists("UOM", uom):
				frappe.get_doc({"doctype": "UOM", "uom_name": uom}).insert()
		for code, name, uom, rate, _stock in ITEMS:
			self._item(code, name, uom, rate, is_stock=1)
		code, name, uom, rate = LABOUR_ITEM
		self._item(code, name, uom, rate, is_stock=0, group="Services")

	def _item(self, code, name, uom, rate, *, is_stock, group="Spares") -> None:
		if not frappe.db.exists("Item", code):
			frappe.get_doc(
				{
					"doctype": "Item",
					"item_code": code,
					"item_name": name,
					"item_group": group if frappe.db.exists("Item Group", group) else "All Item Groups",
					"stock_uom": uom,
					"is_stock_item": is_stock,
					"standard_rate": rate,
					"valuation_rate": rate * 0.6,
				}
			).insert()
		if not frappe.db.exists("Item Price", {"item_code": code, "price_list": "Standard Selling"}):
			frappe.get_doc(
				{
					"doctype": "Item Price",
					"item_code": code,
					"price_list": "Standard Selling",
					"price_list_rate": rate,
				}
			).insert()

	def warehouses_and_stock(self) -> None:
		self._inventory_account()
		vans = [self._van(full_name) for full_name, _email, _mobile in TECHNICIANS]
		# ERPNext caches warehouse accounts for the whole run; the vans were just created.
		frappe.flags.pop("warehouse_account_map", None)
		for warehouse in vans:
			if frappe.db.count("Bin", {"warehouse": warehouse}):
				continue
			entry = frappe.get_doc(
				{
					"doctype": "Stock Entry",
					"stock_entry_type": "Material Receipt",
					"company": COMPANY,
					"items": [
						{"item_code": code, "qty": stock, "t_warehouse": warehouse, "basic_rate": rate * 0.6}
						for code, _name, _uom, rate, stock in ITEMS
					],
				}
			)
			entry.insert()
			entry.submit()

	@staticmethod
	def _inventory_account() -> None:
		"""Perpetual inventory posts stock to an account; the wizard leaves the company default empty."""
		if frappe.db.get_value("Company", COMPANY, "default_inventory_account"):
			return
		account = frappe.db.get_value(
			"Account", {"company": COMPANY, "account_type": "Stock", "is_group": 0}, "name"
		)
		frappe.db.set_value("Company", COMPANY, "default_inventory_account", account)

	def _van(self, full_name: str) -> str:
		label = f"Van {full_name.split()[0]}"
		name = f"{label} - {ABBR}"
		if not frappe.db.exists("Warehouse", name):
			frappe.get_doc(
				{
					"doctype": "Warehouse",
					"warehouse_name": label,
					"company": COMPANY,
					"parent_warehouse": f"All Warehouses - {ABBR}",
				}
			).insert()
		return name

	# ---------------------------------------------------------------- people

	def users_and_technicians(self) -> None:
		self._user(
			MANAGER, "Faith", "Muthoni", ["Field Manager", "Accounts User", "Stock User", "Sales User"]
		)
		for full_name, email, mobile in TECHNICIANS:
			first, last = full_name.split()
			self._user(email, first, last, ["Field Technician"], website_user=True)
			if not frappe.db.exists("Technician", {"user": email}):
				frappe.get_doc(
					{
						"doctype": "Technician",
						"full_name": full_name,
						"user": email,
						"mobile_no": mobile,
						"warehouse": self._van(full_name),
						"is_active": 1,
					}
				).insert()

	def customers(self) -> None:
		for name, email, contact, _address in CUSTOMERS:
			first, last = contact.split()
			self._user(email, first, last, ["Customer"], website_user=True)
			if frappe.db.exists("Customer", name):
				continue
			customer = frappe.get_doc(
				{
					"doctype": "Customer",
					"customer_name": name,
					"customer_type": "Company",
					"customer_group": "Commercial"
					if frappe.db.exists("Customer Group", "Commercial")
					else "All Customer Groups",
					"territory": "Kenya" if frappe.db.exists("Territory", "Kenya") else "All Territories",
				}
			)
			customer.append("portal_users", {"user": email})
			customer.insert()

	@staticmethod
	def _user(email, first, last, roles, website_user=False) -> None:
		if frappe.db.exists("User", email):
			return
		user = frappe.get_doc(
			{
				"doctype": "User",
				"email": email,
				"first_name": first,
				"last_name": last,
				"send_welcome_email": 0,
				"user_type": "Website User" if website_user else "System User",
				"new_password": PASSWORD,
			}
		)
		user.insert(ignore_permissions=True)
		user.add_roles(*roles)

	def settings(self) -> None:
		settings = frappe.get_single("Fieldpro Settings")
		settings.update(
			{
				"company": COMPANY,
				"labour_item": LABOUR_ITEM[0],
				"labour_rate": LABOUR_ITEM[3],
				"approval_threshold": 20000,
			}
		)
		settings.save()

	@staticmethod
	def oauth_client() -> None:
		"""A partner's accounting system that signs in with OAuth2 (docs/AUTH.md)."""
		if frappe.db.exists("OAuth Client", {"app_name": "Partner Accounting"}):
			return
		frappe.get_doc(
			{
				"doctype": "OAuth Client",
				"app_name": "Partner Accounting",
				"scopes": "all openid",
				"redirect_uris": "http://localhost:4000/callback",
				"default_redirect_uri": "http://localhost:4000/callback",
				"grant_type": "Authorization Code",
				"response_type": "Code",
				"skip_authorization": 0,
			}
		).insert(ignore_permissions=True)

	# ---------------------------------------------------------------- jobs, as the real users

	def jobs(self) -> None:
		clinic, apartments, supermarket = (c[0] for c in CUSTOMERS)
		achieng, otieno, wanjiru = (t[1] for t in TECHNICIANS)
		day = today()

		# Finished last week, so the reports have history.
		for days_ago, customer, tech, issue in [
			(6, supermarket, wanjiru, "Quarterly AC service"),
			(5, clinic, achieng, "Thermostat replacement"),
			(4, apartments, otieno, "Gas top-up, unit 2A"),
			(3, supermarket, wanjiru, "Cold room door seal"),
			(2, clinic, achieng, "Fridge compressor noise"),
		]:
			job = self._book(customer, issue, add_days(day, -days_ago))
			self._assign(job, tech, estimated=8000)
			self._visit(
				job, tech, add_days(day, -days_ago), hours=2.5, parts=[("CAP-35UF", 1), ("GAS-R134A", 1)]
			)
			self._complete(job, tech)
			self._as(
				tech,
				lambda j=job: JobFlow().apply(j, SIGN_OFF, signature=SIGNATURE, signed_by="Site supervisor"),
			)

		self._book(
			clinic,
			"Fridge not cooling",
			day,
			description="The vaccine fridge reads 12 degrees since morning.",
		)
		job = self._book(apartments, "AC not cooling in unit 4B", day)
		self._assign(job, achieng, estimated=6000)

		job = self._book(
			supermarket, "Cold room temperature alarm", day, description="Alarm keeps going off at night."
		)
		self._assign(job, otieno, estimated=9000)
		self._start_only(job, otieno)

		job = self._book(clinic, "Vaccine fridge service", add_days(day, -1))
		self._assign(job, achieng, estimated=7000)
		self._visit(job, achieng, add_days(day, -1), hours=1.5, parts=[("THERM-01", 1)])
		self._complete(job, achieng)  # now Awaiting Sign-off: the clinic approves it in the portal

		job = self._book(apartments, "Compressor replacement, block C", add_days(day, -1))
		self._assign(job, otieno, estimated=45000)
		self._visit(
			job,
			otieno,
			add_days(day, -1),
			hours=4,
			parts=[("COMP-1HP", 1), ("GAS-R134A", 2), ("FILTER-DRIER", 1)],
		)
		self._complete(job, otieno)  # big job: Pending Approval for the manager

		job = self._book(supermarket, "Display chiller not cold", add_days(day, 1))
		self._assign(job, wanjiru, estimated=5000)

	def _as(self, user: str, fn):
		frappe.set_user(user)
		try:
			return fn()
		finally:
			frappe.set_user("Administrator")

	def _book(self, customer: str, issue: str, date, description: str | None = None) -> str:
		email, address = next((c[1], c[3]) for c in CUSTOMERS if c[0] == customer)
		# Booked from the portal as the customer; past dates are history, so the manager books those.
		if get_datetime(date).date() >= get_datetime(today()).date():
			doc = self._as(
				email,
				lambda: JobService(AccessProfile(email)).book(
					issue=issue, description=description, site_address=address, preferred_date=date
				),
			)
		else:
			doc = self._as(
				MANAGER,
				lambda: frappe.get_doc(
					{
						"doctype": "Service Job",
						"customer": customer,
						"issue": issue,
						"description": description,
						"site_address": address,
						"scheduled_date": date,
						"source": "Desk",
					}
				).insert(),
			)
		return doc.name

	def _assign(self, job: str, tech_email: str, estimated: float) -> None:
		technician = frappe.db.get_value("Technician", {"user": tech_email}, "name")

		def assign():
			doc = frappe.get_doc("Service Job", job)
			doc.technician = technician
			doc.estimated_value = estimated
			doc.scheduled_date = doc.scheduled_date or today()
			doc.save()
			JobFlow().apply(job, "Assign")

		self._as(MANAGER, assign)

	def _visit(self, job: str, tech_email: str, date, hours: float, parts: list) -> None:
		started = add_to_date(get_datetime(f"{date} 09:00:00"), hours=0)
		ended = add_to_date(started, hours=hours)

		def work():
			service = VisitService(AccessProfile(tech_email))
			visit = service.start(job, started_at=started)
			for item_code, qty in parts:
				service.add_part(visit.name, item_code=item_code, qty=qty)
			service.end(visit.name, ended_at=ended, notes="Work done and tested.")

		self._as(tech_email, work)

	def _start_only(self, job: str, tech_email: str) -> None:
		self._as(
			tech_email, lambda: VisitService(AccessProfile(tech_email)).start(job, started_at=now_datetime())
		)

	def _complete(self, job: str, tech_email: str) -> None:
		self._as(tech_email, lambda: JobFlow().apply(job, COMPLETE))


def seed() -> None:
	"""`bench --site <site> execute fieldpro.demo.seed` does the same as `fieldpro-demo`."""
	DemoData().seed()
