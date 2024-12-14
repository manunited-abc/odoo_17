from datetime import datetime, timedelta
import requests
import json
from odoo import models, fields, api
from odoo.exceptions import UserError
from odoo.http import request


class MkCampaign(models.Model):
    _name = 'mk.campaign'  # Tên model trong cơ sở dữ liệu
    _description = 'Marketing Campaign'  # Mô tả của model

    name = fields.Char(string='Campaign Name', required=True)
    description = fields.Text(string='Description')
    start_date = fields.Datetime(string='Start Date', required=True)
    end_date = fields.Datetime(string='End Date')
    budget = fields.Float(string='Budget')
    is_active = fields.Boolean(string='Active', default=False)
    cron_job_id = fields.Many2one('ir.cron', string="Cron Job")
    message_template_id = fields.Many2one('mk.message_template', string='Message Template')
    content_html = fields.Html(string='Content', compute='_compute_content')
    platform = fields.Selection([
        ('zalo', 'Zalo')
    ], string='Platform', required=False, default='zalo')
    is_broadcast = fields.Boolean(string='Is Broadcast', compute='_compute_is_broadcast', store=True)

    @api.depends('message_template_id')
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

    @api.depends('message_template_id')
    def _compute_is_broadcast(self):
        for record in self:
            record.is_broadcast = record.message_template_id.message_template_type_id.code == 'BROADCAST'

    @api.model
    def create(self, vals):
        """Override create để tạo ir.cron khi tạo chiến dịch"""
        campaign = super(MkCampaign, self).create(vals)

        # Tạo ir.cron nếu có chiến dịch được tạo
        if campaign.start_date and campaign.is_active:
            cron_values = {
                'name': f"Chiến dịch {campaign.name} - Gửi tin nhắn",
                'model_id': self.env['ir.model'].search([('model', '=', 'mk.campaign')], limit=1).id,
                # Chỉ định model tương ứng, có thể thay đổi nếu cần
                'state': 'code',  # Chạy theo code
                'user_id': self.env.user.id,  # Người dùng thực hiện tác vụ này
                'interval_number': 5,  # Tần suất (ví dụ: 1 phút, 1 giờ,...)
                'interval_type': 'minutes',  # Kiểu tần suất (minutes, hours, days,...)
                'nextcall': campaign.start_date,  # Thời gian bắt đầu
                'code': f"model.send_campaign_message({campaign.id})",
                'numbercall': 1
                # Code chạy (cần có method send_campaign_message)
            }

            cron_job = self.env['ir.cron'].create(cron_values)
            campaign.cron_job_id = cron_job.id  # Gắn cron job với chiến dịch

        return campaign

    @api.onchange('start_date')
    def _onchange_start_date(self):
        """Kiểm tra ngày bắt đầu"""
        if self.start_date and self.start_date < fields.Datetime.now():
            self.is_active = False
            return {
                'warning': {
                    'title': "Cảnh báo",
                    'message': "Ngày bắt đầu không thể nhỏ hơn ngày hiện tại. Chiến dịch đã được vô hiệu hóa.",
                }
            }
        else:
            # Nếu ngày bắt đầu hợp lệ, cập nhật lại cron job
            if self.cron_job_id:
                self.cron_job_id.write({
                    'nextcall': self.start_date,
                    'numbercall': 1,
                    'active': self.is_active  # Bật cron job nếu ngày bắt đầu hợp lệ
                })
            else:
                print("Schedule action not found")

    @api.onchange('is_active')
    def _onchange_is_active(self):
        """Kiểm tra điều kiện khi bật is_active"""
        if self.is_active and self.start_date:
            current_time = fields.Datetime.now()
            if self.start_date < current_time:
                self.is_active = False  # Tắt lại is_active
                return {
                    'warning': {
                        'title': "Cảnh báo",
                        'message': "Ngày bắt đầu không được nhỏ hơn thời gian hiện tại. Vui lòng chọn ngày hợp lệ.",
                    }
                }
            else:
                if self.cron_job_id:
                    self.cron_job_id.write({
                        'nextcall': self.start_date,
                        'numbercall': 1,
                        'active': True  # Bật cron job nếu ngày bắt đầu hợp lệ
                    })
        else:
            if self.cron_job_id:
                self.cron_job_id.write({
                    'active': False
                })

    def send_campaign_message(self, campaign_id):
        # Lấy cấu hình app
        app_config = self.env['mk.app_config'].sudo().search([('platform', '=', 'zalo')], limit=1)
        if not app_config:
            raise UserError("Zalo app config not found.")

        # Lấy chiến dịch
        campaign = self.env['mk.campaign'].browse(campaign_id)
        # URL cho từng loại tin nhắn
        url_consultant = "https://openapi.zalo.me/v3.0/oa/message/cs"
        url_media = "https://openapi.zalo.me/v3.0/oa/message/promotion"
        url_broadcast = "https://openapi.zalo.me/v2.0/oa/message"

        # Lấy danh sách khách hàng
        customers = self.env['res.partner'].sudo().search(
            [("x_user_social_id", '!=', False), ('x_source', '=', 'zalo')])

        dict_message_send_count = {}

        # Tạo headers chung
        headers = {
            'access_token': app_config.access_token,
            'Content-Type': 'application/json'
        }
        data = {}

        def send_message(url, headers, data):
            response = requests.post(url, headers=headers, data=json.dumps(data))
            if response.status_code != 200:
                print("Error when sending message.")
            else:
                response_data = json.loads(response.text)
                if response_data.get('error'):
                    print(response_data.get('message'))
                else:
                    print(response_data.get('message'))
                    return True
            return False

        if campaign.message_template_id.message_template_type_id.code != 'BROADCAST':
            # Hàm gửi tin nhắn
            for customer in customers:
                if not customer.x_user_social_id:
                    continue

                # Chuẩn bị dữ liệu tin nhắn
                if campaign.message_template_id.message_template_type_id.code == 'MEDIA':
                    url = url_media
                    data = {
                        "recipient": {
                            "user_id": customer.x_user_social_id
                        },
                        "message": json.loads(campaign.message_template_id.content)
                    }
                elif campaign.message_template_id.message_template_type_id.code == 'SHARE_INFO':
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
                                        "subtitle": campaign.message_template_id.content,
                                        "image_url": campaign.message_template_id.image_url
                                    }]
                                }
                            }
                        }
                    }
                    # Chỉ gửi tin nhắn nếu khoảng cách ngày < 7
                    delta = customer.x_last_interaction_date - datetime.now()
                    if delta.days < 7:
                        if send_message(url, headers, data):
                            dict_message_send_count[customer.id] = dict_message_send_count.get(customer.id, 0) + 1
                else:
                    if send_message(url, headers, data):
                        dict_message_send_count[customer.id] = dict_message_send_count.get(customer.id, 0) + 1

            # Cập nhật số lần gửi tin nhắn trong cơ sở dữ liệu
            if dict_message_send_count:
                data = [(customer_id, message_count) for customer_id, message_count in dict_message_send_count.items()]
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
        else:
            data = {
                "recipient": {
                    "target": {
                        "gender": campaign.message_template_id.gender,
                        "cities": "18"
                    }
                },
                "message": {
                    "attachment": {
                        "type": "template",
                        "payload": {
                            "template_type": "media",
                            "elements": [
                                {
                                    "media_type": "article",
                                    "attachment_id": campaign.message_template_id.attachment_id
                                }
                            ]
                        }
                    }
                }
            }
            send_message(url_broadcast, headers, data)
        # Vô hiệu hóa chiến dịch sau khi gửi tin nhắn
        if campaign.exists():
            campaign.sudo().write({
                'is_active': False
            })

        length = len(dict_message_send_count)
        print(f"Send message auto to {length} customer successfully")
