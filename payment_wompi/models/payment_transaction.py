import logging
from datetime import timedelta, timezone

from odoo import _, models
from odoo.tools import float_round
from odoo.exceptions import ValidationError

_logger = logging.getLogger(__name__)

WOMPI_STATUS_MAPPING = {
    "APPROVED": "done",
    "DECLINED": "cancel",
    "ERROR": "error",
    "VOIDED": "cancel",
    "PENDING": "pending",
}


class PaymentTransaction(models.Model):
    _inherit = "payment.transaction"

    def _get_specific_rendering_values(self, processing_values):
        rendering_values = super()._get_specific_rendering_values(processing_values)
        if self.provider_code != "wompi":
            return rendering_values
        access_token = (
            processing_values.get("access_token")
            or processing_values.get("transaction_access_token")
            or rendering_values.get("access_token")
        )
        rendering_values.update({
            "reference": self.reference,
            "access_token": access_token,
        })
        return rendering_values

    def _wompi_get_amount_in_cents(self):
        self.ensure_one()
        precision = 10 ** self.currency_id.decimal_places
        return int(float_round(self.amount * precision, precision_digits=0))

    def _wompi_create_payment_link(self):
        self.ensure_one()

        if self.currency_id.name != "COP":
            raise ValidationError(_("Wompi payment links only support COP currency. Current currency: %s", self.currency_id.name))

        base_url = self.provider_id.get_base_url()
        expires_at = (
            (self.create_date.replace(tzinfo=timezone.utc) + timedelta(hours=12))
            .strftime("%Y-%m-%dT%H:%M:%S.000Z")
        )
        payload = {
            "name": self.reference,
            "description": self.reference,
            "currency": self.currency_id.name,
            "amount_in_cents": self._wompi_get_amount_in_cents(),
            "single_use": True,
            "redirect_url": f"{base_url}/payment/wompi/return?reference={self.reference}",
            "expires_at": expires_at,
        }

        response = self.provider_id._wompi_make_request("payment_links", method="POST", payload=payload)
        payment_link_data = response.get("data", {})
        permalink = payment_link_data.get("permalink")
        if not permalink:
            raise ValueError(_("Wompi did not return the payment link URL."))

        self.provider_reference = payment_link_data.get("id")
        return permalink

    @staticmethod
    def _wompi_get_status_from_notification(notification_data):
        data = notification_data.get("data", {})
        if "transaction" in data:
            return data.get("transaction", {}).get("status")
        return data.get("status")

    def _wompi_apply_status(self, notification_data):
        self.ensure_one()
        status = self._wompi_get_status_from_notification(notification_data)
        mapped_status = WOMPI_STATUS_MAPPING.get(status)

        if mapped_status == "done":
            self._set_done()
        elif mapped_status == "pending":
            self._set_pending()
        elif mapped_status == "cancel":
            self._set_canceled(state_message=_("Payment declined or canceled on Wompi."))
        else:
            self._set_error(
                _("Wompi marked this payment with an unexpected status: %s", status)
            )

    def _wompi_sync_status(self, transaction_id):
        self.ensure_one()
        if not transaction_id:
            return
        response = self.provider_id._wompi_make_request(f"transactions/{transaction_id}")
        self._wompi_apply_status(response)

    def _get_tx_from_notification_data(self, provider_code, notification_data):
        tx = super()._get_tx_from_notification_data(provider_code, notification_data)
        if provider_code != "wompi":
            return tx

        reference = (
            notification_data.get("reference")
            or notification_data.get("data", {}).get("transaction", {}).get("reference")
            or notification_data.get("data", {}).get("reference")
        )
        if not reference:
            raise ValueError("Wompi notification does not include a transaction reference.")

        tx = self.search([("reference", "=", reference), ("provider_code", "=", "wompi")], limit=1)
        if not tx:
            raise ValueError(f"No transaction found for Wompi reference {reference}")
        return tx

    def _process_notification_data(self, notification_data):
        super()._process_notification_data(notification_data)
        if self.provider_code != "wompi":
            return
        self._wompi_apply_status(notification_data)
        if self.state in ("done", "authorized"):
            _logger.info("Wompi payment completed for transaction %s", self.reference)
