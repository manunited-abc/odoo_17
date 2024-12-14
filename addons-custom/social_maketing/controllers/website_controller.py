from odoo import http
from odoo.http import request


class WebsiteRegister(http.Controller):
    @http.route(['/register-member'], type='http', auth='public', website=True)
    def registration_form(self, **kwargs):
        user_id = kwargs.get('user_id')
        return request.render('social_maketing.registration_form_template', {'user_id': user_id})

    @http.route('/thank-you', type='http', auth='public', website=True)
    def thank_you_page(self, **kwargs):
        return request.render('social_maketing.thank_you')

    @http.route('/register/submit', type='http', auth='public', website=True, csrf=False, methods=['POST'])
    def submit_registration_form(self, **kwargs):
        # Lấy dữ liệu từ form
        name = kwargs.get('name')
        phone = kwargs.get('phone')
        email = kwargs.get('email')
        user_id = kwargs.get('user_id')

        # Kiểm tra nếu user_id hợp lệ (không rỗng và không chứa chỉ khoảng trắng)
        if user_id and user_id.strip():
            # Tìm kiếm customer nếu có user_id
            record = request.env['res.partner'].sudo().search([('x_user_social_id', 'like', user_id)], limit=1)
        else:
            # Nếu không có user_id, tạo mới customer ngay
            record = None

        # Nếu tìm thấy customer hoặc user_id không hợp lệ, tạo mới customer
        if not record:
            request.env['res.partner'].sudo().create({
                'name': name,
                'phone': phone,
                'email': email,
                'x_source': 'zalo',
                'customer_rank': 1 # chỉ thêm user_id nếu có
            })
        else:
            # Nếu đã có customer, cập nhật thông tin
            record.sudo().write({
                'name': name,
                'phone': phone,
                'email': email,
            })

        # Trả về một trang cảm ơn hoặc chuyển hướng
        return request.redirect('/thank-you')
