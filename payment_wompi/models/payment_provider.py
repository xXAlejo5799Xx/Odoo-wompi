import logging

import requests

from odoo import _, fields, models
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

    def _wompi_make_request(self, endpoint, method="GET", payload=None):
        self.ensure_one()
        if not self.wompi_private_key:
            raise ValidationError(_("Configure the Wompi private key first."))

        url = f"{self._wompi_get_api_base().rstrip('/')}/{endpoint.lstrip('/')}"
        headers = {
            "Authorization": f"Bearer {self.wompi_private_key}",
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
        except requests.exceptions.RequestException as error:
            _logger.exception("Wompi request failed for %s", url)
            raise ValidationError(
                _("Could not connect with Wompi. Technical details: %s", error)
            ) from error

        response_data = response.json()
        if response_data.get("error"):
            raise ValidationError(
                _("Wompi returned an error: %s", response_data["error"])
            )
        return response_data
