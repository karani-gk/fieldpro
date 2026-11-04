"""Offline sync for the technician app (services/sync.py explains the protocol)."""

import json

from fieldpro.api.endpoint import api, ok
from fieldpro.api.pagination import page_size
from fieldpro.services.sync import SyncService


@api(methods=["GET"])
def pull(cursor: str | None = None, limit: int | None = None):
	return ok(SyncService().pull(cursor=cursor, limit=page_size(limit, default=50)))


@api(methods=["POST"])
def push(operations):
	if isinstance(operations, str):
		operations = json.loads(operations)
	return ok(SyncService().push(operations))
