import logging

import requests

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError

_logger = logging.getLogger(__name__)


class PaymentProvider(models.Model):
    _inherit = "payment.provider"

    code = fields.Selection(
        selection_add=[("wompi", "Wompi")],
        ondelete={"wompi": "set default"},
    )
    wompi_public_key = fields.Char(
        string="Wompi Public Key",
        groups="base.group_system",
    )
    wompi_private_key = fields.Char(
        string="Wompi Private Key",
        groups="base.group_system",
    )
    wompi_sandbox = fields.Boolean(
        string="Use Sandbox",
        default=True,
        help="If enabled, the provider uses Wompi's sandbox API.",
    )

    def _wompi_ensure_payment_method_lines(self):
        method_line_model = self.env.get("payment.method.line")
        if not method_line_model:
            return

        payment_method_model = self.env["payment.method"].sudo()
        method_line_model = method_line_model.sudo()
        for provider in self.filtered(lambda p: p.code == "wompi"):
            method_codes = provider._get_default_payment_method_codes()
            payment_methods = payment_method_model.search([("code", "in", method_codes)])
            for payment_method in payment_methods:
                existing_line = method_line_model.search(
                    [
                        ("provider_id", "=", provider.id),
                        ("payment_method_id", "=", payment_method.id),
                    ],
                    limit=1,
                )
                if not existing_line:
                    method_line_model.create(
                        {
                            "provider_id": provider.id,
                            "payment_method_id": payment_method.id,
                        }
                    )

    @api.model_create_multi
    def create(self, vals_list):
        providers = super().create(vals_list)
        providers._wompi_ensure_payment_method_lines()
        return providers

    def write(self, vals):
        result = super().write(vals)
        self._wompi_ensure_payment_method_lines()
        return result

    def _get_default_payment_method_codes(self):
        default_codes = super()._get_default_payment_method_codes()
        if self.code != "wompi":
            return default_codes
        return ["card"]

    def _get_redirect_form_view(self, is_validation=False):
        res = super()._get_redirect_form_view(is_validation=is_validation)
        if self.code != "wompi":
            return res
        return self.env.ref("payment_wompi.redirect_form")

    def _wompi_get_api_base(self):
        self.ensure_one()
        if self.wompi_sandbox:
            return "https://sandbox.wompi.co/v1"
        return "https://production.wompi.co/v1"

    @staticmethod
    def _wompi_normalize_token(token):
        token = (token or "").strip()
        if token.lower().startswith("bearer "):
            token = token.split(" ", 1)[1].strip()
        return token

    def _wompi_get_auth_tokens(self):
        self.ensure_one()
        primary_token = self._wompi_normalize_token(self.wompi_private_key)
        secondary_token = self._wompi_normalize_token(self.wompi_public_key)

        tokens = []
        if primary_token:
            tokens.append(("private", primary_token))
        if secondary_token and secondary_token != primary_token:
            tokens.append(("public", secondary_token))

        if not tokens:
            raise ValidationError(_("Configure at least one Wompi API key (private/public)."))
        return tokens

    def _wompi_make_request(self, endpoint, method="GET", payload=None):
        self.ensure_one()
        url = f"{self._wompi_get_api_base().rstrip('/')}/{endpoint.lstrip('/')}"
        response = None
        last_error = None

        for token_type, token in self._wompi_get_auth_tokens():
            headers = {
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
            }
            try:
                response = requests.request(
                    method=method,
                    url=url,
                    headers=headers,
                    json=payload,
                    timeout=20,
                )
                response.raise_for_status()
                break
            except requests.exceptions.HTTPError as error:
                last_error = error
                status_code = error.response.status_code if error.response else None
                _logger.warning("Wompi request failed with %s key for %s", token_type, url)
                if status_code == 401:
                    continue
                raise ValidationError(
                    _("Could not connect with Wompi. Technical details: %s", error)
                ) from error
            except requests.exceptions.RequestException as error:
                _logger.exception("Wompi request failed for %s", url)
                raise ValidationError(
                    _("Could not connect with Wompi. Technical details: %s", error)
                ) from error
        else:
            env_name = _("sandbox") if self.wompi_sandbox else _("production")
            raise ValidationError(
                _(
                    "Wompi rejected credentials (401 Unauthorized). Verify your API keys and selected environment (%s). You can place either private or public key fields and the module will try both.",
                    env_name,
                )
            ) from last_error


        response_data = response.json()
        if response_data.get("error"):
            raise ValidationError(
                _("Wompi returned an error: %s", response_data["error"])
            )
        return response_data
