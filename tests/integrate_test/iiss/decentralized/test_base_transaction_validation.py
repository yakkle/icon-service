# -*- coding: utf-8 -*-

# Copyright 2019 ICON Foundation
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""IconScoreEngine testcase
"""
import hashlib
import os
from copy import deepcopy

from iconservice.base.address import ZERO_SCORE_ADDRESS, Address
from iconservice.base.block import Block
from iconservice.base.exception import InvalidBaseTransactionException
from iconservice.icon_constant import ISSUE_CALCULATE_ORDER, ISSUE_EVENT_LOG_MAPPER, REV_IISS, \
    ISCORE_EXCHANGE_RATE, REV_DECENTRALIZATION, ICX_IN_LOOP, PREP_MAIN_PREPS, IconScoreContextType
from iconservice.iconscore.icon_score_context import IconScoreContext
from iconservice.icx.issue.base_transaction_creator import BaseTransactionCreator
from iconservice.iiss.reward_calc.ipc.reward_calc_proxy import CalculateResponse
from iconservice.prep.data import PRepContainer, PRepFlag
from tests import create_tx_hash, create_block_hash
from tests.integrate_test import create_timestamp
from tests.integrate_test.iiss.test_iiss_base import TestIISSBase
from tests.integrate_test.test_integrate_base import TOTAL_SUPPLY


class TestIISSBaseTransactionValidation(TestIISSBase):
    def setUp(self):
        super().setUp()

        # decentralized
        self.update_governance()

        # set Revision REV_IISS
        tx: dict = self.create_set_revision_tx(REV_IISS)
        prev_block, tx_results = self._make_and_req_block([tx])
        self._write_precommit_state(prev_block)

        self.public_key_list = [os.urandom(32) for _ in range(PREP_MAIN_PREPS)]
        self._addr_array = [Address.from_bytes(hashlib.sha3_256(public_key[1:]).digest()[-20:])
                            for public_key in self.public_key_array]

        main_preps = self._addr_array[:PREP_MAIN_PREPS]

        total_supply = TOTAL_SUPPLY * ICX_IN_LOOP
        # Minimum_delegate_amount is 0.02 * total_supply
        # In this test delegate 0.03*total_supply because `Issue transaction` exists since REV_IISS
        minimum_delegate_amount_for_decentralization: int = total_supply * 2 // 1000 + 1
        init_balance: int = minimum_delegate_amount_for_decentralization * 10

        # distribute icx PREP_MAIN_PREPS ~ PREP_MAIN_PREPS + PREP_MAIN_PREPS - 1
        tx_list: list = []
        for i in range(PREP_MAIN_PREPS):
            tx: dict = self._make_icx_send_tx(self._genesis,
                                              self._addr_array[PREP_MAIN_PREPS + i],
                                              init_balance)
            tx_list.append(tx)
        prev_block, tx_results = self._make_and_req_block(tx_list)
        for tx_result in tx_results:
            self.assertEqual(int(True), tx_result.status)
        self._write_precommit_state(prev_block)

        # stake PREP_MAIN_PREPS ~ PREP_MAIN_PREPS + PREP_MAIN_PREPS - 1
        stake_amount: int = minimum_delegate_amount_for_decentralization
        tx_list: list = []
        for i in range(PREP_MAIN_PREPS):
            tx: dict = self.create_set_stake_tx(self._addr_array[PREP_MAIN_PREPS + i],
                                                stake_amount)
            tx_list.append(tx)
        prev_block, tx_results = self._make_and_req_block(tx_list)
        for tx_result in tx_results:
            self.assertEqual(int(True), tx_result.status)
        self._write_precommit_state(prev_block)

        # distribute icx for register PREP_MAIN_PREPS ~ PREP_MAIN_PREPS + PREP_MAIN_PREPS - 1
        tx_list: list = []
        for i in range(PREP_MAIN_PREPS):
            tx: dict = self._make_icx_send_tx(self._genesis,
                                              self._addr_array[i],
                                              3000 * ICX_IN_LOOP)
            tx_list.append(tx)
        prev_block, tx_results = self._make_and_req_block(tx_list)
        for tx_result in tx_results:
            self.assertEqual(int(True), tx_result.status)
        self._write_precommit_state(prev_block)

        # register PRep
        tx_list: list = []
        for i, address in enumerate(main_preps):
            tx: dict = self.create_register_prep_tx(address, public_key=f"0x{self.public_key_array[i].hex()}")
            tx_list.append(tx)
        prev_block, tx_results = self._make_and_req_block(tx_list)
        for tx_result in tx_results:
            self.assertEqual(int(True), tx_result.status)
        self._write_precommit_state(prev_block)

        # delegate to PRep
        tx_list: list = []
        for i in range(PREP_MAIN_PREPS):
            tx: dict = self.create_set_delegation_tx(self._addr_array[PREP_MAIN_PREPS + i],
                                                     [
                                                         (
                                                             self._addr_array[i],
                                                             minimum_delegate_amount_for_decentralization
                                                         )
                                                     ])
            tx_list.append(tx)
        prev_block, tx_results = self._make_and_req_block(tx_list)
        for tx_result in tx_results:
            self.assertEqual(int(True), tx_result.status)
        self._write_precommit_state(prev_block)

        # get main prep
        response: dict = self.get_main_prep_list()
        expected_response: dict = {
            "preps": [],
            "totalDelegated": 0
        }
        self.assertEqual(expected_response, response)

        # set Revision REV_IISS (decentralization)
        tx: dict = self.create_set_revision_tx(REV_DECENTRALIZATION)
        prev_block, tx_results = self._make_and_req_block([tx])
        self._write_precommit_state(prev_block)

        # get main prep
        response: dict = self.get_main_prep_list()
        expected_preps: list = []
        expected_total_delegated: int = 0
        for address in main_preps:
            expected_preps.append({
                'address': address,
                'delegated': minimum_delegate_amount_for_decentralization
            })
            expected_total_delegated += minimum_delegate_amount_for_decentralization
        expected_response: dict = {
            "preps": expected_preps,
            "totalDelegated": expected_total_delegated
        }
        self.assertEqual(expected_response, response)

        custom_delegate: int = 1 * ICX_IN_LOOP
        # delegate to PRep 0
        tx_list: list = []
        for i in range(PREP_MAIN_PREPS):
            tx: dict = self.create_set_delegation_tx(self._addr_array[PREP_MAIN_PREPS + i],
                                                     [
                                                         (
                                                             self._addr_array[i],
                                                             custom_delegate
                                                         )
                                                     ])
            tx_list.append(tx)
        prev_block, tx_results = self._make_and_req_block(tx_list)
        for tx_result in tx_results:
            self.assertEqual(int(True), tx_result.status)
        self._write_precommit_state(prev_block)

        self.make_blocks_to_next_calculation()

        # get main prep
        response: dict = self.get_main_prep_list()
        expected_preps: list = []
        for address in main_preps:
            expected_preps.append({
                'address': address,
                'delegated': custom_delegate
            })
        expected_response: dict = {
            "preps": expected_preps,
            "totalDelegated": custom_delegate * PREP_MAIN_PREPS
        }
        self.assertEqual(expected_response, response)

    def _make_base_tx(self, data: dict):
        timestamp_us = create_timestamp()

        request_params = {
            "version": self._version,
            "timestamp": timestamp_us,
            "dataType": "base",
            "data": data
        }
        method = 'icx_sendTransaction'
        request_params['txHash'] = create_tx_hash()
        tx = {
            'method': method,
            'params': request_params
        }

        return tx

    def _create_dummy_tx(self):
        return self._make_icx_send_tx(self._genesis, self._admin, 0)

    def _make_issue_info(self) -> tuple:
        context = IconScoreContext(IconScoreContextType.DIRECT)
        context.preps: 'PRepContainer' = context.engine.prep.preps.copy(PRepFlag.NONE)
        block_height: int = self._block_height
        block_hash = create_block_hash()
        timestamp_us = create_timestamp()
        block = Block(block_height, block_hash, timestamp_us, self._prev_block_hash, 0)
        context.block = block
        issue_data, _ = IconScoreContext.engine.issue.create_icx_issue_info(context)
        total_issue_amount = 0
        for group_dict in issue_data.values():
            if "value" in group_dict:
                total_issue_amount += group_dict["value"]

        return issue_data, total_issue_amount

    def _create_base_transaction(self):
        context = IconScoreContext(IconScoreContextType.DIRECT)
        context.preps: 'PRepContainer' = context.engine.prep.preps.copy(PRepFlag.NONE)
        block_height: int = self._block_height
        block_hash = create_block_hash()
        timestamp_us = create_timestamp()
        block = Block(block_height, block_hash, timestamp_us, self._prev_block_hash, 0)
        context.block = block
        transaction, regulator = BaseTransactionCreator.create_base_transaction(context)
        return transaction

    def test_validate_base_transaction_position(self):
        # isBlockEditable is false in this method
        issue_data, total_issue_amount = self._make_issue_info()

        # failure case: when first transaction is not a issue transaction, should raise error
        invalid_tx_list = [
            self._create_dummy_tx()
        ]
        self.assertRaises(InvalidBaseTransactionException, self._make_and_req_block_for_issue_test, invalid_tx_list)

        # failure case: when first transaction is not a issue transaction
        # but 2nd is a issue transaction, should raise error
        invalid_tx_list = [
            self._create_dummy_tx(),
            self._make_base_tx(issue_data)
        ]
        self.assertRaises(InvalidBaseTransactionException, self._make_and_req_block_for_issue_test, invalid_tx_list)

        # failure case: if there are more than 2 issue transaction, should raise error
        invalid_tx_list = [
            self._make_base_tx(issue_data),
            self._make_base_tx(issue_data)
        ]
        self.assertRaises(KeyError, self._make_and_req_block_for_issue_test, invalid_tx_list)

        # failure case: when there is no issue transaction, should raise error
        invalid_tx_list = [
            self._create_dummy_tx(),
            self._create_dummy_tx(),
            self._create_dummy_tx()
        ]
        self.assertRaises(InvalidBaseTransactionException, self._make_and_req_block_for_issue_test, invalid_tx_list)

    def test_validate_base_transaction_format(self):
        # isBlockEditable is false in this method

        issue_data, total_issue_amount = self._make_issue_info()

        # failure case: when group(i.e. prep, eep, dapp) key in the issue transaction's data is different with
        # stateDB, should raise error

        # less than
        copied_issue_data = deepcopy(issue_data)
        for group_key in issue_data.keys():
            temp = copied_issue_data[group_key]
            del copied_issue_data[group_key]
            tx_list = [
                self._make_base_tx(copied_issue_data),
                self._create_dummy_tx(),
                self._create_dummy_tx()
            ]
            self.assertRaises(InvalidBaseTransactionException, self._make_and_req_block_for_issue_test, tx_list)
            copied_issue_data[group_key] = temp

        # more than
        copied_issue_data = deepcopy(issue_data)
        copied_issue_data['dummy_key'] = {}
        tx_list = [
            self._make_base_tx(copied_issue_data),
            self._create_dummy_tx(),
            self._create_dummy_tx()
        ]
        self.assertRaises(InvalidBaseTransactionException, self._make_and_req_block_for_issue_test, tx_list)

        # failure case: when group's inner data key (i.e. incentiveRep, rewardRep, etc) is different
        # with stateDB (except value), should raise error

        # more than
        copied_issue_data = deepcopy(issue_data)
        for _, data in copied_issue_data.items():
            data['dummy_key'] = ""
            tx_list = [
                self._make_base_tx(copied_issue_data),
                self._create_dummy_tx(),
                self._create_dummy_tx()
            ]
            self.assertRaises(InvalidBaseTransactionException, self._make_and_req_block_for_issue_test, tx_list)
            del data['dummy_key']

        # less than
        copied_issue_data = deepcopy(issue_data)
        for group, data in copied_issue_data.items():
            for key in issue_data[group].keys():
                temp = data[key]
                del data[key]
                tx_list = [
                    self._make_base_tx(copied_issue_data),
                    self._create_dummy_tx(),
                    self._create_dummy_tx()
                ]
                self.assertRaises(InvalidBaseTransactionException, self._make_and_req_block_for_issue_test, tx_list)
                data[key] = temp

    def test_validate_base_transaction_value_editable_block(self):
        issue_data, total_issue_amount = self._make_issue_info()

        expected_step_price = 0
        expected_step_used = 0

        # failure case: when issue transaction invoked even though isBlockEditable is true, should raise error
        # case of isBlockEditable is True
        before_total_supply = self._query({}, "icx_getTotalSupply")
        before_treasury_icx_amount = self._query({"address": self._fee_treasury}, 'icx_getBalance')

        base_transaction = self._create_base_transaction()

        tx_list = [
            base_transaction,
            self._create_dummy_tx(),
            self._create_dummy_tx()
        ]
        self.assertRaises(KeyError,
                          self._make_and_req_block_for_issue_test,
                          tx_list, None, None, None, True, 0)

        # success case: when valid issue transaction invoked, should issue icx according to calculated icx issue amount
        # case of isBlockEditable is True
        tx_list = [
            self._create_dummy_tx(),
            self._create_dummy_tx()
        ]
        prev_block, tx_results = self._make_and_req_block_for_issue_test(tx_list, is_block_editable=True)
        self._write_precommit_state(prev_block)
        expected_tx_status = 1
        expected_failure = None
        expected_trace = []
        self.assertEqual(expected_tx_status, tx_results[0].status)
        self.assertEqual(expected_failure, tx_results[0].failure)
        self.assertEqual(expected_step_price, tx_results[0].step_price)
        self.assertEqual(expected_step_used, tx_results[0].step_used)
        self.assertEqual(expected_trace, tx_results[0].traces)

        for index, group_key in enumerate(ISSUE_CALCULATE_ORDER):
            if group_key not in issue_data:
                continue
            expected_score_address = ZERO_SCORE_ADDRESS
            expected_indexed: list = [ISSUE_EVENT_LOG_MAPPER[group_key]['event_signature']]
            expected_data: list = [issue_data[group_key][key] for key in ISSUE_EVENT_LOG_MAPPER[group_key]['data']]
            self.assertEqual(expected_score_address, tx_results[0].event_logs[index].score_address)
            self.assertEqual(expected_indexed, tx_results[0].event_logs[index].indexed)
            self.assertEqual(expected_data, tx_results[0].event_logs[index].data)

        # event log about correction
        self.assertEqual(0, tx_results[0].event_logs[1].data[0])
        self.assertEqual(0, tx_results[0].event_logs[1].data[1])
        self.assertEqual(total_issue_amount, tx_results[0].event_logs[1].data[2])
        self.assertEqual(0, tx_results[0].event_logs[1].data[3])

        after_total_supply = self._query({}, "icx_getTotalSupply")
        after_treasury_icx_amount = self._query({"address": self._fee_treasury}, 'icx_getBalance')

        self.assertEqual(before_total_supply + total_issue_amount, after_total_supply)
        self.assertEqual(before_treasury_icx_amount + total_issue_amount, after_treasury_icx_amount)

    def test_validate_base_transaction_value_not_editable_block(self):
        issue_data, total_issue_amount = self._make_issue_info()

        expected_step_price = 0
        expected_step_used = 0

        # success case: when valid issue transaction invoked, should issue icx according to calculated icx issue amount
        # case of isBlockEditable is False
        before_total_supply = self._query({}, "icx_getTotalSupply")
        before_treasury_icx_amount = self._query({"address": self._fee_treasury}, 'icx_getBalance')
        base_transaction = self._create_base_transaction()

        tx_list = [
            base_transaction,
            self._create_dummy_tx(),
            self._create_dummy_tx()
        ]
        prev_block, tx_results = self._make_and_req_block_for_issue_test(tx_list, is_block_editable=False)
        self._write_precommit_state(prev_block)
        expected_tx_status = 1
        expected_failure = None
        expected_trace = []
        self.assertEqual(expected_tx_status, tx_results[0].status)
        self.assertEqual(expected_failure, tx_results[0].failure)
        self.assertEqual(expected_step_price, tx_results[0].step_price)
        self.assertEqual(expected_step_used, tx_results[0].step_used)
        self.assertEqual(expected_trace, tx_results[0].traces)

        for index, group_key in enumerate(ISSUE_CALCULATE_ORDER):
            if group_key not in issue_data:
                continue
            expected_score_address = ZERO_SCORE_ADDRESS
            expected_indexed: list = [ISSUE_EVENT_LOG_MAPPER[group_key]['event_signature']]
            expected_data: list = [issue_data[group_key][key] for key in ISSUE_EVENT_LOG_MAPPER[group_key]['data']]
            self.assertEqual(expected_score_address, tx_results[0].event_logs[index].score_address)
            self.assertEqual(expected_indexed, tx_results[0].event_logs[index].indexed)
            self.assertEqual(expected_data, tx_results[0].event_logs[index].data)

        # event log about correction
        self.assertEqual(0, tx_results[0].event_logs[1].data[0])
        self.assertEqual(0, tx_results[0].event_logs[1].data[1])
        self.assertEqual(total_issue_amount, tx_results[0].event_logs[1].data[2])
        self.assertEqual(0, tx_results[0].event_logs[1].data[3])

        after_total_supply = self._query({}, "icx_getTotalSupply")
        after_treasury_icx_amount = self._query({"address": self._fee_treasury}, 'icx_getBalance')

        self.assertEqual(before_total_supply + total_issue_amount, after_total_supply)
        self.assertEqual(before_treasury_icx_amount + total_issue_amount, after_treasury_icx_amount)

    def test_validate_base_transaction_value_corrected_issue_amount(self):
        # success case: when icon service over issued 10 icx than reward carc, icx issue amount
        # should be corrected on calc period.
        calc_period = 10
        calc_point = calc_period
        expected_sequence = 0

        diff_between_is_and_rc = 10 * ISCORE_EXCHANGE_RATE
        cumulative_fee = 10
        first_expected_issue_amount = 2589195129375951183
        calculate_response_iscore = \
            first_expected_issue_amount * calc_period * ISCORE_EXCHANGE_RATE - diff_between_is_and_rc

        expected_issue_amount = 2561944563165905521
        calculate_response_iscore_after_first_period = \
            expected_issue_amount * 10 * ISCORE_EXCHANGE_RATE - diff_between_is_and_rc
        expected_diff_in_calc_period = (expected_issue_amount * calc_period) - \
                                       (calculate_response_iscore_after_first_period // ISCORE_EXCHANGE_RATE)

        def mock_calculated(_self, _path, _block_height):
            response = CalculateResponse(0, True, 1, calculate_response_iscore, b'mocked_response')
            _self._calculation_callback(response)

        self._mock_ipc(mock_calculated)

        tx_list = [
            self._create_dummy_tx(),
            self._create_dummy_tx()
        ]
        for x in range(1, 11):

            copied_tx_list = deepcopy(tx_list)
            prev_block, tx_results = self._make_and_req_block_for_issue_test(copied_tx_list,
                                                                             is_block_editable=True,
                                                                             cumulative_fee=cumulative_fee)
            issue_amount = tx_results[0].event_logs[0].data[3]
            actual_covered_by_fee = tx_results[0].event_logs[1].data[0]
            actual_covered_by_remain = tx_results[0].event_logs[1].data[1]
            actual_issue_amount = tx_results[0].event_logs[1].data[2]
            print(f"=================={x}====================")
            print(tx_results[0].event_logs[0].data)
            print(tx_results[0].event_logs[1].data)
            if x == 1:
                self.assertEqual(0, actual_covered_by_fee)
                self.assertEqual(0, actual_covered_by_remain)
                self.assertEqual(first_expected_issue_amount, actual_issue_amount)
                self.assertEqual(0, tx_results[0].event_logs[1].data[3])

                actual_sequence = tx_results[0].event_logs[2].data[0]
                actual_start_block = tx_results[0].event_logs[2].data[1]
                actual_end_block = tx_results[0].event_logs[2].data[2]
                self.assertEqual(expected_sequence, actual_sequence)
                self.assertEqual(prev_block._height, actual_start_block)
                self.assertEqual(prev_block._height + calc_period - 1, actual_end_block)
                expected_sequence += 1
            elif x == calc_point:
                calc_point += calc_period
            else:
                self.assertEqual(cumulative_fee, actual_covered_by_fee)
                self.assertEqual(0, actual_covered_by_remain)
                self.assertEqual(first_expected_issue_amount - cumulative_fee, actual_issue_amount)
                self.assertEqual(0, tx_results[0].event_logs[1].data[3])
            self.assertEqual(issue_amount, actual_covered_by_fee + actual_covered_by_remain + actual_issue_amount)
            self._write_precommit_state(prev_block)

        calculate_response_iscore = calculate_response_iscore_after_first_period

        for x in range(11, 51):
            copied_tx_list = deepcopy(tx_list)
            prev_block, tx_results = self._make_and_req_block_for_issue_test(copied_tx_list,
                                                                             is_block_editable=True,
                                                                             cumulative_fee=cumulative_fee)
            issue_amount = tx_results[0].event_logs[0].data[3]
            actual_covered_by_fee = tx_results[0].event_logs[1].data[0]
            actual_covered_by_remain = tx_results[0].event_logs[1].data[1]
            actual_issue_amount = tx_results[0].event_logs[1].data[2]
            print(f"=================={x}====================")
            print(tx_results[0].event_logs[0].data)
            print(tx_results[0].event_logs[1].data)
            if x == calc_point:
                self.assertEqual(cumulative_fee, actual_covered_by_fee)
                self.assertEqual(expected_diff_in_calc_period, actual_covered_by_remain)
                self.assertEqual(expected_issue_amount - cumulative_fee - expected_diff_in_calc_period,
                                 actual_issue_amount)
                self.assertEqual(0, tx_results[0].event_logs[1].data[3])
                calc_point += calc_period
            elif x == calc_point - calc_period + 1:
                actual_sequence = tx_results[0].event_logs[2].data[0]
                actual_start_block = tx_results[0].event_logs[2].data[1]
                actual_end_block = tx_results[0].event_logs[2].data[2]
                self.assertEqual(expected_sequence, actual_sequence)
                self.assertEqual(prev_block._height, actual_start_block)
                self.assertEqual(prev_block._height + calc_period - 1, actual_end_block)
                expected_sequence += 1
            else:
                self.assertEqual(cumulative_fee, actual_covered_by_fee)
                self.assertEqual(0, actual_covered_by_remain)
                self.assertEqual(expected_issue_amount - cumulative_fee, actual_issue_amount)
                self.assertEqual(0, tx_results[0].event_logs[1].data[3])
            self.assertEqual(issue_amount, actual_covered_by_fee + actual_covered_by_remain + actual_issue_amount)

            self._write_precommit_state(prev_block)