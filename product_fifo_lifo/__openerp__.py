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

{
    'name': 'FIFO (v7.0)',
    'version': '1.1',
    'author': 'OpenERP SA',
    'summary': 'Inventory Management',
    'website': 'http://www.openerp.com',
    'depends': ['purchase', 'stock_location', 'mrp', 'product_margin', 'product_extended'],
    'category': 'Warehouse Management',
    'demo': [
        'stock_demo.xml'
    ],
    'data': [
        'product_view.xml',
        'procurement_pull_workflow.xml',
        'security/stock_security.xml',
        'security/ir.model.access.csv',
        'report/mrp_report_view.xml',
        'report/report_stock_move_view.xml',
    ],
    'test': [
        'test/fifo_returns.yml',
        'test/costmethodchange.yml',
        'test/average_price.yml',
        'test/fifo_price.yml',
        'test/lifo_price.yml',
    ],
    'installable': True,
    'application': True,
    'auto_install': False,
}

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
