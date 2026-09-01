/* eslint-disable jsdoc/check-tag-names, sort-imports */
/* global window, console, URLSearchParams */
/** @odoo-module **/

import {_t} from "@web/core/l10n/translation";
import {rpc} from "@web/core/network/rpc";
import paymentForm from "@payment/js/payment_form";

paymentForm.include({
    async _processRedirectFlow(
        providerCode,
        paymentOptionId,
        paymentMethodCode,
        processingValues
    ) {
        if (providerCode !== "easypay") {
            return await this._super(...arguments);
        }

        try {
            // Create checkout session now (when user actually pays) using JSON-RPC
            const response_data = await rpc(
                "/payment/easypay/create_checkout_session",
                {
                    reference: processingValues.reference,
                }
            );

            if (!response_data || response_data.error) {
                const msg =
                    response_data?.message ||
                    _t("Failed to create payment session. Please try again.");
                this._displayErrorDialog(_t("Payment Error"), msg);
                this._enableButton();
                return;
            }

            // Redirect to dedicated payment page with session data
            const params = new URLSearchParams({
                session_id: response_data.checkout_id,
                manifest: JSON.stringify(response_data.checkout_manifest),
            });
            window.location.href = "/payment/easypay/checkout?" + params.toString();
        } catch (error) {
            console.error("EasyPay: Failed to create checkout session", error);
            this._displayErrorDialog(
                _t("Payment Error"),
                _t("Failed to create payment session. Please try again.")
            );
            this._enableButton();
        }
    },
});
