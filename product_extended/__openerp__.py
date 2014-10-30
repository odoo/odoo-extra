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
{
    "name" : "Product extension to calculate Bill of Materials",
    "version" : "1.0",
    "author" : "OpenERP S.A.",
    "depends" : ["product", "purchase", "sale", "mrp"],
    "category" : "Generic Modules/Inventory Control",
    "description": """
Product extension. This module adds:
  * When a product's price is changed and is part of a BoM, 
    it will update the price of the BoM with the sum of the cost prices
    of its components
""",
    "init_xml" : [],
    "demo_xml" : [],
    "update_xml" : ["mrp_view.xml"],
    "active": False,
    "installable": True
}
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:

