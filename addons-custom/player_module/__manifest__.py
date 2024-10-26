# -*- coding: utf-8 -*-
{
    'name': "People Module",

    'summary': """
        ok""",

    'description': """
        Long description of module's purpose
    """,

    'author': "Mountain",
    'website': "http://www.yourcompany.com",

    # Categories can be used to filter modules in modules listing
    # Check https://github.com/odoo/odoo/blob/14.0/odoo/addons/base/data/ir_module_category_data.xml
    # for the full list
    'category': 'Uncategorized',
    'version': '0.1',

    # any module necessary for this one to work correctly
    'depends': ['base'],

    'data': [
        'views/player_views.xml',
        'views/menu.xml'
    ],
    'installable': True,
    'application': False,
}