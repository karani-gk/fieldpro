"""/activate: enter the access code from the course email, once per installation."""

from fieldpro.services.activation import Activation

no_cache = 1


def get_context(context):
	context.no_cache = 1
	context.title = "Activate fieldpro"
	context.update(Activation().status())
