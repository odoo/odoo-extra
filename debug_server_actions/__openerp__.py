# -*- encoding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2004-TODAY OpenERP S.A. <http://www.openerp.com>
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
    'name': 'Debug Server Actions',
    'version': '1.0',
    'category': 'Tools',
    'description': """
Allows for interactive debugging of server actions through pdb.

A new field "Debug" has been added on the server actions, which allows you to
mark specific server actions for debugging. No other actions will be debugged.

In order to enable this, install this module, restart the server with the
--debug flag, and set the Debug option on the server action you wish to debug.

Then trigger your server action, and check your console.
    """,
    'author': 'OpenERP SA',
    'depends': ['base'],
    'data': [
        'views/ir_actions.xml',
    ],
    'demo': [],
    'test': [],
    'installable': True,
    'auto_install': False,
    'images': [],
    'css': [],
}
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
