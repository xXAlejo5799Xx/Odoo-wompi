{
    'name': 'Wompi Payment Provider',
    'version': '19.0.1.0.0',
    'category': 'Accounting/Payment Providers',
    'summary': 'Accept payments via Wompi',
    'description': 'Adds the Wompi payment provider to Odoo.',
    'depends': ['payment'],
    'data': [
        'data/payment_provider_data.xml',
        'data/payment_method_data.xml',
        'views/payment_provider_views.xml',
    ],
    'assets': {
        'web.assets_frontend': [
            'payment_wompi/static/src/js/payment_wompi.js',
        ],
    },
    'license': 'LGPL-3',
    'installable': True,
}
