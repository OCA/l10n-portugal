(function () {
    "use strict";

    var checkoutEl = document.getElementById("easypay-checkout");
    var data = null;
    try {
        data =
            checkoutEl && checkoutEl.dataset.easypay
                ? JSON.parse(checkoutEl.dataset.easypay)
                : null;
    } catch {
        data = null;
    }
    var loadingEl = document.getElementById("payment-loading");
    var containerEl = document.getElementById("easypay-checkout-container");
    var errorEl = document.getElementById("payment-error");

    if (loadingEl) loadingEl.style.display = "none";

    if (!data || !window.easypayCheckout) {
        // SDK failed to load (onerror already showed error div) or missing data
        if (!data && errorEl) errorEl.style.display = "block";
        return;
    }

    if (containerEl) containerEl.style.display = "block";

    var sessionId = data.sessionId;
    var isTestMode = !data.apiUrl || data.apiUrl.includes("test");

    // SDK callbacks are browser-side notifications only: they POST back the
    // opaque session id plus the CSRF token rendered with the page. No SDK
    // field is ever used as payment evidence.
    function submitCallback(path) {
        var form = document.createElement("form");
        form.method = "POST";
        form.action = path;
        Object.entries({
            csrf_token: data.csrfToken,
            session_id: sessionId,
        }).forEach(function ([name, value]) {
            var input = document.createElement("input");
            input.type = "hidden";
            input.name = name;
            input.value = value;
            form.appendChild(input);
        });
        document.body.appendChild(form);
        form.submit();
    }

    var successHandled = false;
    var checkoutInstance = window.easypayCheckout.startCheckout(data.manifest, {
        display: "inline",
        testing: isTestMode,
        language: data.language || undefined,
        hideDetails: data.hideDetails || false,
        onSuccess: function () {
            successHandled = true;
            checkoutInstance.unmount();
            submitCallback("/payment/easypay/checkout/success");
        },
        onError: function (error) {
            checkoutInstance.unmount();
            switch (error.code) {
                case "checkout-expired":
                    // Session expired - go back so user can restart and a new session is created
                    window.history.back();
                    break;
                case "already-paid":
                    window.location.href = "/payment/status";
                    break;
                case "checkout-canceled":
                    submitCallback("/payment/easypay/checkout/cancel");
                    break;
                default:
                    if (errorEl) {
                        errorEl.querySelector("p").textContent =
                            "Payment error: " + (error.message || "Unknown error");
                        errorEl.style.display = "block";
                    }
                    if (containerEl) containerEl.style.display = "none";
            }
        },
        onPaymentError: function () {
            // Recoverable error - SDK keeps form open, user can retry
        },
        onClose: function () {
            checkoutInstance.unmount();
            if (!successHandled) {
                window.location.href = "/payment/status";
            }
        },
    });
})();
