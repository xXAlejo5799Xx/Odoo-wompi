import json
import logging

from odoo import http
from odoo.http import request

_logger = logging.getLogger(__name__)


class WompiController(http.Controller):
    _return_url = "/payment/wompi/return"
    _redirect_url = "/payment/wompi/redirect"
    _webhook_url = "/payment/wompi/webhook"

    @http.route(_redirect_url, type="http", auth="public", website=True, methods=["POST"], csrf=True)
    def wompi_redirect(self, reference=None, access_token=None, **kwargs):
        tx_sudo = request.env["payment.transaction"].sudo().search(
            [("reference", "=", reference), ("provider_code", "=", "wompi")],
            limit=1,
        )
        if not tx_sudo or not tx_sudo._check_access_token(access_token):
            return request.redirect("/payment/status")

        payment_url = tx_sudo._wompi_create_payment_link()
        return request.redirect(payment_url)

    @http.route(_return_url, type="http", auth="public", website=True, methods=["GET"], csrf=False)
    def wompi_return(self, reference=None, id=None, transaction_id=None, **kwargs):
        tx_sudo = request.env["payment.transaction"].sudo().search(
            [("reference", "=", reference), ("provider_code", "=", "wompi")],
            limit=1,
        )
        if not tx_sudo:
            return request.redirect("/payment/status")

        wompi_tx_id = transaction_id or id
        if wompi_tx_id:
            tx_sudo._wompi_sync_status(wompi_tx_id)

        return request.redirect("/payment/status")

    @http.route(_webhook_url, type="http", auth="public", methods=["POST"], csrf=False)
    def wompi_webhook(self, **kwargs):
        payload = json.loads(request.httprequest.data.decode("utf-8") or "{}")
        _logger.info("Wompi webhook received")

        tx_model = request.env["payment.transaction"].sudo()
        tx_sudo = tx_model._get_tx_from_notification_data("wompi", payload)
        tx_sudo._process_notification_data(payload)
        return request.make_response("OK")
