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

from openerp.osv import fields, osv

class purchase_config_settings(osv.osv_memory):
    _inherit = 'purchase.config.settings'

    _columns = {
        'group_costing_method':fields.boolean("Compute product cost price based on average/FIFO/LIFO cost",
            implied_group='product.group_costing_method',
            help="""Allows you to compute product cost price based on average/FIFO/LIFO cost."""),
        'group_stock_inventory_valuation': fields.boolean("Generate accounting entries per stock movement",
            implied_group='stock.group_inventory_valuation',
            help="""Allows to configure inventory valuations on products and product categories."""),
    }

    def onchange_group_costing_method(self, cr, uid, ids, group_costing_method, context=None):
        value = {}
        if group_costing_method:
            value['group_stock_inventory_valuation'] = True
        return {'value': value}

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4: