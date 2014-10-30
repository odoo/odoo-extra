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

from openerp import tools
from openerp.osv import osv, fields
import openerp.addons.decimal_precision as dp

def rounding(f, r):
    if not r:
        return f
    return round(f / r) * r

class product_uom(osv.osv):
    _inherit = 'product.uom'

    def _compute_qty(self, cr, uid, from_uom_id, qty, to_uom_id=False, round=True):
        if not from_uom_id or not qty or not to_uom_id:
            return qty
        uoms = self.browse(cr, uid, [from_uom_id, to_uom_id])
        if uoms[0].id == from_uom_id:
            from_unit, to_unit = uoms[0], uoms[-1]
        else:
            from_unit, to_unit = uoms[-1], uoms[0]
        return self._compute_qty_obj(cr, uid, from_unit, qty, to_unit, round=round)

    def _compute_qty_obj(self, cr, uid, from_unit, qty, to_unit, round=True, context=None):
        if context is None:
            context = {}
        if from_unit.category_id.id <> to_unit.category_id.id:
            if context.get('raise-exception', True):
                raise osv.except_osv(_('Error!'), _('Conversion from Product UoM %s to Default UoM %s is not possible as they both belong to different Category!.') % (from_unit.name,to_unit.name,))
            else:
                return qty
        amount = qty / from_unit.factor
        if to_unit:
            if round:
                amount = rounding(amount * to_unit.factor, to_unit.rounding)
            else:
                amount = amount * to_unit.factor
        return amount

product_uom()

class product_template(osv.osv):
    _inherit = "product.template"
    _columns = {
        'standard_price': fields.property(False, type='float', digits_compute=dp.get_precision('Product Price'), view_load=True,
                                          help="Cost price of the product used for standard stock valuation in accounting and used as a base price on purchase orders.", 
                                          groups="base.group_user", string="Cost"),
        'cost_method': fields.property(False, type='selection', view_load=True, selection = [('standard','Standard Price'), ('average','Average Price'), ('fifo', 'FIFO'), ('lifo', 'LIFO')],
            help="""Standard Price: The cost price is manually updated at the end of a specific period (usually every year)
                    Average Price: The cost price is recomputed at each incoming shipment
                    FIFO Price: The cost price is recomputed at each outgoing shipment FIFO
                    LIFO Price: The cost price is recomputed at each outgoing shipment LIFO""", 
            string="Costing Method", required=True),
    }
product_template()

