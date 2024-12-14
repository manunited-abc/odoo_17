from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from email.policy import default
from tokenize import String

from Demos.mmapfile_demo import offset
import logging
from odoo import api, fields, models
import requests
import json

from odoo.addons.test_impex.models import field
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class MkAppConfig(models.Model):
    _name = 'mk.app_config'
    _description = 'App Configuration'

    name = fields.Char(string='Name', required=True)
    app_id = fields.Char(string='App Id', required=True)
    app_secret = fields.Char(string='App Secret', required=True)
    access_token = fields.Char(string='Access Token')
    refresh_token = fields.Char(string='Refresh Token')
    platform = fields.Selection([
        ('zalo', 'Zalo'),
    ], string='Platform', required=True)
    offset_sync = fields.Integer(String="Offset", default=0)
    count_sync = fields.Integer(String="Offset", default=50)

    @api.model
    def create(self, vals):
        # Logic to run before creating a record
        # Ví dụ: kiểm tra xem một bản ghi với cùng tên đã tồn tại chưa
        if 'name' in vals:
            existing_record = self.search([('name', '=', vals['name'])], limit=1)
            if existing_record:
                raise UserError("A record with this name already exists.")

        # Gọi phương thức create của lớp cha để thực hiện tạo bản ghi
        record = super(MkAppConfig, self).create(vals)

        # Logic bổ sung sau khi tạo bản ghi (nếu cần)
        # Ví dụ: ghi lại thông tin vào log hoặc tạo cấu hình mặc định
        # self.env['ir.config_parameter'].set_param('social_app.created_id', record.id)

        return record

    def write(self, vals):
        # Logic trước khi cập nhật bản ghi
        if 'app_id' in vals:
            # Ví dụ: kiểm tra giá trị app_id mới
            if not vals['app_id']:
                raise UserError("App Id cannot be empty.")

        # Gọi phương thức write của lớp cha
        result = super(MkAppConfig, self).write(vals)

        # Logic sau khi cập nhật bản ghi (nếu cần)
        return result

    def action_refresh_token(self):
        url = "https://oauth.zaloapp.com/v4/oa/access_token"
        headers = {
            'Content-Type': 'application/x-www-form-urlencoded',
            'secret_key': self.app_secret,  # Sử dụng secret key của bản ghi hiện tại
        }
        payload = {
            'refresh_token': self.refresh_token,
            'app_id': self.app_id,
            'grant_type': 'refresh_token',
        }

        try:
            response = requests.post(url, headers=headers, data=payload)
            response_data = response.json()

            if response.status_code == 200 and 'access_token' in response_data:
                # Lấy access_token và refresh_token mới
                new_access_token = response_data['access_token']
                new_refresh_token = response_data.get('refresh_token', self.refresh_token)

                # Cập nhật các trường access_token và refresh_token của bản ghi hiện tại
                self.write({
                    'access_token': new_access_token,
                    'refresh_token': new_refresh_token,
                })
                return {
                    'type': 'ir.actions.client',
                    'tag': 'reload',
                }
            else:
                error_message = response_data.get('message', 'Unknown error occurred')
                raise UserError(f"Failed to refresh token: {error_message}")
        except Exception as e:
            raise UserError(f"Failed to refresh token: {str(e)}")

    def refresh_token_auto(self):
        url = "https://oauth.zaloapp.com/v4/oa/access_token"
        app_config = self.env['mk.app_config'].sudo().search([('platform', '=', 'zalo')], limit=1)
        if app_config.exists():
            headers = {
                'Content-Type': 'application/x-www-form-urlencoded',
                'secret_key': app_config.app_secret,  # Sử dụng secret key của bản ghi hiện tại
            }
            payload = {
                'refresh_token': app_config.refresh_token,
                'app_id': app_config.app_id,
                'grant_type': 'refresh_token',
            }

            try:
                response = requests.post(url, headers=headers, data=payload)
                response_data = response.json()

                if response.status_code == 200 and 'access_token' in response_data:
                    # Lấy access_token và refresh_token mới
                    new_access_token = response_data['access_token']
                    new_refresh_token = response_data.get('refresh_token', app_config.refresh_token)

                    app_config.sudo().write({
                        'access_token': new_access_token,
                        'refresh_token': new_refresh_token,
                    })
                    print("Refresh token auto success")
                else:
                    error_message = response_data.get('message', 'Unknown error occurred')
                    print("Refresh token auto fail: " + error_message)
            except Exception as e:
                print("Refresh token auto fail: " + str(e))
        else:
            print("App Config not found")

    def sync_customer_zalo(self):
        app_config = self.env['mk.app_config'].sudo().search([('platform', '=', 'zalo')], limit=1)
        if not app_config:
            raise UserError("Zalo app config not found.")

        users = self._get_user_list(app_config)

        partner_data = []
        user_data_list = self._get_user_info_parallel(users, app_config)
        for user_data in user_data_list:
            if user_data and user_data.get('display_name'):
                partner_data.append({
                    'x_user_social_id': user_data.get('user_id'),
                    'x_source': 'zalo',
                    'name': user_data.get('display_name'),
                    'phone': user_data.get('phone') if user_data.get('phone') != 0 else '',
                    'x_is_follow': user_data.get('user_is_follower', False),
                    'x_last_interaction_date': datetime.strptime(user_data.get("last_interaction_date"), "%d/%m/%Y"),
                    'customer_rank': 1,
                })

        # Bulk create partners for better performance

        self.env['res.partner'].sudo().create(partner_data)
        # Update app_config offset
        app_config.sudo().write({'offset_sync': app_config.count_sync + app_config.offset_sync})

        sync_num = len(partner_data)
        return self._display_notification(f"Đã đồng bộ {sync_num} khách hàng từ Zalo.", "success")

    def _get_user_info(self, user_id, app_config):
        url = "https://openapi.zalo.me/v3.0/oa/user/detail"
        headers = {"access_token": app_config.access_token}
        params = {"data": json.dumps({"user_id": user_id})}

        response = self._send_request("GET", url, headers, params)
        if response:
            return response.get("data")
        return None

    def _get_user_info_parallel(self, user_ids, app_config):
        headers = {"access_token": app_config.access_token}
        url = "https://openapi.zalo.me/v3.0/oa/user/detail"

        def fetch_user(user_id):
            params = {"data": json.dumps({"user_id": user_id})}
            response = self._send_request("GET", url, headers, params)
            if response:
                user_data = response.get("data", {})
                return {
                    "user_id": user_data.get("user_id"),
                    "display_name": user_data.get("display_name"),
                    "user_alias": user_data.get("user_alias"),
                    "user_is_follower": user_data.get("user_is_follower"),
                    "last_interaction_date": user_data.get("user_last_interaction_date"),
                    "avatar": user_data.get("avatar"),
                    "address": user_data.get("shared_info", {}).get("address"),
                    "city": user_data.get("shared_info", {}).get("city"),
                    "district": user_data.get("shared_info", {}).get("district"),
                    "phone": user_data.get("shared_info", {}).get("phone"),
                }
            return None

        with ThreadPoolExecutor(max_workers=5) as executor:  # Adjust max_workers as needed
            user_data_list = list(executor.map(fetch_user, user_ids))

        return [user_data for user_data in user_data_list if user_data]

    def _get_user_list(self, app_config):
        url = "https://openapi.zalo.me/v3.0/oa/user/getlist"
        current_date = datetime.now().strftime("%Y_%m_%d")
        params = {
            "data": json.dumps({
                "offset": app_config.offset_sync,
                "count": app_config.count_sync,
                "is_follower": True,

            })
        }
        headers = {"access_token": app_config.access_token}

        response = self._send_request("GET", url, headers, params)
        if response and response.get("error") == 0:
            users = response.get("data", {}).get("users", [])
            return [user.get("user_id") for user in users if user.get("user_id")]
        else:
            _logger.warning(f"Failed to fetch user list: {response}")
            return []

    def _send_request(self, method, url, headers, params=None):
        try:
            response = requests.request(method, url, headers=headers, params=params, timeout=10)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            _logger.error(f"Request failed: {e}")
            return None

    def _display_notification(self, message, notif_type="info"):
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": "Thông báo",
                "message": message,
                "type": notif_type,
                "sticky": False,
            }
        }

    # Xử lý kết quả
