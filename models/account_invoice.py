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
from odoo.tools import float_is_zero
import logging
_logger = logging.getLogger(__name__)


class AccountInvoice(models.Model):
    _inherit = 'account.invoice'

    amount_subtotal = fields.Float('Subtotal', store=False, readonly=True,
                                    compute='_compute_amount',
                                    track_visibility='onchange',
                                    digits=dp.get_precision('Product Price 2'))

    @api.one
    @api.depends('discount_type', 'discount_rate', )
    def _compute_discount(self):
        amount_untaxed = sum(line.price_subtotal for line in self.invoice_line_ids)
        amount_discount = amount_untaxed * self.discount_rate / 100
        amount_tax = sum(line.amount for line in self.tax_line_ids)
        self.amount_untaxed = amount_untaxed
        self.amount_discount = amount_discount
        self.amount_tax = amount_tax
        self.amount_subtotal = amount_untaxed - amount_discount
        self.amount_total = amount_untaxed - amount_discount + amount_tax

    @api.one
    @api.depends('invoice_line_ids.price_subtotal', 'tax_line_ids.amount',
                'currency_id', 'company_id', 'date_invoice', 'type')
    def _compute_amount(self):
        amount_untaxed = sum(line.price_subtotal for line in self.invoice_line_ids)
        amount_discount = amount_untaxed * self.discount_rate / 100
        amount_tax = sum(line.amount for line in self.tax_line_ids)
        #amount_tax = amount_tax - amount_tax * self.discount_rate / 100
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


    @api.multi
    def get_taxes_values(self):
        tax_grouped = {}
        for line in self.invoice_line_ids:
            price_unit = line.price_unit * (1 - (line.discount or 0.0) / 100.0) * (1 - (self.discount_rate or 0.0) / 100.0)
            #price_unit = line.price_unit * (1 - (line.discount or 0.0) / 100.0)
            taxes = line.invoice_line_tax_ids.compute_all(price_unit, self.currency_id, line.quantity, line.product_id, self.partner_id)['taxes']
            for tax in taxes:
                val = self._prepare_tax_line_vals(line, tax)
                key = self.env['account.tax'].browse(tax['id']).get_grouping_key(val)
                if val['amount']:
                    val['amount'] = val['amount']
                    _logger.info(val['amount'])
                if key not in tax_grouped:
                    tax_grouped[key] = val
                else:
                    tax_grouped[key]['amount'] += val['amount']
                    tax_grouped[key]['base'] += val['base']
        return tax_grouped

#   NEW
    @api.model
    def invoice_line_move_line_get(self):
        res = []
        for line in self.invoice_line_ids:
            if line.quantity==0:
                continue
            tax_ids = []
            for tax in line.invoice_line_tax_ids:
                tax_ids.append((4, tax.id, None))
                for child in tax.children_tax_ids:
                    if child.type_tax_use != 'none':
                        tax_ids.append((4, child.id, None))
            analytic_tag_ids = [(4, analytic_tag.id, None) for analytic_tag in line.analytic_tag_ids]
            move_line_dict = {
                'invl_id': line.id,
                'type': 'src',
                'name': line.name.split('\n')[0][:64],
                'price_unit': line.price_unit - (line.price_unit * self.discount_rate / 100),
                #'price_unit': line.price_unit,
                'quantity': line.quantity,
                'price': line.price_subtotal  - (line.price_subtotal * self.discount_rate / 100),
                #'price': line.price_subtotal,
                'account_id': line.account_id.id,
                'product_id': line.product_id.id,
                'uom_id': line.uom_id.id,
                'account_analytic_id': line.account_analytic_id.id,
                'tax_ids': tax_ids,
                'invoice_id': self.id,
                'analytic_tag_ids': analytic_tag_ids
            }
            if line['account_analytic_id']:
                move_line_dict['analytic_line_ids'] = [(0, 0, line._get_analytic_line())]
            res.append(move_line_dict)
        return res

    @api.one
    @api.depends(
        'state', 'currency_id', 'invoice_line_ids.price_subtotal',
        'move_id.line_ids.amount_residual',
        'move_id.line_ids.currency_id')
    def _compute_residual(self):
        residual = 0.0
        residual_company_signed = 0.0
        sign = self.type in ['in_refund', 'out_refund'] and -1 or 1
        for line in self.sudo().move_id.line_ids:
            if line.account_id.internal_type in ('receivable', 'payable'):
                residual_company_signed += line.amount_residual
                if line.currency_id == self.currency_id:
                    residual += line.amount_residual_currency if line.currency_id else line.amount_residual
                else:
                    from_currency = (line.currency_id and line.currency_id.with_context(date=line.date)) or line.company_id.currency_id.with_context(date=line.date)
                    residual += from_currency.compute(line.amount_residual, self.currency_id)
        if self.state == 'draft':
            self.residual_company_signed = abs(residual_company_signed) * sign - self.amount_discount
            self.residual_signed = abs(residual) * sign - self.amount_discount
            self.residual = abs(residual) - self.amount_discount
        else:
            self.residual_company_signed = abs(residual_company_signed) * sign
            self.residual_signed = abs(residual) * sign
            self.residual = abs(residual)

        digits_rounding_precision = self.currency_id.rounding
        if float_is_zero(self.residual, precision_rounding=digits_rounding_precision):
            self.reconciled = True
        else:
            self.reconciled = False