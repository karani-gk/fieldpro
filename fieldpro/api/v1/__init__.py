"""Version 1 of the fieldpro API: /api/method/fieldpro.api.v1.<module>.<function>.

The version is part of the path. A change that could break an installed app (a renamed field, a
removed endpoint, a different meaning) goes into v2 beside this one; v1 keeps working until the
last app that uses it has been updated. Adding a field or a new endpoint is safe in v1.
"""

API_VERSION = "1"
# Clients older than this are told to update (meta.info). Raise it only when v1 itself must change.
MIN_CLIENT_VERSION = "1.0.0"
