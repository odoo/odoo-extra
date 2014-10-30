# -*- coding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2004-TODAY OpenERP SA (<http://openerp.com>).
#
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU Affero General Public License as
#    published by the Free Software Foundation, either version 3 of the
#    License, or (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU Affero General Public License for more details.
#
#    You should have received a copy of the GNU Affero General Public License
#    along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
##############################################################################

import time

from openerp.osv import osv,fields
from openerp.tools.misc import attrgetter

class ir_property(osv.osv):
    _inherit = 'ir.property'

    _columns = {
        'type' : fields.selection([('char', 'Char'),
                                   ('float', 'Float'),
                                   ('boolean', 'Boolean'),
                                   ('integer', 'Integer'),
                                   ('text', 'Text'),
                                   ('binary', 'Binary'),
                                   ('many2one', 'Many2One'),
                                   ('date', 'Date'),
                                   ('datetime', 'DateTime'),
                                   ('selection', 'Selection'),
                                  ],
                                  'Type',
                                  required=True,
                                  select=1),
    }

    def _update_values(self, cr, uid, ids, values):
        value = values.pop('value', None)
        if not value:
            return values

        prop = None
        type_ = values.get('type')
        if not type_:
            if ids:
                prop = self.browse(cr, uid, ids[0])
                type_ = prop.type
            else:
                type_ = self._defaults['type']

        type2field = {
            'char': 'value_text',
            'float': 'value_float',
            'boolean' : 'value_integer',
            'integer': 'value_integer',
            'text': 'value_text',
            'binary': 'value_binary',
            'many2one': 'value_reference',
            'date' : 'value_datetime',
            'datetime' : 'value_datetime',
            'selection': 'value_text',
        }
        field = type2field.get(type_)
        if not field:
            raise osv.except_osv('Error', 'Invalid type')

        if field == 'value_reference':
            if isinstance(value, osv.orm.browse_record):
                value = '%s,%d' % (value._name, value.id)
            elif isinstance(value, (int, long)):
                field_id = values.get('fields_id')
                if not field_id:
                    if not prop:
                        raise ValueError()
                    field_id = prop.fields_id
                else:
                    field_id = self.pool.get('ir.model.fields').browse(cr, uid, field_id)

                value = '%s,%d' % (field_id.relation, value)

        values[field] = value
        return values

    def get_by_record(self, cr, uid, record, context=None):
        if record.type == 'selection':
            return record.value_text
        return super(ir_property, self).get_by_record(cr, uid, record, context=context)

ir_property()

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4: