"""Test data: a company with stocked vans (from the demo seed, made once) and, per test, fresh
technicians, customers and jobs with unique names, so tests never depend on each other."""

import random

import frappe
from frappe.utils import add_to_date, now_datetime, today

from fieldpro.access import AccessProfile
from fieldpro.demo import ITEMS, DemoData
from fieldpro.services.job_flow import JobFlow
from fieldpro.services.visits import VisitService

SIGNATURE = "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNkYAAAAAYAAjCB0C8AAAAASUVORK5CYII="
PART = ITEMS[3][0]  # a run capacitor: cheap, plenty in every van


def ensure_company() -> None:
	demo = DemoData()
	demo.setup_company()
	demo.items()
	demo.warehouses_and_stock()
	demo.settings()


def suffix() -> str:
	return frappe.generate_hash(length=6).lower()


def user(roles: list[str], website: bool = True) -> str:
	email = f"t-{suffix()}@fieldpro.test"
	doc = frappe.get_doc(
		{
			"doctype": "User",
			"email": email,
			"first_name": "Test",
			"last_name": email.split("@")[0],
			"send_welcome_email": 0,
			"user_type": "Website User" if website else "System User",
		}
	).insert(ignore_permissions=True)
	doc.add_roles(*roles)
	return email


def technician() -> tuple[str, str]:
	"""(technician name, user email), with the first demo van."""
	email = user(["Field Technician"])
	name = (
		frappe.get_doc(
			{
				"doctype": "Technician",
				"full_name": f"Tech {email[2:8]}",
				"user": email,
				"mobile_no": f"+2547{random.randint(10_000_000, 99_999_999)}",
				"warehouse": DemoData()._van("Achieng Odhiambo"),
				"is_active": 1,
			}
		)
		.insert(ignore_permissions=True)
		.name
	)
	return name, email


def customer() -> tuple[str, str]:
	"""(customer name, portal user email)."""
	email = user(["Customer"])
	doc = frappe.get_doc(
		{
			"doctype": "Customer",
			"customer_name": f"Test Customer {suffix()}",
			"customer_type": "Company",
			"customer_group": frappe.db.get_value("Customer Group", {"is_group": 0}, "name"),
			"territory": frappe.db.get_value("Territory", {"is_group": 0}, "name"),
		}
	)
	doc.append("portal_users", {"user": email})
	doc.insert(ignore_permissions=True)
	return doc.name, email


def manager() -> str:
	return user(["Field Manager"], website=False)


def as_user(email: str, fn):
	previous = frappe.session.user
	frappe.set_user(email)
	try:
		return fn()
	finally:
		frappe.set_user(previous)


def job(
	customer_name: str, *, technician_name: str | None = None, estimated: float = 5000, assign: bool = True
) -> str:
	"""A job booked by a manager, assigned (state Assigned) unless assign=False."""
	doc = frappe.get_doc(
		{
			"doctype": "Service Job",
			"customer": customer_name,
			"issue": "Test issue",
			"scheduled_date": today(),
		}
	).insert(ignore_permissions=True)
	if technician_name and assign:
		doc.technician = technician_name
		doc.estimated_value = estimated
		doc.save(ignore_permissions=True)
		as_user("Administrator", lambda: JobFlow().apply(doc.name, "Assign"))
	return doc.name


def finished_visit(job_name: str, tech_email: str, hours: float = 2, parts=((PART, 1),)) -> str:
	def work():
		service = VisitService(AccessProfile(tech_email))
		visit = service.start(job_name, started_at=add_to_date(now_datetime(), hours=-hours))
		for code, qty in parts:
			service.add_part(visit.name, item_code=code, qty=qty)
		service.end(visit.name, ended_at=now_datetime())
		return visit.name

	return as_user(tech_email, work)
