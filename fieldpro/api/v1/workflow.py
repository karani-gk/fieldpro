"""Workflow actions from any client. The server decides which actions exist for whom."""

from fieldpro.api import shapes
from fieldpro.api.endpoint import api, ok
from fieldpro.services.job_flow import JobFlow
from fieldpro.services.jobs import JobService


@api(methods=["GET"])
def actions(job: str):
	"""The buttons to show: only actions this user may take on this job right now."""
	doc = JobService().get(job)
	return ok([shapes.action(t) for t in JobFlow().actions(doc)])


@api(methods=["POST"])
def apply(
	job: str,
	action: str,
	signature: str | None = None,
	signed_by: str | None = None,
	reason: str | None = None,
):
	"""Take an action. Sign Off On Site needs signature (PNG data URL) and signed_by; Reject needs reason."""
	JobService().get(job)  # 404 for a job you cannot see, before anything else
	JobFlow().apply(job, action, signature=signature, signed_by=signed_by, reason=reason)
	return ok(JobService().detail(job))
