from odoo import api, SUPERUSER_ID


def post_init_hook(cr, registry):
    env = api.Environment(cr, SUPERUSER_ID, {})
    provider_model = env["payment.provider"].sudo()

    existing = provider_model.search([("code", "=", "wompi")], limit=1)
    if existing:
        return

    provider_model.create({
        "name": "Wompi",
        "code": "wompi",
        "state": "disabled",
    })
