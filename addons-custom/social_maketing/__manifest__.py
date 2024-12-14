# -*- coding: utf-8 -*-
{
    'name': "social_marketing",

    'summary': "Social Marketing",

    'description': """
Long description of module's purpose
    """,

    'author': "khaihieu",
    'website': "https://khaihieu.id.vn",

    # Categories can be used to filter modules in modules listing
    # Check https://github.com/odoo/odoo/blob/15.0/odoo/addons/base/data/ir_module_category_data.xml
    # for the full list
    'category': 'Uncategorized',
    'version': '0.1',

    # any module necessary for this one to work correctly
    'depends': ['base', 'account', 'crm', 'website'],
    'controllers': ['api_controller'],
    # always loaded
    'data': [
        "security/ir.model.access.csv",
        "views/mk_campaign_view.xml",
        "views/mk_customer_view.xml",
        "views/mk_app_config_view.xml",
        "wizard/send_message_social.xml",
        "views/mk_message_template_view.xml",
        "views/mk_message_template_type_view.xml",
        "views/mk_register_member_form_view.xml",
        "views/layout_no_header_no_footer.xml",
        "views/thank_you.xml"

    ],
}
