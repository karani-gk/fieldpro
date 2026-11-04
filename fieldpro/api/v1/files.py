"""Documents: the job card PDF, served only to people who can read the job."""

import frappe
from frappe.utils.pdf import get_pdf

from fieldpro.api.endpoint import api
from fieldpro.services.jobs import JobService

PRINT_FORMAT = "Job Card"


@api(methods=["GET"])
def job_card(job: str):
	doc = JobService().get(job)  # permission check first: the PDF is built with system rights
	html = frappe.get_print("Service Job", doc.name, PRINT_FORMAT, doc=doc, no_letterhead=1)
	frappe.local.response.filename = f"job-card-{doc.name}.pdf"
	frappe.local.response.filecontent = get_pdf(html)
	frappe.local.response.type = "pdf"
