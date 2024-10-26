from email.policy import default

from odoo import models, fields


class Player (models.Model):
    _name = 'player'
    _description =  'Player'

    name = fields.Char(string='Name',required=True)
    image = fields.Binary(string='Image',attachment=True)
    country = fields.Char(string='Country')
    gender = fields.Selection([('male','Male'), ('female','Female')], string='Gender',default='male')
    date_of_birth = fields.Datetime(string='Date of Birth')
    position = fields.Char(string='Position')
    height = fields.Float(string='Height')
    weight = fields.Float(string='Weight')