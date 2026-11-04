"""Bench commands from this app (Frappe loads `commands` from <app>.commands)."""

import click
from frappe.commands import get_site, pass_context


@click.command("fieldpro-demo")
@pass_context
def fieldpro_demo(context):
	"""Load the Baridi Services demo: company, technicians, customers, stock and jobs."""
	import frappe

	from fieldpro.demo import DemoData

	site = get_site(context)
	frappe.init(site=site)
	frappe.connect()
	try:
		DemoData().seed()
	finally:
		frappe.destroy()


@click.command("fieldpro-activate")
@click.argument("code")
@pass_context
def fieldpro_activate(context, code):
	"""Activate this installation with the access code from your course email."""
	import frappe

	from fieldpro.services.activation import Activation

	frappe.init(site=get_site(context))
	frappe.connect()
	try:
		Activation().activate(code)
		frappe.db.commit()
		click.echo("fieldpro is activated. Everyone can sign in now.")
	finally:
		frappe.destroy()


commands = [fieldpro_demo, fieldpro_activate]
