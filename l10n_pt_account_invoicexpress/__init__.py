# Copyright (C) 2021 Open Source Integrators
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from . import models


def post_init_hook(env):
    env["l10n_pt.invoice.provider.record"]._register_provider("invoicexpress")
