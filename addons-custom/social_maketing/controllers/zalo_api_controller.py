import logging
from datetime import datetime

from odoo import http
from odoo.http import request
import json
import requests

_logger = logging.getLogger(__name__)


class ZaloApiController(http.Controller):
    @http.route('/api/social_marketing/test', type='http', auth='user', methods=['GET'], csrf=False)
    def test(self):
        mk_app_config = request.env['mk.app_config']
        record = mk_app_config.search([('platform', '=', 'zalo')], limit=1)
        if record.exists():
            access_token = record.access_token

        print(f"Access token: {access_token}")
        response_data = {
            'message': 'Hello world'
        }
        return http.Response(json.dumps(response_data), content_type='application/json')

    @http.route('/api/social_marketing/webhook/zalo', type='json', auth='public', methods=['POST'])
    def receive_webhook(self, **kwargs):
        # Nhận dữ liệu từ yêu cầu webhook
        data = request.httprequest.get_json()
        event_name = data.get("event_name")
        user_id = data.get("follower", {}).get("id")
        timestamp = int(data.get('timestamp'))
        customer = request.env['res.partner']

        # Hàm dùng chung để xử lý cập nhật hoặc tạo khách hàng
        def create_or_update_customer(user_id, name, phone=None, is_follow=None):
            record = customer.sudo().search([('x_user_social_id', 'like', user_id)], limit=1)
            customer_data = {
                'x_user_social_id': str(user_id),
                'x_source': 'zalo',
                'x_last_interaction_date': datetime.fromtimestamp(timestamp / 1000),
                'customer_rank': 1,
            }

            # Thêm các thông tin riêng biệt theo từng sự kiện
            if name:
                customer_data['name'] = name
            if phone:
                customer_data['phone'] = phone
            if is_follow is not None:
                customer_data['x_is_follow'] = is_follow

            if record.exists():
                record.sudo().write(customer_data)
            else:
                customer.sudo().create(customer_data)

        # Xử lý theo từng sự kiện
        if event_name == "follow":
            user_info = self.get_user_info(user_id)
            name = user_info.get('data', {}).get('display_name')
            is_follow = user_info.get('data', {}).get('user_is_follower')
            create_or_update_customer(user_id, name, is_follow=is_follow)

        elif event_name == "user_submit_info":
            info = data.get('info', {})
            user_id = data.get('recipient', {}).get('id')
            create_or_update_customer(user_id, info.get('name'), info.get('phone'))

        elif event_name == "user_send_text":
            user_id = data.get('sender', {}).get('id')
            app_config = request.env['mk.app_config'].sudo().search([('platform', '=', 'zalo')], limit=1)
            user = self._get_user_info(user_id, app_config)
            name = ''
            phone = ''
            is_follower = False
            if user:
                name = user.get("display_name") if user.get("display_name") else f'Khách hàng zalo - {user_id}'
                phone = user.get('phone') if user.get('phone') != 0 else ''
                is_follower = user.get('user_is_follower', False)
            create_or_update_customer(user_id,
                                      name,phone,is_follower)  # Cập nhật thời gian tương tác mà không thay đổi tên hoặc số điện thoại

        # Trả về phản hồi cho Zalo
        return {"status": "success"}

    def _get_user_info(self, user_id, app_config):
        url = "https://openapi.zalo.me/v3.0/oa/user/detail"
        headers = {"access_token": app_config.access_token}
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

    def _send_request(self, method, url, headers, params=None):
        try:
            response = requests.request(method, url, headers=headers, params=params, timeout=10)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            _logger.error(f"Request failed: {e}")
            return None
