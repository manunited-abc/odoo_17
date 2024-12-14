import requests
import json
from odoo import models, fields, api
from odoo.exceptions import UserError
from odoo.tools.populate import compute
from odoo.http import request


class SendMessagesSocial(models.TransientModel):
    _name = 'send.message.social'
    _description = 'Send Message Social'

    use_template = fields.Boolean(string='Use Template')
    message_template_id = fields.Many2one('mk.message_template', string='Message Template')
    content = fields.Text(string='Content')
    content_html = fields.Html(string='Content', compute='_compute_content')
    platform = fields.Selection([
        ('zalo', 'Zalo'),
        ('facebook', 'Facebook'),
    ], string='Platform', required=False, default='zalo')

    @api.depends('message_template_id', 'use_template')
    def _compute_content(self):
        for record in self:
            if record.message_template_id:
                if record.message_template_id.message_template_type_id.code == 'CONSULTANT':
                    domain = request.env['ir.config_parameter'].sudo().get_param('web.base.url')
                    url_register = domain + '/register-member'
                    full_content = record.message_template_id.content_html.format(url=url_register)
                    record.content_html = full_content
                elif record.message_template_id.message_template_type_id.code == 'SHARE_INFO':
                    record.content_html = record.message_template_id.content_html
                else:
                    record.content_html = record.message_template_id.content
            else:
                record.content_html = ''

    def send_zalo_message(self):
        # if self.use_template:
        #     if not self.content_html:
        #         raise UserError("Content is required.")
        # else:
        #     if not self.content:
        #         raise UserError("Content is required.")

        # Logic to send
        selected_customer_ids = self.env.context.get('active_ids', [])
        if not selected_customer_ids:
            raise UserError("No customer selected.")
        # Get app config
        app_config = self.env['mk.app_config'].sudo().search([('platform', '=', 'zalo')], limit=1)
        if not app_config.exists():
            raise UserError("Zalo app config not found.")

        # send message
        # Get customers by ids
        customers = self.env['res.partner'].sudo().search([('id', 'in', selected_customer_ids)])
        # build url
        domain = request.env['ir.config_parameter'].sudo().get_param('web.base.url')
        url_consultant = "https://openapi.zalo.me/v3.0/oa/message/cs"
        url_media = "https://openapi.zalo.me/v3.0/oa/message/promotion"

        dict_message_send_count = {}
        for customer_id in selected_customer_ids:
            customer = customers.filtered(lambda x: x.id == customer_id)
            if customer.x_user_social_id:
                headers = {
                    'access_token': app_config.access_token,
                    'Content-Type': 'application/json'
                }
                url_register = domain + '/register-member?user_id=' + customer.x_user_social_id
                if self.message_template_id:
                    if self.message_template_id.message_template_type_id.code == 'CONSULTANT':
                        url = url_consultant
                        data = {
                            "recipient": {
                                "user_id": customer.x_user_social_id
                            },
                            "message": {
                                "text": self.message_template_id.content.format(url=url_register),
                                "attachment": {
                                    "type": "template",
                                    "payload": {
                                        "template_type": "media",
                                        "elements": [{
                                            "media_type": "image",
                                            "url": self.message_template_id.image_url
                                        }]
                                    }
                                }
                            }
                        }
                    elif self.message_template_id.message_template_type_id.code == 'MEDIA':
                        url = url_media
                        data = {
                            "recipient": {
                                "user_id": customer.x_user_social_id
                            },
                            "message": json.loads(self.message_template_id.content)
                        }
                    elif self.message_template_id.message_template_type_id.code == 'SHARE_INFO':
                        url = url_consultant
                        data = {
                            "recipient": {
                                "user_id": customer.x_user_social_id
                            },
                            "message": {
                                "attachment": {
                                    "type": "template",
                                    "payload": {
                                        "template_type": "request_user_info",
                                        "elements": [{
                                            "title": "Yêu cầu chia sẽ thông tin",
                                            "subtitle": self.message_template_id.content,
                                            "image_url": self.message_template_id.image_url
                                        }]
                                    }
                                }
                            }
                        }

                else:
                    url = url_consultant
                    data = {
                        "recipient": {
                            "user_id": customer.x_user_social_id
                        },
                        "message": {
                            "text": self.content
                        }
                    }

                response = requests.post(url, headers=headers, data=json.dumps(data))
                if response.status_code != 200:
                    raise UserError("Error when sending message.")
                # Get error
                response_data = json.loads(response.text)
                if response_data.get('error'):
                    raise UserError(response_data.get('message'))

                dict_message_send_count[customer_id] = dict_message_send_count.get(customer_id,
                                                                                   0) + 1
        # Update message send count
        if dict_message_send_count:
            data = [(customer_id, message_count) for customer_id, message_count in dict_message_send_count.items()]
            print(data)
            query = """
                UPDATE res_partner
                SET 
                    x_count_send = COALESCE(x_count_send, 0) + data_table.message_count,
                    x_last_send_message = NOW()
                FROM (VALUES %s) AS data_table (id, message_count)
                WHERE res_partner.id = data_table.id
            """
            values = ','.join(['(%s, %s)' % (d[0], d[1]) for d in data])
            final_query = query % values
            self.env.cr.execute(final_query)
            self.env.cr.flush()
            # for customer_id, _ in data:
            #     partner = self.env['res.partner'].browse(customer_id)
            #     if partner.exists():
            #         partner.clear_caches()
            data = []
        pass

    def get_user_list(self):
        url = "https://openapi.zalo.me/v3.0/oa/user/getlist"

        # Dữ liệu tham số
        data = {
            "offset": 0,
            "count": 10,
            "last_interaction_period": "2023_11_17:2024_11_17",
        }
        # Get app config
        app_config = self.env['mk.app_config'].sudo().search([('platform', '=', 'zalo')], limit=1)
        if not app_config.exists():
            raise UserError("Zalo app config not found.")
        # Thêm access_token của bạn
        access_token = app_config.access_token

        # Header
        headers = {
            "access_token": access_token
        }

        # Gửi yêu cầu GET
        response = requests.get(url, params={"data": json.dumps(data)}, headers=headers)
        if response.status_code == 200:
            response_data = response.json()
            users = response_data.get("data", {}).get("users", [])

            if users:
                for user in users:
                    print(f"User ID: {user.get('user_id')}")
                    print("---")
            else:
                print("Không có user nào được trả về.")
        else:
            print(f"Error {response.status_code}: {response.text}")
        # Xử lý kết quả
        pass
