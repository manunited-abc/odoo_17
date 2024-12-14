import base64
from email.policy import default

import requests

from odoo import models, fields, api
from odoo.exceptions import UserError
from odoo.tools.populate import compute


class MkMessageTemplate(models.Model):
    _name = 'mk.message_template'
    _description = 'Message Template'

    name = fields.Char(string='Name', required=True)
    description = fields.Text(string='Description')
    content = fields.Text(string='Content')
    template_id = fields.Char(string='Template Id')
    template_data = fields.Text(string='Template Data')
    platform = fields.Selection([
        ('zalo', 'Zalo'),
    ], string='Platform', required=True, default='zalo')
    message_template_type_id = fields.Many2one('mk.message_template_type', string='Type')
    image_url = fields.Char(string='Image URL')
    image_binary = fields.Binary(string='Image')
    attachment_id = fields.Char(string='Blog Id')
    from_age = fields.Integer(string='From Age', default=18)
    to_age = fields.Integer(string='To Age', default=64)
    ages = fields.Char(string='Ages', default='2,3,4,5,6', compute='_compute_ages', store=True)
    gender = fields.Selection([
        ('0', 'Tất cả giới tính'), ('1', 'Nam'), ('2', 'Nữ')
    ], string='Giới tính', default='0')
    content_html = fields.Html(string='Content HTML', compute="_compute_html_content", store=True)
    is_broadcast = fields.Boolean(string='Is Broadcast', compute='_compute_is_broadcast', store=True)

    @api.depends('content', 'image_url')
    def _compute_html_content(self):
        for record in self:
            if record.content and (
                    record.message_template_type_id.code == 'CONSULTANT' or record.message_template_type_id.code == 'SHARE_INFO'):
                record.content_html = f'''
                            <div style="width:60%">
                                <img src="{record.image_url}" alt="Avatar" style="width:100%">
                                <div style="padding: 2px 16px">
                                 <p>{record.content}</p>
                                </div>
                            </div>
                            '''
            else:
                record.content_html = ''

    @api.depends('from_age', 'to_age')
    def _compute_ages(self):
        # Bảng quy ước index theo khoảng tuổi
        age_groups = [
            (0, 12),  # Index 0
            (13, 17),  # Index 1
            (18, 24),  # Index 2
            (25, 34),  # Index 3
            (35, 44),  # Index 4
            (45, 54),  # Index 5
            (55, 64),  # Index 6
            (65, float('inf'))  # Index 7 (tuổi >= 65)
        ]

        for record in self:
            indexes = []
            from_age = record.from_age
            to_age = record.to_age

            # Tính toán các index dựa trên khoảng tuổi
            for index, (start, end) in enumerate(age_groups):
                if from_age <= end and to_age >= start:
                    indexes.append(index)

            # Chuyển danh sách index thành chuỗi và gán giá trị
            record.ages = ",".join(map(str, indexes))

    @api.onchange('to_age')
    def _onchange_to_age(self):
        if self.to_age < 0 or self.from_age > self.to_age:
            self.to_age = 18
            return {
                'warning': {
                    'title': "Cảnh báo",
                    'message': "Tuổi không hợp",
                }
            }

    @api.onchange('from_age')
    def _onchange_from_age(self):
        if self.from_age < 0 or self.from_age > self.to_age:
            self.from_age = 64
            return {
                'warning': {
                    'title': "Cảnh báo",
                    'message': "Tuổi không hợp",
                }
            }

    @api.depends('message_template_type_id')
    def _compute_is_broadcast(self):
        for record in self:
            record.is_broadcast = record.message_template_type_id.code == 'BROADCAST'

    @api.depends('message_template_type_id')
    def _compute_message_template_type_code(self):
        for record in self:
            if record.message_template_type_id:
                record.message_template_type_code = record.message_template_type_id.code
            else:
                record.message_template_type_code = ''


class MkMessageTemplateType(models.Model):
    _name = 'mk.message_template_type'
    _description = 'Message Template Type'

    name = fields.Char(string='Name', required=True)
    code = fields.Char(string='Code', required=True)
    message_template_ids = fields.One2many('mk.message_template', 'message_template_type_id', string='Templates')
