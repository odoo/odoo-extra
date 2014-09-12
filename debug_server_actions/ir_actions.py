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

from openerp.osv import fields, osv
from .safe_eval import safe_eval_debug


class ir_actions_server(osv.osv):
    _name = 'ir.actions.server'
    _inherit = 'ir.actions.server'

    _columns = {
        'debug': fields.boolean('Debug',
                                help="Run this server action through the Python debugger.\n"
                                "This only works if the server has been launched with the --debug_server_actions flag, "
                                "and aids in local development of new server actions."),
    }

    def run_action_code_multi(self, cr, uid, action, eval_context=None, context=None):
        safe_eval_debug(action.code.strip(), eval_context, mode="exec", nocopy=True, debug=action.debug)  # nocopy allows to return 'action'
        if 'action' in eval_context:
            return eval_context['action']
