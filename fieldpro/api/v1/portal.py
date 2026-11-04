"""The customer portal: book a job and follow your company's jobs."""

from fieldpro.api import shapes
from fieldpro.api.endpoint import api, ok
from fieldpro.api.pagination import page_size
from fieldpro.services.jobs import JobService


@api(methods=["POST"])
def book_job(
	issue: str,
	description: str | None = None,
	site_address: str | None = None,
	contact_phone: str | None = None,
	preferred_date: str | None = None,
	customer: str | None = None,
):
	doc = JobService().book(
		issue=issue,
		customer=customer,
		description=description,
		site_address=site_address,
		contact_phone=contact_phone,
		preferred_date=preferred_date,
	)
	return ok(JobService().detail(doc.name))


@api(methods=["GET"])
def my_jobs(status: str | None = None, cursor: str | None = None, limit: int | None = None):
	page = JobService().customer_jobs(status=status, cursor=cursor, limit=page_size(limit))
	return ok(
		[shapes.job_summary(r) for r in page.rows], next_cursor=page.next_cursor, has_more=page.has_more
	)
