{
    'name': 'HR Leave Tracker',
    'version': '1.0.0',
    'category': 'Human Resources',
    'summary': 'Track employee leave balances',
    'description': """
        HR Leave Tracker
        
        Simple leave balance tracking system.
    """,
    'author': 'Your Company',
    'depends': ['hr', 'hr_holidays'],
    'external_dependencies': {
        'python': ['openpyxl', 'xlrd'],
    },
    'data': [
        'security/ir.model.access.csv',
        'views/hr_leave_tracker_views.xml',
        'wizard/hr_leave_import_views.xml',
    ],
    'installable': True,
    'auto_install': False,
    'application': False,
}