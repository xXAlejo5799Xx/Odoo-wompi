def post_init_hook(env):
    provider_model = env["payment.provider"].sudo()

    existing = provider_model.search([("code", "=", "wompi")], limit=1)
    if existing:
        return

    provider_model.create({
        "name": "Wompi",
        "code": "wompi",
        "state": "disabled",
    })
