"""Row-level security for jobs and visits (hooks.py: permission_query_conditions, has_permission).

Role permissions on the DocTypes say what a role may do at all; these hooks narrow it to the
rows that are theirs. A technician sees only jobs assigned to them, a customer only their own
company's jobs. Both hooks must agree: the query condition filters every list (Desk, REST,
frappe.get_list) and has_permission decides for one document (forms, get_doc, file downloads).
"""

import frappe

from fieldpro.access import AccessProfile


def _job_condition(profile: AccessProfile, table: str) -> str:
	if profile.is_manager:
		return ""
	if profile.technician:
		return f"`tab{table}`.`technician` = {frappe.db.escape(profile.technician)}"
	if profile.customers:
		names = ", ".join(frappe.db.escape(c) for c in profile.customers)
		return f"`tab{table}`.`customer` in ({names})"
	return "1 = 0"


def service_job_query(user: str | None = None, doctype: str | None = None) -> str:
	return _job_condition(AccessProfile(user), "Service Job")


def job_visit_query(user: str | None = None, doctype: str | None = None) -> str:
	return _job_condition(AccessProfile(user), "Job Visit")


def technician_query(user: str | None = None, doctype: str | None = None) -> str:
	profile = AccessProfile(user)
	if profile.is_manager:
		return ""
	if profile.technician:
		return f"`tabTechnician`.`name` = {frappe.db.escape(profile.technician)}"
	return "1 = 0"


def has_job_permission(doc, ptype: str | None = None, user: str | None = None) -> bool:
	"""Service Job and Job Visit share the rule: the row's technician or customer must be yours.

	A hook can only take away what role permissions give: False denies, True leaves the role
	permissions to decide. (Frappe treats None as a denial too, so never return it.)"""
	profile = AccessProfile(user)
	if profile.is_manager:
		return True
	if doc.is_new() and profile.customers and doc.doctype == "Service Job":
		# A customer booking a job: the edit guard on Service Job checks the customer field.
		return True
	return profile.can_see_job(doc.get("technician"), doc.get("customer"))


def has_technician_permission(doc, ptype: str | None = None, user: str | None = None) -> bool:
	profile = AccessProfile(user)
	return profile.is_manager or profile.technician == doc.name
