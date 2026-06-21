{
    'name': 'Scoring et Routage Automatique des Leads',
    'version': '1.0',
    'category': 'Sales/CRM',
    'summary': 'Assigne automatiquement un commercial, calcule un score et route les leads lors de leur création',
    'description': """
Ce module personnalise la création des leads dans le CRM Odoo :
- Assigne automatiquement un vendeur par défaut si manquant.
- Calcule un Lead Score (0-100) basé sur le revenu attendu, l'email pro, et le numéro de téléphone.
- Route le lead en fonction du score (archiver, prioriser, appel téléphonique automatique, etc).
- Ajoute un rapport HTML détaillé au chatter du lead.
    """,
    'author': 'Antigravity',
    'depends': ['crm', 'mail'],
    'data': [],
    'installable': True,
    'application': False,
    'auto_install': False,
    'license': 'LGPL-3',
}
