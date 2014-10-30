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

from openerp.osv import osv,fields

class account_invoice_line(osv.osv):
    _inherit = "account.invoice.line"

    """ Override account_invoice_line to add the link to the purchase order line it is related to"""
    _columns = {
        'purchase_line_id': fields.many2one('purchase.order.line',
            'Purchase Order Line', ondelete='set null', select=True,
            readonly=True),
    }

    def move_line_get(self, cr, uid, invoice_id, context=None):
        res = []
        tax_obj = self.pool.get('account.tax')
        cur_obj = self.pool.get('res.currency')
        if context is None:
            context = {}
        inv = self.pool.get('account.invoice').browse(cr, uid, invoice_id, context=context)
        company_currency = self.pool['res.company'].browse(cr, uid, inv.company_id.id).currency_id.id
        for line in inv.invoice_line:
            mres = self.move_line_get_item(cr, uid, line, context)
            if not mres:
                continue
            res.append(mres)
            tax_code_found= False
            for tax in tax_obj.compute_all(cr, uid, line.invoice_line_tax_id,
                    (line.price_unit * (1.0 - (line['discount'] or 0.0) / 100.0)),
                    line.quantity, line.product_id,
                    inv.partner_id)['taxes']:

                if inv.type in ('out_invoice', 'in_invoice'):
                    tax_code_id = tax['base_code_id']
                    tax_amount = line.price_subtotal * tax['base_sign']
                else:
                    tax_code_id = tax['ref_base_code_id']
                    tax_amount = line.price_subtotal * tax['ref_base_sign']

                if tax_code_found:
                    if not tax_code_id:
                        continue
                    res.append(self.move_line_get_item(cr, uid, line, context))
                    res[-1]['price'] = 0.0
                    res[-1]['account_analytic_id'] = False
                elif not tax_code_id:
                    continue
                tax_code_found = True

                res[-1]['tax_code_id'] = tax_code_id
                res[-1]['tax_amount'] = cur_obj.compute(cr, uid, inv.currency_id.id, company_currency, tax_amount, context={'date': inv.date_invoice})
        
        def get_price(cr, uid, inv, company_currency,i_line):
            cur_obj = self.pool.get('res.currency')
            if inv.currency_id.id != company_currency:
                price = cur_obj.compute(cr, uid, company_currency, inv.currency_id.id, i_line.product_id.standard_price * i_line.quantity, context={'date': inv.date_invoice})
            else:
                price = i_line.product_id.standard_price * i_line.quantity
            return price

        if inv.type in ('out_invoice','out_refund'):
            for i_line in inv.invoice_line:
                if i_line.product_id and i_line.product_id.valuation == 'real_time':
                    if inv.type == 'out_invoice':
                        # debit account dacc will be the output account
                        # first check the product, if empty check the category
                        dacc = i_line.product_id.property_stock_account_output and i_line.product_id.property_stock_account_output.id
                        if not dacc:
                            dacc = i_line.product_id.categ_id.property_stock_account_output_categ and i_line.product_id.categ_id.property_stock_account_output_categ.id
                    else:
                        # = out_refund
                        # debit account dacc will be the input account
                        # first check the product, if empty check the category
                        dacc = i_line.product_id.property_stock_account_input and i_line.product_id.property_stock_account_input.id
                        if not dacc:
                            dacc = i_line.product_id.categ_id.property_stock_account_input_categ and i_line.product_id.categ_id.property_stock_account_input_categ.id
                    # in both cases the credit account cacc will be the expense account
                    # first check the product, if empty check the category
                    cacc = i_line.product_id.property_account_expense and i_line.product_id.property_account_expense.id
                    if not cacc:
                        cacc = i_line.product_id.categ_id.property_account_expense_categ and i_line.product_id.categ_id.property_account_expense_categ.id
                    if dacc and cacc:
                        res.append({
                            'type':'src',
                            'name': i_line.name[:64],
                            'price_unit':i_line.product_id.standard_price,
                            'quantity':i_line.quantity,
                            'price':get_price(cr, uid, inv, company_currency, i_line),
                            'account_id':dacc,
                            'product_id':i_line.product_id.id,
                            'uos_id':i_line.uos_id.id,
                            'account_analytic_id': False,
                            'taxes':i_line.invoice_line_tax_id,
                            })

                        res.append({
                            'type':'src',
                            'name': i_line.name[:64],
                            'price_unit':i_line.product_id.standard_price,
                            'quantity':i_line.quantity,
                            'price': -1 * get_price(cr, uid, inv, company_currency, i_line),
                            'account_id':cacc,
                            'product_id':i_line.product_id.id,
                            'uos_id':i_line.uos_id.id,
                            'account_analytic_id': False,
                            'taxes':i_line.invoice_line_tax_id,
                            })
        elif inv.type in ('in_invoice','in_refund'):
            for i_line in inv.invoice_line:
                if i_line.product_id and i_line.product_id.valuation == 'real_time':
                    if i_line.product_id.type != 'service':
                        # get the price difference account at the product
                        acc = i_line.product_id.property_account_creditor_price_difference and i_line.product_id.property_account_creditor_price_difference.id
                        if not acc:
                            # if not found on the product get the price difference account at the category
                            acc = i_line.product_id.categ_id.property_account_creditor_price_difference_categ and i_line.product_id.categ_id.property_account_creditor_price_difference_categ.id
                        a = None
                        if inv.type == 'in_invoice':
                            # oa will be the stock input account
                            # first check the product, if empty check the category
                            oa = i_line.product_id.property_stock_account_input and i_line.product_id.property_stock_account_input.id
                            if not oa:
                                oa = i_line.product_id.categ_id.property_stock_account_input_categ and i_line.product_id.categ_id.property_stock_account_input_categ.id
                        else:
                            # = in_refund
                            # oa will be the stock output account
                            # first check the product, if empty check the category
                            oa = i_line.product_id.property_stock_account_output and i_line.product_id.property_stock_account_output.id
                            if not oa:
                                oa = i_line.product_id.categ_id.property_stock_account_output_categ and i_line.product_id.categ_id.property_stock_account_output_categ.id
                        if oa:
                            # get the fiscal position
                            fpos = i_line.invoice_id.fiscal_position or False
                            a = self.pool.get('account.fiscal.position').map_account(cr, uid, fpos, oa)
                        diff_res = []
                        # calculate and write down the possible price difference between invoice price and product price
                        for line in res:
                            if a == line['account_id'] and i_line.product_id.id == line['product_id']:
                                uom = i_line.product_id.uos_id or i_line.product_id.uom_id
                                valuation_price_unit = self.pool.get('product.uom')._compute_price(cr, uid, uom.id, i_line.product_id.standard_price, i_line.uos_id.id)
                                if i_line.product_id.cost_method != 'standard' and i_line.purchase_line_id:
                                    #for average/fifo/lifo costing method, fetch real cost price from incomming moves
                                    stock_move_obj = self.pool.get('stock.move')
                                    valuation_stock_move = stock_move_obj.search(cr, uid, [('purchase_line_id', '=', i_line.purchase_line_id.id)], limit=1, context=context)
                                    if valuation_stock_move:
                                        valuation_price_unit = stock_move_obj.browse(cr, uid, valuation_stock_move[0], context=context).price_unit
                                if valuation_price_unit != i_line.price_unit and line['price_unit'] == i_line.price_unit and acc:
                                    price_diff = i_line.price_unit - valuation_price_unit
                                    line.update({'price': valuation_price_unit * line['quantity']})
                                    diff_res.append({
                                        'type':'src',
                                        'name': i_line.name[:64],
                                        'price_unit':price_diff,
                                        'quantity':line['quantity'],
                                        'price': price_diff * line['quantity'],
                                        'account_id':acc,
                                        'product_id':line['product_id'],
                                        'uos_id':line['uos_id'],
                                        'account_analytic_id':line['account_analytic_id'],
                                        'taxes':line.get('taxes',[]),
                                        })
                        res += diff_res
        return res
class purchase_order(osv.osv):
    _inherit = "purchase.order"

    def _prepare_inv_line(self, cr, uid, account_id, order_line, context=None):
        """Collects require data from purchase order line that is used to create invoice line
        for that purchase order line
        :param account_id: Expense account of the product of PO line if any.
        :param browse_record order_line: Purchase order line browse record
        :return: Value for fields of invoice lines.
        :rtype: dict
        """
        return {
            'name': order_line.name,
            'account_id': account_id,
            'price_unit': order_line.price_unit or 0.0,
            'quantity': order_line.product_qty,
            'product_id': order_line.product_id.id or False,
            'uos_id': order_line.product_uom.id or False,
            'invoice_line_tax_id': [(6, 0, [x.id for x in order_line.taxes_id])],
            'account_analytic_id': order_line.account_analytic_id.id or False,
            'purchase_line_id': order_line.id,
        }

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
