# Copyright (C) 2026 Daniel Reis
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl).


def post_init_hook(env):
    """Load the bundled IRS withholding tables shipped under data/irs/."""
    from .wizard.hr_pt_irs_withholding_import import (
        HrPtIrsWithholdingImport,
    )

    HrPtIrsWithholdingImport.load_bundled(env)


from . import models  # noqa: E402
from . import wizard  # noqa: E402
