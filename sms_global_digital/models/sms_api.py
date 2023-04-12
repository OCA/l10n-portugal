import json
import logging

import requests

from odoo import _, api, models
from odoo.exceptions import UserError, ValidationError

_logger = logging.getLogger(__name__)

GLOBAL_DIGITAL_ENDPOINT = "https://www.globaldigital.pt/api/sms/send.php?token="


class SmsApi(models.AbstractModel):
    _inherit = "sms.api"

    def _prepare_global_digital_params(self, account, number, message):
        if not number:
            raise ValidationError(_("Please enter a phone number!"))
        return {
            "sender": account.sms_global_digital_sender_id,
            "phone_numbers": number[1:] if number[0] == "+" else number,
            "message": message,
        }

    def _get_sms_account(self):
        return self.env["iap.account"].get("sms")

    def _send_sms_with_global_digital(self, number, message):
        error_msg = ""

        try:
            # Try to return same error code like odoo
            # list is here: self.IAP_TO_SMS_
            account = self._get_sms_account()
            # validate_phone_number(number)
            r = requests.post(
                GLOBAL_DIGITAL_ENDPOINT
                + self.env["iap.account"].get("sms").sms_global_digital_api_key
                + "&action=simple",
                data=self._prepare_global_digital_params(account, number, message),
                headers={"User-Agent": "some-user-agent"},
            )
            if r.status_code == 400:
                raise ValidationError(
                    _("Message not sent, please enter a valid number!")
                )

            r.raise_for_status()
        except requests.exceptions.Timeout:
            error_msg = "Timeout"
        except requests.exceptions.TooManyRedirects:
            error_msg = "Too many redirects"
        except requests.exceptions.HTTPError as e:
            error_msg = str(e)
        except requests.exceptions.RequestException as e:
            error_msg = str(e)
        except json.decoder.JSONDecodeError as e:
            error_msg = str(e)

        if error_msg:
            _logger.info(error_msg)
            return "server_error"
        return "success"

    def _is_sent_with_global_digital(self):
        return self._get_sms_account().provider == "sms_global_digital"

    @api.model
    def _send_sms(self, numbers, message):
        if self._is_sent_with_global_digital():
            # This method seem to be deprecated (no odoo code uses it).
            # As Global Digital doesn't support it we also don't
            # Note: if you want to implement it, be advised: just looping
            # on the list of numbers is not the right way to do it.
            # If you have an error, you will send and send again the same
            # message
            raise NotImplementedError
        else:
            return super()._send_sms(numbers, message)

    @api.model
    def _send_sms_batch(self, messages):
        if self._is_sent_with_global_digital():
            if len(messages) != 1:
                # we already have inherited the split_batch method on sms.sms
                # so this case should not append
                raise UserError(_("Batch sending is not support with Global Digital"))
            state = self._send_sms_with_global_digital(
                messages[0]["number"], messages[0]["content"], messages[0]["res_id"]
            )
            return [{"state": state, "credit": 0, "res_id": messages[0]["res_id"]}]
        else:
            return super()._send_sms_batch(messages)
