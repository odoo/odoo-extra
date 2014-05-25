{
    'name': 'Document filesystem',
    'version': '1.0',
    'category': 'Hidden',
    'description': """
Document filesystem
===================

Hardlink filestore attachments to human readable path.

The hardcoded layout is model/<res.model>/<res.id>/<name>.

_document_fs_sync performs the opposite synchronisation, this can be used in a
cron job or be called by scripts (i.e. post-upload scripts).

It can be used as a basis for remplacing of the deprecated document_ftp and
document_webdav modules.

""",
    'author': 'OpenERP SA',
    'website': 'http://www.openerp.com',
    'depends': ['base'],
    'data': [],
    'installable': True,
}
