# -*- coding: utf-8 -*-
##############################################################################
#
#    Author: Guewen Baconnier
#    Copyright 2013 Camptocamp SA
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
import unittest2
from functools import partial

from openerp.tools import DEFAULT_SERVER_DATE_FORMAT as D_FMT
import openerp.tests.common as common
from . import logistic_requisition
from . import purchase_requisition
from . import purchase_order


class test_sale_order_from_lr_confirm(common.TransactionCase):
    """ Test the confirmation of a sale order created by a logistic
    requisition.

    According to the type of products (make to stock, make to order),
    the behavior when confirming a sale order line is different.
    """

    def setUp(self):
        super(test_sale_order_from_lr_confirm, self).setUp()
        self.purch_req_model = self.registry('purchase.requisition')
        self.log_req_model = self.registry('logistic.requisition')
        self.log_req_line_model = self.registry('logistic.requisition.line')
        self.sale_model = self.registry('sale.order')
        self.purchase_model = self.registry('purchase.order')
        data_model = self.registry('ir.model.data')
        self.get_ref = partial(data_model.get_object_reference,
                               self.cr, self.uid)
        __, self.partner_1 = self.get_ref('base', 'res_partner_1')
        __, self.partner_3 = self.get_ref('base', 'res_partner_3')
        __, self.partner_4 = self.get_ref('base', 'res_partner_4')
        __, self.user_demo = self.get_ref('base', 'user_demo')
        # Computer Case: make_to_order
        __, self.product_16 = self.get_ref('product', 'product_product_16')
        __, self.product_uom_pce = self.get_ref('product', 'product_uom_unit')
        __, self.pricelist_sale = self.get_ref('product', 'list0')
        self.vals = {
            'partner_id': self.partner_4,
            'consignee_id': self.partner_3,
            'date_delivery': time.strftime(D_FMT),
            'user_id': self.user_demo,
            'pricelist_id': self.pricelist_sale,
        }

        self.line1 = {
            'product_id': self.product_16,  # MTO
            'requested_qty': 100,
            'requested_uom_id': self.product_uom_pce,
            'date_delivery': time.strftime(D_FMT),
            'account_code': '1234',
        }
        self.source1 = {
            'proposed_qty': 100,
            'proposed_product_id': self.product_16,
            'proposed_uom_id': self.product_uom_pce,
            'unit_cost': 10,
            'transport_applicable': 0,
            'procurement_method': 'procurement',
            'price_is': 'estimated',
        }

    def test_mto_generate_po(self):
        """ The purchase requisition must generate the purchase orders on confirmation of sale order.

        When a logistic requisition creates a sale order with MTO lines,
        the confirmation of the lines should generates the purchase
        orders on the purchase requisition linked to the logistic
        requisition lines.
        """
        cr, uid = self.cr, self.uid
        requisition_id = logistic_requisition.create(self, self.vals)
        line_id = logistic_requisition.add_line(self, requisition_id, self.line1)
        source_id = logistic_requisition.add_source(self, line_id, self.source1)
        logistic_requisition.confirm(self, requisition_id)
        logistic_requisition.assign_lines(self, [line_id], self.user_demo)
        purch_req_id = logistic_requisition.create_purchase_requisition(
            self, source_id)
        purchase_requisition.confirm_call(self, purch_req_id)
        bid, bid_line = purchase_requisition.create_draft_purchase_order(
            self, purch_req_id, self.partner_1)
        bid_line.write({'price_unit': 10})
        purchase_order.select_line(self, bid_line.id, 100)
        purchase_order.bid_encoded(self, bid.id)
        purchase_requisition.close_call(self, purch_req_id)
        purchase_requisition.bids_selected(self, purch_req_id)
        logistic_requisition.source_lines(self, [line_id])
        sale_id, __ = logistic_requisition.create_quotation(
            self, requisition_id, [line_id])
        # the confirmation of the sale order should generate the
        # purchase order of the purchase requisition
        self.sale_model.action_button_confirm(cr, uid, [sale_id])
        purch_req = self.purch_req_model.browse(cr, uid, purch_req_id)
        self.assertEquals(purch_req.state,
                          'done',
                          "The purchase requisition should be in 'done' state.")
        self.assertEquals(len(purch_req.purchase_ids), 1,
                          "We should have only 1 purchase order.")

    def test_mto_sales_order_line_per_source_line(self):
        """ 1 sales order line is generated for each source line """
        cr, uid = self.cr, self.uid
        requisition_id = logistic_requisition.create(self, self.vals)
        line_id = logistic_requisition.add_line(self, requisition_id, self.line1)
        source_id = logistic_requisition.add_source(self, line_id, self.source1)
        logistic_requisition.confirm(self, requisition_id)
        logistic_requisition.assign_lines(self, [line_id], self.user_demo)
        purch_req_id = logistic_requisition.create_purchase_requisition(
            self, source_id)
        purchase_requisition.confirm_call(self, purch_req_id)
        # create 2 purchase requisitions
        bid1, bid_line1 = purchase_requisition.create_draft_purchase_order(
            self, purch_req_id, self.partner_1)
        bid_line1.write({'price_unit': 10})
        purchase_order.select_line(self, bid_line1.id, 60)
        purchase_order.bid_encoded(self, bid1.id)

        bid2, bid_line2 = purchase_requisition.create_draft_purchase_order(
            self, purch_req_id, self.partner_3)
        bid_line2.write({'price_unit': 10})
        purchase_order.select_line(self, bid_line2.id, 40)
        purchase_order.bid_encoded(self, bid2.id)

        purchase_requisition.close_call(self, purch_req_id)
        purchase_requisition.bids_selected(self, purch_req_id)
        logistic_requisition.source_lines(self, [line_id])
        sale_id, sale_line_ids = logistic_requisition.create_quotation(
            self, requisition_id, [line_id])
        self.assertEquals(len(sale_line_ids), 2,
                          "We should have one sales order line per "
                          "logistic requisition source")
        sale_line_obj = self.registry('sale.order.line')
        sale_lines = sale_line_obj.browse(cr, uid, sale_line_ids)
        lrl_obj = self.registry('logistic.requisition.line')
        line = lrl_obj.browse(cr, uid, line_id)
        self.assertEquals(len(line.source_ids), 2)
        self.assertEquals(sorted([line.source_ids[0].id, line.source_ids[1].id]),
                          sorted([sl.logistic_requisition_source_id.id for sl
                                  in sale_lines]))
