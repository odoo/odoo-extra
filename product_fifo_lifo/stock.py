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
from openerp.osv import fields, osv
from openerp.tools.translate import _
from openerp import netsvc
from openerp import tools
from openerp.tools import float_compare, DEFAULT_SERVER_DATETIME_FORMAT

class stock_picking(osv.osv):
    _inherit = "stock.picking"

    def do_partial(self, cr, uid, ids, partial_datas, context=None):
        """ Makes partial picking and moves done.
        @param partial_datas : Dictionary containing details of partial picking
                          like partner_id, partner_id, delivery_date,
                          delivery moves with product_id, product_qty, uom
        @return: Dictionary of values
        """
        if context is None:
            context = {}
        else:
            context = dict(context)
        res = {}
        move_obj = self.pool.get('stock.move')
        product_obj = self.pool.get('product.product')
        currency_obj = self.pool.get('res.currency')
        uom_obj = self.pool.get('product.uom')
        sequence_obj = self.pool.get('ir.sequence')
        wf_service = netsvc.LocalService("workflow")
        for pick in self.browse(cr, uid, ids, context=context):
            new_picking = None
            complete, too_many, too_few = [], [], []
            move_product_qty, prodlot_ids, partial_qty, product_uoms = {}, {}, {}, {}
            for move in pick.move_lines:
                if move.state in ('done', 'cancel'):
                    continue
                partial_data = partial_datas.get('move%s'%(move.id), {})
                product_qty = partial_data.get('product_qty',0.0)
                move_product_qty[move.id] = product_qty
                product_uom = partial_data.get('product_uom',False)
                product_price = partial_data.get('product_price',0.0)
                prodlot_id = partial_data.get('prodlot_id')
                prodlot_ids[move.id] = prodlot_id
                product_uoms[move.id] = product_uom
                partial_qty[move.id] = uom_obj._compute_qty(cr, uid, product_uoms[move.id], product_qty, move.product_uom.id)
                if move.product_qty == partial_qty[move.id]:
                    complete.append(move)
                elif move.product_qty > partial_qty[move.id]:
                    too_few.append(move)
                else:
                    too_many.append(move)

            for move in too_few:
                product_qty = move_product_qty[move.id]
                if not new_picking:
                    new_picking_name = pick.name
                    self.write(cr, uid, [pick.id], 
                               {'name': sequence_obj.get(cr, uid,
                                            'stock.picking.%s'%(pick.type)),
                               })
                    new_picking = self.copy(cr, uid, pick.id,
                            {
                                'name': new_picking_name,
                                'move_lines' : [],
                                'state':'draft',
                            })
                if product_qty != 0:
                    defaults = {
                            'product_qty' : product_qty,
                            'product_uos_qty': product_qty, #TODO: put correct uos_qty
                            'picking_id' : new_picking,
                            'state': 'assigned',
                            'move_dest_id': False,
                            'price_unit': product_price,
                            'product_uom': product_uoms[move.id]
                    }
                    prodlot_id = prodlot_ids[move.id]
                    if prodlot_id:
                        defaults.update(prodlot_id=prodlot_id)
                    move_obj.copy(cr, uid, move.id, defaults)
                move_obj.write(cr, uid, [move.id],
                        {
                            'product_qty': move.product_qty - partial_qty[move.id],
                            'product_uos_qty': move.product_qty - partial_qty[move.id], #TODO: put correct uos_qty
                            'prodlot_id': False,
                            'tracking_id': False,
                        })

            if new_picking:
                move_obj.write(cr, uid, [c.id for c in complete], {'picking_id': new_picking})
            for move in complete:
                defaults = {'product_uom': product_uoms[move.id], 'product_qty': move_product_qty[move.id]}
                if prodlot_ids.get(move.id):
                    defaults.update({'prodlot_id': prodlot_ids[move.id]})
                move_obj.write(cr, uid, [move.id], defaults)
            for move in too_many:
                product_qty = move_product_qty[move.id]
                defaults = {
                    'product_qty' : product_qty,
                    'product_uos_qty': product_qty, #TODO: put correct uos_qty
                    'product_uom': product_uoms[move.id]
                }
                prodlot_id = prodlot_ids.get(move.id)
                if prodlot_ids.get(move.id):
                    defaults.update(prodlot_id=prodlot_id)
                if new_picking:
                    defaults.update(picking_id=new_picking)
                move_obj.write(cr, uid, [move.id], defaults)

            # At first we confirm the new picking (if necessary)
            if new_picking:
                wf_service.trg_validate(uid, 'stock.picking', new_picking, 'button_confirm', cr)
                # Then we finish the good picking
                self.write(cr, uid, [pick.id], {'backorder_id': new_picking})
                self.action_move(cr, uid, [new_picking], context=context)
                wf_service.trg_validate(uid, 'stock.picking', new_picking, 'button_done', cr)
                wf_service.trg_write(uid, 'stock.picking', pick.id, cr)
                delivered_pack_id = new_picking
                back_order_name = self.browse(cr, uid, delivered_pack_id, context=context).name
                self.message_post(cr, uid, ids, body=_("Back order <em>%s</em> has been <b>created</b>.") % (back_order_name), context=context)
            else:
                self.action_move(cr, uid, [pick.id], context=context)
                wf_service.trg_validate(uid, 'stock.picking', pick.id, 'button_done', cr)
                delivered_pack_id = pick.id

            delivered_pack = self.browse(cr, uid, delivered_pack_id, context=context)
            res[pick.id] = {'delivered_picking': delivered_pack.id or False}

        return res

class stock_move(osv.osv):
    _inherit = "stock.move"

    _columns = {
        'move_returned_from': fields.many2one('stock.move', 'Move this move was returned from'),
        'price_unit': fields.float('Unit Price', help="Technical field used to record the product cost set by the user during a picking confirmation (when average price costing method is used)"),
    }

    def _check_company_location(self, cr, uid, ids, context=None):
        for record in self.browse(cr, uid, ids, context=context):
            if record.location_id.company_id and (record.company_id.id != record.location_id.company_id.id):
                raise osv.except_osv(_('Error'), _('The company of the source location (%s) and the company of the stock move (%s) should be the same') % (record.location_id.company_id.name, record.company_id.name))
            if record.location_dest_id.company_id and (record.company_id.id != record.location_dest_id.company_id.id):
                raise osv.except_osv(_('Error'), _('The company of the destination location (%s) and the company of the stock move (%s) should be the same') % (record.location_dest_id.company_id.name, record.company_id.name))
        return True

    _constraints = [
        (_check_company_location, 'You cannot use a location from another company. ', 
            ['company_id', 'location_id', 'location_dest_id'])]

    def _default_location_destination(self, cr, uid, context=None):
        """ Gets default address of partner for destination location
        @return: Address id or False
        """
        mod_obj = self.pool.get('ir.model.data')
        picking_type = context.get('picking_type')
        location_id = False
        if context is None:
            context = {}
        if context.get('move_line', []):
            if context['move_line'][0]:
                if isinstance(context['move_line'][0], (tuple, list)):
                    location_id = context['move_line'][0][2] and context['move_line'][0][2].get('location_dest_id',False)
                else:
                    move_list = self.pool.get('stock.move').read(cr, uid, context['move_line'][0], ['location_dest_id'])
                    location_id = move_list and move_list['location_dest_id'][0] or False
        elif context.get('address_out_id', False):
            property_out = self.pool.get('res.partner').browse(cr, uid, context['address_out_id'], context).property_stock_customer
            location_id = property_out and property_out.id or False
        else:
            location_xml_id = False
            if picking_type in ('in', 'internal'):
                location_xml_id = 'stock_location_stock'
            elif picking_type == 'out':
                location_xml_id = 'stock_location_customers'
            if location_xml_id:
                location_model, location_id = mod_obj.get_object_reference(cr, uid, 'stock', location_xml_id)
                if location_id:
                    location_company = self.pool.get("stock.location").browse(cr, uid, location_id, context=context).company_id
                    user_company = self.pool.get("res.users").browse(cr, uid, uid, context=context).company_id.id
                    if location_company and location_company.id != user_company:
                        location_id = False
        return location_id

    def _default_location_source(self, cr, uid, context=None):
        """ Gets default address of partner for source location
        @return: Address id or False
        """
        mod_obj = self.pool.get('ir.model.data')
        picking_type = context.get('picking_type')
        location_id = False

        if context is None:
            context = {}
        if context.get('move_line', []):
            try:
                location_id = context['move_line'][0][2]['location_id']
            except:
                pass
        elif context.get('address_in_id', False):
            part_obj_add = self.pool.get('res.partner').browse(cr, uid, context['address_in_id'], context=context)
            if part_obj_add:
                location_id = part_obj_add.property_stock_supplier.id
        else:
            location_xml_id = False
            if picking_type == 'in':
                location_xml_id = 'stock_location_suppliers'
            elif picking_type in ('out', 'internal'):
                location_xml_id = 'stock_location_stock'
            if location_xml_id:
                location_model, location_id = mod_obj.get_object_reference(cr, uid, 'stock', location_xml_id)
                if location_id:
                    location_company = self.pool.get("stock.location").browse(cr, uid, location_id, context=context).company_id
                    user_company = self.pool.get("res.users").browse(cr, uid, uid, context=context).company_id.id
                    if location_company and location_company.id != user_company:
                        location_id = False
        return location_id

    def onchange_move_type(self, cr, uid, ids, type, context=None):
        """ On change of move type gives sorce and destination location.
        @param type: Move Type
        @return: Dictionary of values
        """
        mod_obj = self.pool.get('ir.model.data')
        location_source_id = 'stock_location_stock'
        location_dest_id = 'stock_location_stock'
        if type == 'in':
            location_source_id = 'stock_location_suppliers'
            location_dest_id = 'stock_location_stock'
        elif type == 'out':
            location_source_id = 'stock_location_stock'
            location_dest_id = 'stock_location_customers'
        source_location = mod_obj.get_object_reference(cr, uid, 'stock', location_source_id)
        dest_location = mod_obj.get_object_reference(cr, uid, 'stock', location_dest_id)
        #Check companies
        user_company = self.pool.get("res.users").browse(cr, uid, uid, context=context).company_id.id
        if source_location:
            location_company = self.pool.get("stock.location").browse(cr, uid, source_location[1], context=context).company_id
            if location_company and location_company.id != user_company:
                source_location = False
        if dest_location:
            location_company = self.pool.get("stock.location").browse(cr, uid, dest_location[1], context=context).company_id
            if location_company and location_company.id != user_company:
                dest_location = False
        return {'value':{'location_id': source_location and source_location[1] or False, 'location_dest_id': dest_location and dest_location[1] or False}}

    #We can use a preliminary type
    def get_reference_amount(self, cr, uid, move, qty, context=None):
        # if product is set to average price and a specific value was entered in the picking wizard,
        # we use it

        # by default the reference currency is that of the move's company
        reference_currency_id = move.company_id.currency_id.id
        
        #I use 
        if move.product_id.cost_method != 'standard' and move.price_unit:
            reference_amount = move.product_qty * move.price_unit #Using move.price_qty instead of qty to have correct amount
            reference_currency_id = move.price_currency_id.id or reference_currency_id

        # Otherwise we default to the company's valuation price type, considering that the values of the
        # valuation field are expressed in the default currency of the move's company.
        else:
            if context is None:
                context = {}
            currency_ctx = dict(context, currency_id = move.company_id.currency_id.id)
            amount_unit = move.product_id.price_get('standard_price', context=currency_ctx)[move.product_id.id]
            reference_amount = amount_unit * qty
        
        return reference_amount, reference_currency_id

    def _get_reference_accounting_values_for_valuation(self, cr, uid, move, context=None):
        """
        Return the reference amount and reference currency representing the inventory valuation for this move.
        These reference values should possibly be converted before being posted in Journals to adapt to the primary
        and secondary currencies of the relevant accounts.
        """
        product_uom_obj = self.pool.get('product.uom')

        default_uom = move.product_id.uom_id.id
        qty = product_uom_obj._compute_qty(cr, uid, move.product_uom.id, move.product_qty, default_uom)
        
        reference_amount, reference_currency_id = self.get_reference_amount(cr, uid, move, qty, context=context)
        return reference_amount, reference_currency_id

    def _create_product_valuation_moves(self, cr, uid, move, matches, context=None):
        """
        Generate the appropriate accounting moves if the product being moved is subject
        to real_time valuation tracking, and the source or the destination location is internal (not both)
        This means an in or out move. 
        
        Depending on the matches it will create the necessary moves
        """
        if context is None:
            context = {}
        ctx = context.copy()
        ctx['force_company'] = move.company_id.id
        valuation = self.pool.get("product.product").browse(cr, uid, move.product_id.id, context=ctx).valuation
        move_obj = self.pool.get('account.move')
        if valuation == 'real_time':
            company_ctx = dict(context,force_company=move.company_id.id)
            journal_id, acc_src, acc_dest, acc_valuation = self._get_accounting_data_for_valuation(cr, uid, move, context=company_ctx)
            reference_amount, reference_currency_id = self._get_reference_accounting_values_for_valuation(cr, uid, move, context=company_ctx)
            account_moves = []
            # Outgoing moves (or cross-company output part)
            if move.location_id.company_id \
                and (move.location_id.usage == 'internal' and move.location_dest_id.usage != 'internal'):
                #returning goods to supplier
                if move.location_dest_id.usage == 'supplier':
                    account_moves += [(journal_id, self._create_account_move_line(cr, uid, move, matches, acc_valuation, acc_src, reference_amount, reference_currency_id, 'out', context=company_ctx))]
                else:
                    account_moves += [(journal_id, self._create_account_move_line(cr, uid, move, matches, acc_valuation, acc_dest, reference_amount, reference_currency_id, 'out', context=company_ctx))]

            # Incoming moves (or cross-company input part)
            if move.location_dest_id.company_id \
                and (move.location_id.usage != 'internal' and move.location_dest_id.usage == 'internal'):
                #goods return from customer
                if move.location_id.usage == 'customer':
                    account_moves += [(journal_id, self._create_account_move_line(cr, uid, move, matches, acc_dest, acc_valuation, reference_amount, reference_currency_id, 'in', context=company_ctx))]
                else:
                    account_moves += [(journal_id, self._create_account_move_line(cr, uid, move, matches, acc_src, acc_valuation, reference_amount, reference_currency_id, 'in', context=company_ctx))]
                if matches and move.product_id.cost_method in ('fifo', 'lifo'):
                    outs = {}
                    match_obj = self.pool.get("stock.move.matching")
                    for match in match_obj.browse(cr, uid, matches, context=context):
                        if match.move_out_id.id in outs:
                            outs[match.move_out_id.id] += [match.id]
                        else:
                            outs[match.move_out_id.id] = [match.id]
                    #When in stock was negative, you will get matches for the in also:
                    account_moves_neg = []
                    for out_mov in self.browse(cr, uid, outs.keys(), context=context):
                        journal_id_out, acc_src_out, acc_dest_out, acc_valuation_out = self._get_accounting_data_for_valuation(cr, uid, out_mov, context=company_ctx)
                        reference_amount_out, reference_currency_id_out = self._get_reference_accounting_values_for_valuation(cr, uid, out_mov, context=company_ctx)
                        if out_mov.location_dest_id.usage == 'supplier':
                            # Is not the way it should be with acc_valuation
                            account_moves_neg += [(journal_id_out, self._create_account_move_line(cr, uid, out_mov, outs[out_mov.id], acc_valuation_out, acc_src_out, reference_amount_out, reference_currency_id_out, 'out', context=company_ctx))]
                        else:
                            account_moves_neg += [(journal_id_out, self._create_account_move_line(cr, uid, out_mov, outs[out_mov.id], acc_valuation_out, acc_dest_out, reference_amount_out, reference_currency_id_out, 'out', context=company_ctx))]
                    #Create account moves for outs which made stock go negative
                    for j_id, move_lines in account_moves_neg:
                        move_obj.create(cr, uid,
                                        {'journal_id': j_id, 
                                         'line_id': move_lines, 
                                         'ref': out_mov.picking_id and out_mov.picking_id.name,
                                         })
            for j_id, move_lines in account_moves:
                move_obj.create(cr, uid,
                        {
                         'journal_id': j_id,
                         'line_id': move_lines,
                         'ref': move.picking_id and move.picking_id.name})

    def action_done(self, cr, uid, ids, context=None):
        """ Makes the move done and if all moves are done, it will finish the picking.
        @return:
        """
        picking_ids = []
        move_ids = []
        wf_service = netsvc.LocalService("workflow")
        if context is None:
            context = {}

        todo = []
        for move in self.browse(cr, uid, ids, context=context):
            if move.state=="draft":
                todo.append(move.id)
        if todo:
            self.action_confirm(cr, uid, todo, context=context)
            todo = []

        #Do price calculation on moves
        matchresults = self.price_calculation(cr, uid, ids, context=context)
        for move in self.browse(cr, uid, ids, context=context):
            if move.state in ['done','cancel']:
                continue
            move_ids.append(move.id)

            if move.picking_id:
                picking_ids.append(move.picking_id.id)
            if move.move_dest_id.id and (move.state != 'done'):
                # Downstream move should only be triggered if this move is the last pending upstream move
                other_upstream_move_ids = self.search(cr, uid, [('id','!=',move.id),('state','not in',['done','cancel']),
                                            ('move_dest_id','=',move.move_dest_id.id)], context=context)
                if not other_upstream_move_ids:
                    self.write(cr, uid, [move.id], {'move_history_ids': [(4, move.move_dest_id.id)]})
                    if move.move_dest_id.state in ('waiting', 'confirmed'):
                        self.force_assign(cr, uid, [move.move_dest_id.id], context=context)
                        if move.move_dest_id.picking_id:
                            wf_service.trg_write(uid, 'stock.picking', move.move_dest_id.picking_id.id, cr)
                        if move.move_dest_id.auto_validate:
                            self.action_done(cr, uid, [move.move_dest_id.id], context=context)

            self._create_product_valuation_moves(cr, uid, move, move.id in matchresults and matchresults[move.id] or [], context=context)
            if move.state not in ('confirmed','done','assigned'):
                todo.append(move.id)

        if todo:
            self.action_confirm(cr, uid, todo, context=context)

        self.write(cr, uid, move_ids, {'state': 'done', 'date': time.strftime(DEFAULT_SERVER_DATETIME_FORMAT)}, context=context)
        for id in move_ids:
             wf_service.trg_trigger(uid, 'stock.move', id, cr)

        for pick_id in picking_ids:
            wf_service.trg_write(uid, 'stock.picking', pick_id, cr)

        return True


    def _create_account_move_line(self, cr, uid, move, matches, src_account_id, dest_account_id, reference_amount, reference_currency_id, type='', context=None):
        """
        Generate the account.move.line values to post to track the stock valuation difference due to the
        processing of the given stock move.
        """
        move_list = []
        # Consists of access rights 
        # TODO Check if amount_currency is not needed
        match_obj = self.pool.get("stock.move.matching")
        product_obj = self.pool.get('product.product')
        if move.product_id.supply_method =='produce' and type=='out' and move.product_id.cost_method in ['fifo', 'lifo']:
            if move.product_id.cost_method == 'fifo':
                order = 'date, id'
            else: 
                order = 'date desc, id desc'
            matching_obj = self.pool.get('stock.mrp.matching')
            match_obj = self.pool.get('stock.move.matching')
            tuples = []
            match_ids = matching_obj.search(cr, uid, [('product_id','=',move.product_id.id), ('mrp_qty','>',0),('move_out_id','=',False)], order=order)
            product_qty = move.product_qty
            move_list = {}
            for match in matching_obj.browse(cr, uid, match_ids):
                if product_qty <= 0:
                    break
                if match.mrp_qty <= product_qty:
                    matching_obj.write(cr, uid, match.id, {'mrp_qty':  match.mrp_qty -product_qty})
                    if match.price_unit_mrp in move_list:
                        move_list[match.price_unit_mrp] += match.mrp_qty
                    else:
                        move_list[match.price_unit_mrp] = match.mrp_qty
                    tuples.append((match.move_in_id.id, match.mrp_qty, match.price_unit_mrp))
                    product_qty = product_qty - match.mrp_qty
                else:
                    tuples.append((match.move_in_id.id, product_qty, match.price_unit_mrp))
                    matching_obj.write(cr, uid, match.id, {'mrp_qty': product_qty - match.mrp_qty })
                    product_qty = 0
                    if match.price_unit_mrp in move_list:
                        move_list[match.price_unit_mrp] += match.mrp_qty
                    else:
                        move_list[match.price_unit_mrp] = match.mrp_qty
            if move_list:
                move_list = [ (qty, price * qty) for price, qty in move_list.items()]
            else:
                move_list = [(move.product_qty, move.product_qty * move.price_unit)]
        elif type == 'out' and move.product_id.cost_method in ['fifo', 'lifo']:
            for match in match_obj.browse(cr, uid, matches, context=context):
                move_list += [(match.qty, match.qty * match.price_unit_out)]
        elif move.production_id and type == 'in' and move.product_id.cost_method in ['fifo', 'lifo']:
            new_move_list, product_id, components, product_toconsume= {}, [], {}, {}
            if move.production_id.picking_id:
                for line in move.production_id.bom_id.bom_lines:
                    product_toconsume.update({line.product_id.id: line.product_qty})
                for component in move.production_id.picking_id.move_lines:
                    move_out_id = component.move_dest_id.id
                    if move.production_id.bom_id and move.production_id.bom_id.routing_id.id and move.production_id.bom_id.routing_id.location_id.id:
                        move_out_id = component.id 
                    out_ids = match_obj.search(cr, uid, [('move_out_id', '=', move_out_id)], context=context)
                    components[component.product_id.id] = [ [out.qty, out.price_unit_out] for out in match_obj.browse(cr, uid, out_ids) ]
                    product_id.append(component.product_id.id)

            looplen = move.product_qty.is_integer() and int(move.product_qty) or int(move.product_qty+ 1)
            for loop in range(looplen):
                move_price = 0
                for product, stock in components.items():
                    qty, price = product_toconsume[product], 0
                    for i in range(len(stock)):
                        if qty == 0:
                            break
                        if stock[i][0] == 0:
                            continue
                        if stock[i][0] >= qty:
                            price += qty * stock[i][1]
                            stock[i][0] -= qty
                            qty = 0
                        else:
                            price += stock[i][1] * stock[i][0]
                            qty -= stock[i][0]
                            stock[i][0] = 0
                        
                    move_price += price
                if move_price in new_move_list:
                    new_move_list[move_price] += 1
                else:
                    new_move_list[move_price] = 1
            move_list = [ (qty, price * qty) for price, qty in new_move_list.items()]
            new_price = 0
            product_obj = self.pool.get('product.product')
            matching_obj = self.pool.get('stock.mrp.matching')
            for price, qty in new_move_list.items():
                matchvals = {'move_in_id': move.id, 'price_unit_mrp': price,
                           'product_id': move.product_id.id, 'mrp_qty': qty}
                match_id = matching_obj.create(cr, uid, matchvals, context=context)
                new_price += price * qty
            product_obj.write(cr, uid, [move.product_id.id], {'standard_price': new_price / move.product_qty,}, context)
            self.write(cr, uid, move.id, {'price_unit': new_price / move.product_qty}, context=context)
        elif type == 'in' and move.product_id.cost_method in ['fifo', 'lifo']:
            move_list = [(move.product_qty, reference_amount)]
        else:
            move_list = [(move.product_qty, reference_amount)]

        res = []
        for item in move_list:
            # prepare default values considering that the destination accounts have the reference_currency_id as their main currency
            partner_id = (move.picking_id.partner_id and self.pool.get('res.partner')._find_accounting_partner(move.picking_id.partner_id).id) or False
            debit_line_vals = {
                        'name': move.name,
                        'product_id': move.product_id and move.product_id.id or False,
                        'quantity': item[0],
                        'product_uom_id': move.product_uom.id, 
                        'ref': move.picking_id and move.picking_id.name or False,
                        'date': time.strftime('%Y-%m-%d'),
                        'partner_id': partner_id,
                        'debit': item[1],
                        'account_id': dest_account_id,
            }
            credit_line_vals = {
                        'name': move.name,
                        'product_id': move.product_id and move.product_id.id or False,
                        'quantity': item[0],
                        'product_uom_id': move.product_uom.id, 
                        'ref': move.picking_id and move.picking_id.name or False,
                        'date': time.strftime('%Y-%m-%d'),
                        'partner_id': partner_id,
                        'credit': item[1],
                        'account_id': src_account_id,
            }
            res += [(0, 0, debit_line_vals), (0, 0, credit_line_vals)]
        return res

    def _generate_negative_stock_matchings(self, cr, uid, ids, product, context=None):
        """
        This method generates the stock move matches for out moves of product with qty remaining
        according to the in move
        force_company should be in context already
        | ids : id of in move
        | product: browse record of product
        Returns: 
        | List of matches
        """
        assert len(ids) == 1, _("Only generate negative stock matchings one by one")
        move = self.browse(cr, uid, ids, context=context)[0]
        cost_method = product.cost_method
        matching_obj = self.pool.get("stock.move.matching")
        product_obj = self.pool.get("product.product")
        uom_obj = self.pool.get("product.uom")
        res = []
        #Search for the most recent out moves
        moves = self.search(cr, uid, [('company_id', '=', move.company_id.id), ('state','=', 'done'), ('location_id.usage','=','internal'), ('location_dest_id.usage', '!=', 'internal'), 
                                          ('product_id', '=', move.product_id.id), ('qty_remaining', '>', 0.0)], order='date, id', context=context)
        qty_to_go = move.product_qty
        for out_mov in self.browse(cr, uid, moves, context=context):
            if qty_to_go <= 0.0:
                break
            out_qty_converted =  uom_obj._compute_qty(cr, uid, out_mov.product_uom.id, out_mov.qty_remaining, move.product_uom.id, round=False)
            qty = 0.0
            if out_qty_converted <= qty_to_go:
                qty = out_qty_converted
            elif qty_to_go > 0.0: 
                qty = qty_to_go
            revert_qty = (qty / out_qty_converted) * out_mov.qty_remaining
            matchvals = {'move_in_id': move.id, 'qty': revert_qty, 
                         'move_out_id': out_mov.id}
            match_id = matching_obj.create(cr, uid, matchvals, context=context)
            res.append(match_id)
            qty_to_go -= qty
            #Need to re-calculate total price of every out_move if FIFO/LIFO
            if cost_method in ['fifo', 'lifo']:
                matches = matching_obj.search(cr, uid, [('move_out_id', '=', out_mov.id)], context=context)
                amount = 0.0
                total_price = 0.0
                for match in matching_obj.browse(cr, uid, matches, context=context):
                    amount += match.qty 
                    total_price += match.qty * match.price_unit_out
                if amount > 0.0:
                    self.write(cr, uid, [out_mov.id], {'price_unit': total_price / amount}, context=context)
                    if amount >= out_mov.product_qty:
                        product_obj.write(cr, uid, [product.id], {'standard_price': total_price / amount}, context=context)
        return res

    def price_calculation(self, cr, uid, ids, context=None):
        '''
        This method puts the right price on the stock move, 
        adapts the price on the product when necessary
        and creates the necessary stock move matchings
        
        It returns a list of tuples with (move_id, match_id) 
        which is used for generating the accounting entries when FIFO/LIFO
        '''
        product_obj = self.pool.get('product.product')
        currency_obj = self.pool.get('res.currency')
        matching_obj = self.pool.get('stock.move.matching')
        uom_obj = self.pool.get('product.uom')
        
        product_avail = {}
        res = {}
        for move in self.browse(cr, uid, ids, context=context):
            # Initialize variables
            res[move.id] = []
            move_qty = move.product_qty
            move_uom = move.product_uom.id
            company_id = move.company_id.id
            ctx = context.copy()
            user = self.pool.get('res.users').browse(cr, uid, uid, context=context)
            ctx['force_company'] = move.company_id.id
            product = product_obj.browse(cr, uid, move.product_id.id, context=ctx)
            cost_method = product.cost_method
            product_uom_qty = uom_obj._compute_qty(cr, uid, move_uom, move_qty, product.uom_id.id, round=False)
            if not product.id in product_avail:
                product_avail[product.id] = product.qty_available
            
            # Check if out -> do stock move matchings and if fifo/lifo -> update price
            # only update the cost price on the product form on stock moves of type == 'out' because if a valuation has to be made without PO, 
            # for inventories for example we want to use the last value used for an outgoing move
            if move.location_id.usage == 'internal' and move.location_dest_id.usage != 'internal':
                fifo = (cost_method != 'lifo')
                tuples = product_obj.get_stock_matchings_fifolifo(cr, uid, [product.id], move_qty, fifo, 
                                                                  move_uom, move.company_id.currency_id.id, context=ctx) #TODO Would be better to use price_currency_id for migration?
                price_amount = 0.0
                amount = 0.0
                #Write stock matchings
                for match in tuples: 
                    matchvals = {'move_in_id': match[0], 'qty': match[1], 
                                 'move_out_id': move.id}
                    match_id = matching_obj.create(cr, uid, matchvals, context=context)
                    res[move.id].append(match_id)
                    price_amount += match[1] * match[2]
                    amount += match[1]
                #Write price on out move
                if product_avail[product.id] >= product_uom_qty and product.cost_method in ['fifo', 'lifo']:
                    if amount > 0:
                        self.write(cr, uid, move.id, {'price_unit': price_amount / amount}, context=context)
                        product_obj.write(cr, uid, product.id, {'standard_price': price_amount / product_uom_qty}, context=ctx)
                    else:
                        raise osv.except_osv(_('Error'), _("Something went wrong finding stock moves ") + str(tuples) + str(self.search(cr, uid, [('company_id','=', company_id), ('qty_remaining', '>', 0), ('state', '=', 'done'), 
                                             ('location_id.usage', '!=', 'internal'), ('location_dest_id.usage', '=', 'internal'), ('product_id', '=', product.id)], 
                                       order = 'date, id', context=context)) + str(move_qty) + str(move_uom) + str(move.company_id.currency_id.id))
                else:
                    new_price = uom_obj._compute_price(cr, uid, product.uom_id.id, product.standard_price, move_uom)
                    self.write(cr, uid, move.id, {'price_unit': new_price}, context=ctx)
                #Adjust product_avail when not average and move returned from
                if (not move.move_returned_from or product.cost_method != 'average'):
                    product_avail[product.id] -= product_uom_qty
            
            #Check if in => if price 0.0, take standard price / Update price when average price and price on move != standard price
            if move.location_id.usage != 'internal' and move.location_dest_id.usage == 'internal':
                if move.price_unit == 0.0:
                    new_price = uom_obj._compute_price(cr, uid, product.uom_id.id, product.standard_price, move_uom)
                    self.write(cr, uid, move.id, {'price_unit': new_price}, context=ctx)
                elif product.cost_method == 'average':
                    move_product_price = uom_obj._compute_price(cr, uid, move_uom, move.price_unit, product.uom_id.id)
                    if product_avail[product.id] > 0.0:
                        amount_unit = product.standard_price
                        new_std_price = ((amount_unit * product_avail[product.id])\
                                + (move_product_price * product_uom_qty))/(product_avail[product.id] + product_uom_qty)
                    else:
                        new_std_price = move_product_price
                    product_obj.write(cr, uid, [product.id], {'standard_price': new_std_price}, context=ctx)
                # Should create the stock move matchings for previous outs for the negative stock that can be matched with is in
                if product_avail[product.id] < 0.0:
                    resneg = self._generate_negative_stock_matchings(cr, uid, [move.id], product, context=ctx)
                    res[move.id] += resneg
                product_avail[product.id] += product_uom_qty
            #The return of average products at average price (could be made optional)
            if move.location_id.usage == 'internal' and move.location_dest_id.usage != 'internal' and cost_method == 'average' and move.move_returned_from:
                move_orig = move.move_returned_from
                new_price = uom_obj._compute_price(cr, uid, move_orig.product_uom, move_orig.price_unit, product.uom_id.id)
                if (product_avail[product.id]- product_uom_qty) >= 0.0:
                    amount_unit = product.standard_price
                    new_std_price = ((amount_unit * product_avail[product.id])\
                                     - (new_price * product_uom_qty))/(product_avail[product.id] - product_uom_qty)
                    self.write(cr, uid, [move.id],{'price_unit': move_orig.price_unit,})
                    product_obj.write(cr, uid, [product.id], {'standard_price': new_std_price}, context=ctx)
                product_avail[product.id] -= product_uom_qty
        return res

    # FIXME: needs refactoring, this code is partially duplicated in stock_picking.do_partial()!
    def do_partial(self, cr, uid, ids, partial_datas, context=None):
        """ Makes partial pickings and moves done.
        @param partial_datas: Dictionary containing details of partial picking
                          like partner_id, delivery_date, delivery
                          moves with product_id, product_qty, uom
        """
        res = {}
        picking_obj = self.pool.get('stock.picking')
        product_obj = self.pool.get('product.product')
        currency_obj = self.pool.get('res.currency')
        uom_obj = self.pool.get('product.uom')
        wf_service = netsvc.LocalService("workflow")

        if context is None:
            context = {}

        complete, too_many, too_few = [], [], []
        move_product_qty, prodlot_ids, partial_qty, product_uoms = {}, {}, {}, {}
        for move in self.browse(cr, uid, ids, context=context):
            if move.state in ('done', 'cancel'):
                continue
            partial_data = partial_datas.get('move%s'%(move.id), {})
            product_qty = partial_data.get('product_qty',0.0)
            move_product_qty[move.id] = product_qty
            product_uom = partial_data.get('product_uom',False)
            product_price = partial_data.get('product_price',0.0)
            product_currency = partial_data.get('product_currency',False)
            prodlot_id = partial_data.get('prodlot_id')
            prodlot_ids[move.id] = prodlot_id
            product_uoms[move.id] = product_uom
            partial_qty[move.id] = uom_obj._compute_qty(cr, uid, product_uoms[move.id], product_qty, move.product_uom.id)
            if move.product_qty == partial_qty[move.id]:
                complete.append(move)
            elif move.product_qty > partial_qty[move.id]:
                too_few.append(move)
            else:
                too_many.append(move)

        for move in too_few:
            product_qty = move_product_qty[move.id]
            if product_qty != 0:
                defaults = {
                            'product_qty' : product_qty,
                            'product_uos_qty': product_qty,
                            'picking_id' : move.picking_id.id,
                            'state': 'assigned',
                            'move_dest_id': False,
                            'price_unit': product_price,
                            }
                prodlot_id = prodlot_ids[move.id]
                if prodlot_id:
                    defaults.update(prodlot_id=prodlot_id)
                new_move = self.copy(cr, uid, move.id, defaults)
                complete.append(self.browse(cr, uid, new_move))
            self.write(cr, uid, [move.id],
                    {
                        'product_qty': move.product_qty - product_qty,
                        'product_uos_qty': move.product_qty - product_qty,
                        'prodlot_id': False,
                        'tracking_id': False,
                    })


        for move in too_many:
            self.write(cr, uid, [move.id],
                    {
                        'product_qty': move.product_qty,
                        'product_uos_qty': move.product_qty,
                    })
            complete.append(move)

        for move in complete:
            if prodlot_ids.get(move.id):
                self.write(cr, uid, [move.id],{'prodlot_id': prodlot_ids.get(move.id)})
            self.action_done(cr, uid, [move.id], context=context)
            if  move.picking_id.id :
                # TOCHECK : Done picking if all moves are done
                cr.execute("""
                    SELECT move.id FROM stock_picking pick
                    RIGHT JOIN stock_move move ON move.picking_id = pick.id AND move.state = %s
                    WHERE pick.id = %s""",
                            ('done', move.picking_id.id))
                res = cr.fetchall()
                if len(res) == len(move.picking_id.move_lines):
                    picking_obj.action_move(cr, uid, [move.picking_id.id])
                    wf_service.trg_validate(uid, 'stock.picking', move.picking_id.id, 'button_done', cr)

        return [move.id for move in complete]

