##############################################################################
#    
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2004-2010 Tiny SPRL (<http://tiny.be>).
#    Copyright (C) 2010-2011 OpenERP S.A. (<http://www.openerp.com>).
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

class product_product(osv.osv):
    _name = 'product.product'
    _inherit = 'product.product'
    

    def write(self, cr, uid, ids, vals, context=None):
        res = super(product_product, self).write(cr, uid, ids, vals, context=context)
        if isinstance(ids, (int, long)):
          ids = [ids]
        bom_obj = self.pool.get("mrp.bom")
        if 'standard_price' in vals:
            for product in self.browse(cr, uid, ids, context=context):
                #Compute price for every product whose bom has this product
                bom_ids = bom_obj.search(cr, uid, [('product_id', '=', product.id), ('bom_id', '!=', False)], context=context)
                if bom_ids:
                    bom_recs = bom_obj.browse(cr, uid, bom_ids, context=context)
                    product_ids = list(set([x.bom_id.product_id.id for x in bom_recs]))
                    self.compute_price(cr, uid, product_ids, recursive = True, real_time_accounting=True, context=context)
        return res

    def compute_price(self, cr, uid, ids, recursive=False, test=False, real_time_accounting = False, context=None):
        '''
        Will return test dict when the test = False
        Multiple ids at once?
        testdict is used to inform the user about the changes to be made
        '''
        testdict = {}
        for prod_id in ids:
            bom_obj = self.pool.get('mrp.bom')
            bom_ids = bom_obj.search(cr, uid, [('bom_id', '=', False), ('product_id','=', prod_id), ('bom_lines', '!=', False)], context=context)
            if bom_ids:
                bom_id = bom_ids[0]
                # In recursive mode, it will first compute the prices of child boms
                if recursive:
                    #Search the products that are components of this bom of prod_id
                    boms = bom_obj.search(cr, uid, [('bom_id', '=', bom_id)], context=context)
                    #Call compute_price on these subproducts
                    prod_set = set([x.product_id.id for x in bom_obj.browse(cr, uid, boms, context=context)])
                    res = self.compute_price(cr, uid, list(prod_set), recursive=recursive, test=test, real_time_accounting = real_time_accounting, context=context)
                    if test: 
                        testdict.update(res)
                #Use calc price to calculate and put the price on the product of the BoM if necessary
                price = self._calc_price(cr, uid, bom_obj.browse(cr, uid, bom_id, context=context), test=test, real_time_accounting = real_time_accounting, context=context)
                if test:
                    testdict.update({prod_id : price})
        if test:
            return testdict
        else:
            return True


    def _calc_price(self, cr, uid, bom, test = False, real_time_accounting=False, context=None):
        if context is None:
            context={}
        price = 0
        uom_obj = self.pool.get("product.uom")
        if bom.bom_lines:
            for sbom in bom.bom_lines:
                my_qty = sbom.bom_lines and 1.0 or sbom.product_qty
                price += uom_obj._compute_price(cr, uid, sbom.product_id.uom_id.id, sbom.product_id.standard_price, sbom.product_uom.id) * my_qty
        #Convert on product UoM quantities
        if price > 0:
            price = uom_obj._compute_price(cr, uid, bom.product_uom.id, price / bom.product_qty, bom.product_id.uom_id.id)
            product = self.pool.get("product.product").browse(cr, uid, bom.product_id.id, context=context)
            if product.cost_method == "standard" and not test:
                if (product.valuation != "real_time" or not real_time_accounting):
                    self.write(cr, uid, [bom.product_id.id], {'standard_price' : price}, context=context)
                else:
                    #Call wizard function here
                    wizard_obj = self.pool.get("stock.change.standard.price")
                    ctx = context.copy()
                    ctx.update({'active_id': bom.product_id.id})
                    if price != bom.product_id.standard_price:
                        wiz_id = wizard_obj.create(cr, uid, {'new_price': price}, context=ctx)
                        wizard_obj.change_price(cr, uid, [wiz_id], context=ctx) #active_id
        return price

class product_bom(osv.osv):
    _inherit = 'mrp.bom'
            
    _columns = {
        'standard_price': fields.related('product_id','standard_price',type="float",relation="product.product",string="Standard Price",store=False)
    }

product_bom()

class stock_move(osv.osv):
    _inherit = 'stock.move'
    
    def action_done(self, cr, uid, ids, context=None):
        bom_obj = self.pool.get("mrp.bom")
        uom_obj = self.pool.get("product.uom")
        for move in self.browse(cr, uid, ids, context=context):
            if (move.location_id.usage == 'production' and move.location_dest_id.usage == 'internal' and move.production_id and move.product_id.cost_method in ['fifo', 'lifo']):
                bom = move.production_id.bom_id
                if bom.bom_lines:
                    cost = 0.0 
                    for line in bom.bom_lines:
                        cost += uom_obj._compute_price(cr, uid, line.product_id.uom_id.id, line.product_id.standard_price, line.product_uom.id) * line.product_qty
                    #Write price (product_uom should be correct)if you have a database of some years old with a product with a lot of moves, this will 
                    self.write(cr, uid, [move.id], {'price_unit': cost / bom.product_qty})
        return super(stock_move, self).action_done(cr, uid, ids, context=context)

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4: