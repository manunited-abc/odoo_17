from odoo import models, fields

class ResPartner(models.Model):
    _inherit = 'res.partner'

    def sync_customer_zalo(self):
        print("Hello")
