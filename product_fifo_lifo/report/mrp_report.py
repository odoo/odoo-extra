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

from openerp.osv import fields,osv

class report_mrp_inout(osv.osv):
    _inherit = "report.mrp.inout"
    _columns = {
        'company_id': fields.many2one('res.company', 'Company', required=True),
    }

    def init(self, cr):
        cr.execute("""
            create or replace view report_mrp_inout as (
                select
                    min(sm.id) as id,
                    to_char(sm.date,'YYYY:IW') as date,
                    sum(case when (sl.usage='internal') then
                        sm.price_unit * sm.product_qty
                    else
                        0.0
                    end - case when (sl2.usage='internal') then
                        sm.price_unit * sm.product_qty
                    else
                        0.0
                    end) as value,
                    sm.company_id
                from
                    stock_move sm
                left join product_product pp
                    on (pp.id = sm.product_id)
                left join product_template pt
                    on (pt.id = pp.product_tmpl_id)
                left join stock_location sl
                    on ( sl.id = sm.location_id)
                left join stock_location sl2
                    on ( sl2.id = sm.location_dest_id)
                where
                    sm.state = 'done'
                group by
                    to_char(sm.date,'YYYY:IW'), sm.company_id
            )""")

report_mrp_inout()

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4: