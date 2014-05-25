import glob
import logging
import os
import re

from openerp.osv import osv, fields

_logger = logging.getLogger(__name__)

class ir_attachment(osv.Model):
    _name = "ir.attachment"
    _inherit = 'ir.attachment'

    def _document_fs_sanitize(self, name):
        if isinstance(name, unicode):
            name = name.encode('utf-8')
        name = str(name)
        name = name.replace('/','')
        name = re.sub('^[.]+', '', name)
        return name

    def _get_document_fs_path(self, cr, uid, ids, field_name, arg, context=None):
        r = {}
        for attachment in self.browse(cr, uid, ids, context=context):
            link_dir = self._full_path(cr, uid, 'file', 'models')
            res_model = self._document_fs_sanitize(attachment.res_model)
            res_id = self._document_fs_sanitize(attachment.res_id)
            datas_fname = self._document_fs_sanitize(attachment.datas_fname)
            r[attachment.id] = os.path.join(link_dir, res_model, res_id, datas_fname)
        return r

    _columns = {
        'document_fs_path': fields.function(_get_document_fs_path, type='char', string='Fs path', readonly=1),
    }

    def _document_fs_unlink(self, cr, uid, ids, context=None):
        for attachment in self.browse(cr, uid, ids, context=context):
            if os.path.isfile(attachment.document_fs_path):
                os.unlink(attachment.document_fs_path)

    def _document_fs_link(self, cr, uid, ids, context=None):
        for attachment in self.browse(cr, uid, ids, context=context):
            src = self._full_path(cr, uid, 'file', attachment.store_fname)
            path = attachment.document_fs_path
            link_dir = os.path.dirname(path)
            if not os.path.isdir(link_dir):
                os.makedirs(link_dir)
            os.link(src, path)

    def _document_fs_sync(self, cr, uid, context=None):
        # WARNING files must be atomically renamed(2) if used in a cron job as
        # we read and unlink them
        if self._storage(cr, uid, context)== 'file':
            link_dir = self._full_path(cr, uid, 'file', 'models')
            l = glob.glob('%s/*/*/*' % link_dir)
            for path in l:
                if not os.path.isfile(path):
                    continue
                (p, fname) = os.path.split(path)
                (p, res_id) = os.path.split(p)
                (p, res_model) = os.path.split(p)
                try:
                    name = unicode(fname,'utf-8')
                except UnicodeError:
                    continue
                if res_model in self.pool:
                    ids = self.search(cr, uid, [('res_model','=',res_model),('res_id','=',res_id),('datas_fname','=',name)])
                    if ids:
                        continue
                    data = open(path).read().encode('base64')
                    os.unlink(path)
                    attachment = {
                        'res_model': res_model,
                        'res_id': res_id,
                        'name': name,
                        'datas_fname': name,
                        'datas': data,
                    }
                    self.create(cr, uid, attachment)

    def create(self, cr, uid, vals, context=None):
        attachment_id = super(ir_attachment, self).create(cr, uid, vals, context)
        if self._storage(cr, uid, context) == 'file':
            self._document_fs_link(cr, uid, [attachment_id], context=context)

    def write(self, cr, uid, ids, vals, context=None):
        if self._storage(cr, uid, context) == 'file':
            self._document_fs_unlink(cr, uid, ids, context=context)
        r = super(ir_attachment, self).write(cr, uid, ids, vals, context)
        if self._storage(cr, uid, context) == 'file':
            self._document_fs_link(cr, uid, ids, context=context)
        return r

    def unlink(self, cr, uid, ids, context=None): 
        if self._storage(cr, uid, context) == 'file':
            self._document_fs_unlink(cr, uid, ids, context=context)
        return super(ir_attachment, self).unlink(cr, uid, ids, context)

# vim:et:
