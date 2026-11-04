"""Jinja helpers for print formats (hooks.py jinja)."""

import base64
import mimetypes

import frappe


def image_data_url(file_url: str | None) -> str:
	"""A private image inlined as a data URL. The PDF renderer cannot log in to fetch
	/private/files, so a signature has to travel inside the HTML."""
	if not file_url:
		return ""
	name = frappe.db.get_value("File", {"file_url": file_url}, "name")
	if not name:
		return ""
	content = frappe.get_doc("File", name).get_content()
	mime = mimetypes.guess_type(file_url)[0] or "image/png"
	return f"data:{mime};base64,{base64.b64encode(content).decode()}"


def company_name() -> str:
	"""The service company's name for documents (Fieldpro Settings, else the default company)."""
	from fieldpro.settings import AppSettings

	company = AppSettings().company
	return frappe.db.get_value("Company", company, "company_name") if company else ""
