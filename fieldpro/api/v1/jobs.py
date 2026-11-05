"""Jobs for the technician app and the portal. Permission hooks decide which rows each caller sees."""

from fieldpro.api import shapes
from fieldpro.api.endpoint import api, ok
from fieldpro.api.pagination import page_size
from fieldpro.services.jobs import JobService


@api(methods=["GET"])
def list_jobs(scope: str = "today", cursor: str | None = None, limit: int | None = None):
	"""The technician's jobs. scope: today (default, includes overdue), open, all or finished."""
	page = JobService().technician_jobs(scope=scope, cursor=cursor, limit=page_size(limit))
	return ok(
		[shapes.job_summary(r) for r in page.rows], next_cursor=page.next_cursor, has_more=page.has_more
	)


@api(methods=["GET"])
def get_job(job: str):
	"""One job with its visits, parts, photos and the actions this user may take now."""
	return ok(JobService().detail(job))
