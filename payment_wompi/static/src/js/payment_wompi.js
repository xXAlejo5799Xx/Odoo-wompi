/** @odoo-module **/

import paymentForm from 'payment.payment_form';

paymentForm.include({
    _processRedirectPayment: function (providerCode, processingValues) {
        if (providerCode !== 'wompi') {
            return this._super.apply(this, arguments);
        }

        const params = new URLSearchParams({
            amount_in_cents: processingValues.amount_in_cents,
            currency: processingValues.currency,
            reference: processingValues.reference,
            redirect_url: processingValues.redirect_url,
            public_key: processingValues.public_key,
        });

        window.location.href = `https://checkout.wompi.co/p/?${params.toString()}`;
    },
});
