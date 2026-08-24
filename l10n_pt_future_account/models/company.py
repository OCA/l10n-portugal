from odoo import models
from odoo.addons.account.models.account_move import MAX_HASH_VERSION


class ResCompany(models.Model):
    _name = "res.company"
    _inherit = ["res.company", "mail.thread"]

    def _get_hash_versioning_list(self):
        return list(range(1, MAX_HASH_VERSION + 1))

    def _verify_hashed_move(self, move, previous_hash, versioning_list, current_versioning_index):
        computed_hash = move.with_context(hash_version=versioning_list[current_versioning_index])._calculate_hashes(previous_hash)[move]
        while move.inalterable_hash != computed_hash and versioning_list[current_versioning_index] < len(versioning_list):
            current_versioning_index += 1
            computed_hash = move.with_context(hash_version=versioning_list[current_versioning_index])._calculate_hashes(previous_hash)[move]
        return move.inalterable_hash == computed_hash, current_versioning_index