class product_product(osv.osv):
    _inherit = "product.product"

    def do_change_standard_price(self, cr, uid, ids, datas, context=None):
        """ Changes the Standard Price of Product and creates an account move accordingly.
        @param datas : dict. contain default datas like new_price, stock_output_account, stock_input_account, stock_journal
        @param context: A standard dictionary
        @return:

        """
        location_obj = self.pool.get('stock.location')
        move_obj = self.pool.get('account.move')
        move_line_obj = self.pool.get('account.move.line')
        if context is None:
            context = {}

        new_price = datas.get('new_price', 0.0)
        stock_output_acc = datas.get('stock_output_account', False)
        stock_input_acc = datas.get('stock_input_account', False)
        journal_id = datas.get('stock_journal', False)
        product_obj=self.browse(cr, uid, ids, context=context)[0]
        account_valuation = product_obj.categ_id.property_stock_valuation_account_id
        account_valuation_id = account_valuation and account_valuation.id or False
        if not account_valuation_id: raise osv.except_osv(_('Error!'), _('Specify valuation Account for Product Category: %s.') % (product_obj.categ_id.name))
        move_ids = []
        loc_ids = location_obj.search(cr, uid,[('usage','=','internal')])
        for rec_id in ids:
            for location in location_obj.browse(cr, uid, loc_ids, context=context):
                c = context.copy()
                c.update({
                    'location': location.id,
                    'compute_child': False
                })

                product = self.browse(cr, uid, rec_id, context=c)
                qty = product.qty_available
                diff = product.standard_price - new_price
                if not diff: raise osv.except_osv(_('Error!'), _("No difference between standard price and new price!"))
                if qty:
                    company_id = location.company_id and location.company_id.id or False
                    if not company_id: raise osv.except_osv(_('Error!'), _('Please specify company in Location.'))
                    #
                    # Accounting Entries
                    #
                    if not journal_id:
                        journal_id = product.categ_id.property_stock_journal and product.categ_id.property_stock_journal.id or False
                    if not journal_id:
                        raise osv.except_osv(_('Error!'),
                            _('Please define journal '\
                              'on the product category: "%s" (id: %d).') % \
                                (product.categ_id.name,
                                    product.categ_id.id,))
                    move_id = move_obj.create(cr, uid, {
                                'journal_id': journal_id,
                                'company_id': company_id
                                })

                    move_ids.append(move_id)


                    if diff > 0:
                        if not stock_input_acc:
                            stock_input_acc = product.\
                                property_stock_account_input.id
                        if not stock_input_acc:
                            stock_input_acc = product.categ_id.\
                                    property_stock_account_input_categ.id
                        if not stock_input_acc:
                            raise osv.except_osv(_('Error!'),
                                    _('Please define stock input account ' \
                                            'for this product: "%s" (id: %d).') % \
                                            (product.name,
                                                product.id,))
                        amount_diff = qty * diff
                        move_line_obj.create(cr, uid, {
                                    'name': product.name,
                                    'account_id': stock_input_acc,
                                    'debit': amount_diff,
                                    'move_id': move_id,
                                    })
                        move_line_obj.create(cr, uid, {
                                    'name': product.categ_id.name,
                                    'account_id': account_valuation_id,
                                    'credit': amount_diff,
                                    'move_id': move_id
                                    })
                    elif diff < 0:
                        if not stock_output_acc:
                            stock_output_acc = product.\
                                property_stock_account_output.id
                        if not stock_output_acc:
                            stock_output_acc = product.categ_id.\
                                    property_stock_account_output_categ.id
                        if not stock_output_acc:
                            raise osv.except_osv(_('Error!'),
                                    _('Please define stock output account ' \
                                            'for this product: "%s" (id: %d).') % \
                                            (product.name,
                                                product.id,))
                        amount_diff = qty * -diff
                        move_line_obj.create(cr, uid, {
                                        'name': product.name,
                                        'account_id': stock_output_acc,
                                        'credit': amount_diff,
                                        'move_id': move_id
                                    })
                        move_line_obj.create(cr, uid, {
                                        'name': product.categ_id.name,
                                        'account_id': account_valuation_id,
                                        'debit': amount_diff,
                                        'move_id': move_id
                                    })

            self.write(cr, uid, [rec_id], {'standard_price': new_price})

        return move_ids

    def _get_locations_from_context(self, cr, uid, ids, context=None):
        '''
        Parses the context and returns a list of location_ids based on it.
        It will return all stock locations when no parameters are given
        Possible parameters are warehouse, location, force_company, compute_child
        '''
        if context is None:
            context = {}
        
        location_obj = self.pool.get('stock.location')
        warehouse_obj = self.pool.get('stock.warehouse')
        shop_obj = self.pool.get('sale.shop')
        
        if context.get('shop', False):
            warehouse_id = shop_obj.read(cr, uid, int(context['shop']), ['warehouse_id'])['warehouse_id'][0]
            if warehouse_id:
                context['warehouse'] = warehouse_id

        if context.get('warehouse', False):
            lot_id = warehouse_obj.read(cr, uid, int(context['warehouse']), ['lot_stock_id'])['lot_stock_id'][0]
            if lot_id:
                context['location'] = lot_id

        if context.get('location', False):
            if type(context['location']) == type(1):
                location_ids = [context['location']]
            elif type(context['location']) in (type(''), type(u'')):
                if context.get('force_company', False):
                    location_ids = location_obj.search(cr, uid, [('name','ilike',context['location']), ('company_id', '=', context['force_company'])], context=context)
                else:
                    location_ids = location_obj.search(cr, uid, [('name','ilike',context['location'])], context=context)
            else:
                location_ids = context['location']
        else:
            location_ids = []
            wids = warehouse_obj.search(cr, uid, [], context=context)
            if not wids:
                return False
            for w in warehouse_obj.browse(cr, uid, wids, context=context):
                if not context.get('force_company', False) or w.lot_stock_id.company_id.id == context['force_company']:
                    location_ids.append(w.lot_stock_id.id)

        # build the list of ids of children of the location given by id
        if context.get('compute_child',True):
            if context.get('force_company', False):
                child_location_ids = location_obj.search(cr, uid, [('location_id', 'child_of', location_ids), ('company_id', '=', context['force_company'])])
            else:
                child_location_ids = location_obj.search(cr, uid, [('location_id', 'child_of', location_ids)])
            location_ids = child_location_ids or location_ids
        return location_ids

    def _get_date_query(self, cr, uid, ids, context):
        '''
            Parses the context and returns the dates query string needed to be processed in _get_product_available
            It searches for a from_date and to_date
        '''
        from_date = context.get('from_date',False)
        to_date = context.get('to_date',False)
        date_str = False
        whereadd = []
        
        if from_date and to_date:
            date_str = "date>=%s and date<=%s"
            whereadd.append(tuple([from_date]))
            whereadd.append(tuple([to_date]))
        elif from_date:
            date_str = "date>=%s"
            whereadd.append(tuple([from_date]))
        elif to_date:
            date_str = "date<=%s"
            whereadd.append(tuple([to_date]))
        return (whereadd, date_str)

    def get_product_available(self, cr, uid, ids, context=None):
        """ Finds the quantity available of product(s) depending on parameters in the context
        for date, location, state (allows e.g. for calculating future stock), what,
        production lot
        @return: Dictionary of values for every product id
        """
        #TODO complete the docstring with possible keys in context + their effect
        if context is None:
            context = {}
        
        states = context.get('states',[])
        what = context.get('what',())
        if not ids:
            ids = self.search(cr, uid, [])
        res = {}.fromkeys(ids, 0.0)
        if not ids:
            return res
        #set_context: refactor code here
        location_ids = self._get_locations_from_context(cr, uid, ids, context=context)
        if not location_ids: #in case of no locations, query will be empty anyways
            return res

        # this will be a dictionary of the product UoM by product id
        product2uom = {}
        uom_ids = []
        for product in self.read(cr, uid, ids, ['uom_id'], context=context):
            product2uom[product['id']] = product['uom_id'][0]
            uom_ids.append(product['uom_id'][0])
        # this will be a dictionary of the UoM resources we need for conversion purposes, by UoM id
        uoms_o = {}
        for uom in self.pool.get('product.uom').browse(cr, uid, uom_ids, context=context):
            uoms_o[uom.id] = uom

        results = []
        results2 = []

        where = [tuple(location_ids),tuple(location_ids),tuple(ids),tuple(states)]

        where_add, date_str = self._get_date_query(cr, uid, ids, context=context)
        if where_add:
            where += where_add

        prodlot_id = context.get('prodlot_id', False)
        prodlot_clause = ''
        if prodlot_id:
            prodlot_clause = ' and prodlot_id = %s '
            where += [prodlot_id]

        # TODO: perhaps merge in one query.
        if 'in' in what:
            # all moves from a location out of the set to a location in the set
            cr.execute(
                'select sum(product_qty), product_id, product_uom '\
                'from stock_move '\
                'where location_id NOT IN %s '\
                'and location_dest_id IN %s '\
                'and product_id IN %s '\
                'and state IN %s ' + (date_str and 'and '+date_str+' ' or '') +' '\
                + prodlot_clause + 
                'group by product_id,product_uom',tuple(where))
            results = cr.fetchall()
        if 'out' in what:
            # all moves from a location in the set to a location out of the set
            cr.execute(
                'select sum(product_qty), product_id, product_uom '\
                'from stock_move '\
                'where location_id IN %s '\
                'and location_dest_id NOT IN %s '\
                'and product_id  IN %s '\
                'and state in %s ' + (date_str and 'and '+date_str+' ' or '') + ' '\
                + prodlot_clause + 
                'group by product_id,product_uom',tuple(where))
            results2 = cr.fetchall()
            
        # Get the missing UoM resources
        uom_obj = self.pool.get('product.uom')
        uoms = map(lambda x: x[2], results) + map(lambda x: x[2], results2)
        if context.get('uom', False):
            uoms += [context['uom']]
        uoms = filter(lambda x: x not in uoms_o.keys(), uoms)
        if uoms:
            uoms = uom_obj.browse(cr, uid, list(set(uoms)), context=context)
            for o in uoms:
                uoms_o[o.id] = o
                
        #TOCHECK: before change uom of product, stock move line are in old uom.
        context.update({'raise-exception': False})
        # Count the incoming quantities
        for amount, prod_id, prod_uom in results:
            amount = uom_obj._compute_qty_obj(cr, uid, uoms_o[prod_uom], amount,
                     uoms_o[context.get('uom', False) or product2uom[prod_id]], context=context)
            res[prod_id] += amount
        # Count the outgoing quantities
        for amount, prod_id, prod_uom in results2:
            amount = uom_obj._compute_qty_obj(cr, uid, uoms_o[prod_uom], amount,
                    uoms_o[context.get('uom', False) or product2uom[prod_id]], context=context)
            res[prod_id] -= amount
        return res

    _columns = {
         'valuation':fields.property(False, type='selection', view_load=True, selection=[('manual_periodic', 'Periodical (manual)'),
                                         ('real_time','Real Time (automated)'),], string = 'Inventory Valuation',
                                         help="If real-time valuation is enabled for a product, the system will automatically write journal entries corresponding to stock moves." \
                                              "The inventory variation account set on the product category will represent the current inventory value, and the stock input and stock output account will hold the counterpart moves for incoming and outgoing products."
                                         , required=True),
    }

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
