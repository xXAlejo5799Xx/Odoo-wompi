def post_init_hook(env):
    provider_model = env["payment.provider"].sudo()

    existing = provider_model.search([("code", "=", "wompi")], limit=1)
    provider = existing or provider_model.create({
        "name": "Wompi",
        "code": "wompi",
        "state": "disabled",
    })
    provider._wompi_ensure_payment_method_lines()
