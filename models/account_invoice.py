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


class AccountInvoice(models.Model):
    _inherit = 'account.invoice'

    amount_subtotal = fields.Float('Subtotal', store=True, readonly=True,
                                    compute='_compute_amount',
                                    track_visibility='onchange',
                                    digits=dp.get_precision('Product Price 2'))

    @api.one
    @api.depends('discount_type','discount_rate','amount_total')
    def _compute_discount(self):
        amount_untaxed = sum(line.price_subtotal for line in self.invoice_line_ids)
        amount_discount = amount_untaxed * self.discount_rate / 100
        amount_tax = sum(line.amount for line in self.tax_line_ids)
        amount_tax = amount_tax - amount_tax * self.discount_rate / 100
        self.amount_untaxed = amount_untaxed
        self.amount_discount = amount_discount
        self.amount_tax = amount_tax
        self.amount_subtotal = amount_untaxed - amount_discount
        self.amount_total = amount_untaxed - amount_discount + amount_tax

    @api.one
    @api.depends('invoice_line_ids.price_subtotal', 'tax_line_ids.amount', 'currency_id', 'company_id', 'date_invoice', 'type')
    def _compute_amount(self):
        #self.amount_untaxed = sum(line.price_subtotal for line in self.invoice_line_ids)
        amount_untaxed = sum(line.price_subtotal for line in self.invoice_line_ids)
        amount_discount = amount_untaxed * self.discount_rate / 100
        amount_tax = sum(line.amount for line in self.tax_line_ids)
        amount_tax = amount_tax - amount_tax * self.discount_rate / 100
        self.amount_untaxed = amount_untaxed
        self.amount_discount = amount_discount
        self.amount_tax = amount_tax
        self.amount_subtotal = amount_untaxed - amount_discount
        self.amount_total = amount_untaxed - amount_discount + amount_tax

        #self.amount_tax = sum(line.amount for line in self.tax_line_ids)
        #self.amount_total = self.amount_untaxed + self.amount_tax
        amount_total_company_signed = self.amount_total
        amount_untaxed_signed = self.amount_untaxed
        if self.currency_id and self.company_id and self.currency_id != self.company_id.currency_id:
            currency_id = self.currency_id.with_context(date=self.date_invoice)
            amount_total_company_signed = currency_id.compute(self.amount_total, self.company_id.currency_id)
            amount_untaxed_signed = currency_id.compute(self.amount_untaxed, self.company_id.currency_id)
        sign = self.type in ['in_refund', 'out_refund'] and -1 or 1
        self.amount_total_company_signed = amount_total_company_signed * sign
        self.amount_total_signed = self.amount_total * sign
        self.amount_untaxed_signed = amount_untaxed_signed * sign