class stock_inventory(osv.osv):
    _inherit = "stock.inventory"

    def action_confirm(self, cr, uid, ids, context=None):
        """ Confirm the inventory and writes its finished date
        @return: True
        """
        if context is None:
            context = {}
        # to perform the correct inventory corrections we need analyze stock location by
        # location, never recursively, so we use a special context
        product_context = dict(context, compute_child=False)

        location_obj = self.pool.get('stock.location')
        for inv in self.browse(cr, uid, ids, context=context):
            move_ids = []
            for line in inv.inventory_line_id:
                pid = line.product_id.id
                product_context.update(uom=line.product_uom.id, to_date=inv.date, date=inv.date, prodlot_id=line.prod_lot_id.id)
                amount = location_obj._product_get(cr, uid, line.location_id.id, [pid], product_context)[pid]
                change = line.product_qty - amount
                lot_id = line.prod_lot_id.id
                if change:
                    location_id = line.product_id.property_stock_inventory.id
                    value = {
                        'name': _('INV:') + (line.inventory_id.name or ''),
                        'product_id': line.product_id.id,
                        'product_uom': line.product_uom.id,
                        'prodlot_id': lot_id,
                        'date': inv.date,
                        'company_id': line.location_id.company_id.id
                    }

                    if change > 0:
                        value.update( {
                            'product_qty': change,
                            'location_id': location_id,
                            'location_dest_id': line.location_id.id,
                        })
                    else:
                        value.update( {
                            'product_qty': -change,
                            'location_id': line.location_id.id,
                            'location_dest_id': location_id,
                        })
                    move_ids.append(self._inventory_line_hook(cr, uid, line, value))
            self.write(cr, uid, [inv.id], {'state': 'confirm', 'move_ids': [(6, 0, move_ids)]})
            self.pool.get('stock.move').action_confirm(cr, uid, move_ids, context=context)
        return True


# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
