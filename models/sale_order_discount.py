# -*- coding: utf-8 -*-
###############################################################################
#
#    Odoo, Open Source Management Solution
#    Copyright (C) 2017 Humanytek (<www.humanytek.com>).
#    Rubén Bravo <rubenred18@gmail.com>
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
###############################################################################

from odoo import fields, models, api
from odoo.addons import decimal_precision as dp


class Sale_order_discount(models.Model):
    _inherit = 'sale.order'

    discount_type = fields.Selection(
                                     [('percent', 'Percentage')],
                                      string='Discount Type',
                                      help='Select discount type',
                                      default='percent')

    amount_subtotal = fields.Float('Subtotal', store=True, readonly=True,
                                    compute='_amount_all',
                                    track_visibility='onchange',
                                    digits=dp.get_precision('Product Price 2'))

    @api.multi
    def _amount_all(self):
        """
        Compute the total amounts of the SO.
        """

        for order in self:
            amount_untaxed = amount_tax = amount_discount = 0.0
            for line in order.order_line:
                amount_untaxed += line.price_subtotal
                amount_tax += line.price_tax
            amount_discount = amount_untaxed * self.discount_rate / 100
            if self.discount_rate > 0:
                amount_tax = amount_tax - amount_tax * self.discount_rate / 100
        order.update({
                'amount_untaxed': amount_untaxed,
                'amount_tax': amount_tax,
                'amount_discount': amount_discount,
                'amount_total': amount_untaxed - amount_discount + amount_tax,
                'amount_subtotal': amount_untaxed - amount_discount,
            })
