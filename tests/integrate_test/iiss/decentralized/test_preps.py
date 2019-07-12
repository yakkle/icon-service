# -*- coding: utf-8 -*-

# Copyright 2018 ICON Foundation
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
from iconservice.base.exception import ExceptionCode
from iconservice.base.type_converter_templates import ConstantKeys
from iconservice.icon_constant import REV_IISS, PREP_MAIN_PREPS, ICX_IN_LOOP, REV_DECENTRALIZATION, IISS_INITIAL_IREP, \
    IISS_MAX_IREP_PERCENTAGE
from tests.integrate_test.iiss.test_iiss_base import TestIISSBase
from tests.integrate_test.test_integrate_base import TOTAL_SUPPLY


class TestPreps(TestIISSBase):

    def setUp(self):
        super().setUp()

        # decentralized
        self.update_governance()

        # set Revision REV_IISS
        tx: dict = self.create_set_revision_tx(REV_IISS)
        prev_block, tx_results = self._make_and_req_block([tx])
        self._write_precommit_state(prev_block)

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

        # delegate to PRep 0
        tx_list: list = []
        for i in range(PREP_MAIN_PREPS):
            tx: dict = self.create_set_delegation_tx(self._addr_array[PREP_MAIN_PREPS + i],
                                                     [
                                                         (
                                                             self._addr_array[i],
                                                             0
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
                'delegated': 0
            })
        expected_response: dict = {
            "preps": expected_preps,
            "totalDelegated": 0
        }
        self.assertEqual(expected_response, response)

    def test_prep_rotate(self):
        """
        Scenario
        0. decentralized (All P-Reps have none delegations)
        1. unregisters the first main prep
        2. delegates 10000 loop to the last prep
        3. check main preps sorted
        :return:
        """

        # un-register first main prep
        tx: dict = self.create_unregister_prep_tx(self._addr_array[0])
        prev_block, tx_results = self._make_and_req_block([tx])
        self.assertEqual(int(True), tx_results[0].status)
        self._write_precommit_state(prev_block)

        response: dict = self.get_prep(self._addr_array[0])
        self.assertEqual(1, response['status'])

        # register user[PREP_MAIN_PREPS]
        tx: dict = self.create_register_prep_tx(self._addr_array[PREP_MAIN_PREPS],
                                                public_key=f"0x{self.public_key_array[PREP_MAIN_PREPS].hex()}")
        prev_block, tx_results = self._make_and_req_block([tx])
        self.assertEqual(int(True), tx_results[0].status)
        self._write_precommit_state(prev_block)

        # delegate to PRep
        delegation_amount: int = 10000
        tx: dict = self.create_set_delegation_tx(self._addr_array[PREP_MAIN_PREPS],
                                                 [
                                                     (
                                                         self._addr_array[PREP_MAIN_PREPS],
                                                         delegation_amount
                                                     )
                                                 ])
        prev_block, tx_results = self._make_and_req_block([tx])
        self.assertEqual(int(True), tx_results[0].status)
        self._write_precommit_state(prev_block)

        # get prep list
        response: dict = self.get_prep_list(1, 1)
        expected_response: dict = \
            {
                "preps":
                    [{
                        "address": self._addr_array[PREP_MAIN_PREPS],
                        "delegated": delegation_amount
                    }],
                "startRanking": 1,
                "totalDelegated": delegation_amount
            }
        self.assertEqual(expected_response, response)

        # make blocks
        self.make_blocks_to_next_calculation()

        # get main prep list
        expected_preps: list = []
        for i in range(1, PREP_MAIN_PREPS):
            expected_preps.append({
                "address": self._addr_array[i],
                "delegated": 0
            })
        expected_preps.insert(0, {"address": self._addr_array[PREP_MAIN_PREPS], "delegated": delegation_amount})

        response: dict = self.get_main_prep_list()
        expected_response: dict = \
            {
                "preps": expected_preps,
                "totalDelegated": delegation_amount
            }
        self.assertEqual(expected_response, response)

    def test_low_productivity(self):

        # get totalBlocks in main prep
        response: dict = self.get_prep(self._addr_array[0])
        total_blocks: int = response['stats']['totalBlocks']

        # make blocks with prev_block_generator and prev_block_validators
        block_count: int = 20
        for i in range(block_count):
            prev_block, tx_results = self._make_and_req_block(
                [],
                prev_block_generator=self._addr_array[0],
                prev_block_validators=[self._addr_array[1], self._addr_array[2]])
            self._write_precommit_state(prev_block)

        for i in range(3):
            response: dict = self.get_prep(self._addr_array[i])
            expected_response: dict = \
                {
                    "totalBlocks": total_blocks + block_count,
                    "validatedBlocks": block_count
                }
            self.assertEqual(expected_response, response["stats"])

        response: dict = self.get_prep(self._addr_array[3])
        expected_response: dict = \
            {
                "totalBlocks": total_blocks + block_count,
                "validatedBlocks": 0
            }
        self.assertEqual(expected_response, response["stats"])

    def test_set_governance_variables1(self):
        origin_irep: int = IISS_INITIAL_IREP
        tx: dict = self.create_set_governance_variables(self._addr_array[0], origin_irep)
        prev_block, tx_results = self._make_and_req_block([tx])
        for tx_result in tx_results:
            self.assertEqual(int(True), tx_result.status)
        self._write_precommit_state(prev_block)

        response: dict = self.get_prep(self._addr_array[0])
        expected_irep: int = origin_irep
        expected_update_block_height: int = self._block_height
        self.assertEqual(expected_irep, response['registration']['irep'])
        self.assertEqual(expected_update_block_height, response['registration']['irepUpdateBlockHeight'])

        self.make_blocks_to_next_calculation()

        irep: int = origin_irep * 12 // 10
        tx: dict = self.create_set_governance_variables(self._addr_array[0], irep)
        prev_block, tx_results = self._make_and_req_block([tx])
        for tx_result in tx_results:
            self.assertEqual(int(True), tx_result.status)
        self._write_precommit_state(prev_block)

        response: dict = self.get_prep(self._addr_array[0])
        expected_irep: int = irep
        expected_update_block_height: int = self._block_height
        self.assertEqual(expected_irep, response['registration']['irep'])
        self.assertEqual(expected_update_block_height, response['registration']['irepUpdateBlockHeight'])

    def test_set_governance_variables2(self):
        origin_irep: int = IISS_INITIAL_IREP
        tx: dict = self.create_set_governance_variables(self._addr_array[0], origin_irep)
        prev_block, tx_results = self._make_and_req_block([tx])
        for tx_result in tx_results:
            self.assertEqual(int(True), tx_result.status)
        self._write_precommit_state(prev_block)

        response: dict = self.get_prep(self._addr_array[0])
        expected_irep: int = origin_irep
        expected_update_block_height: int = self._block_height
        self.assertEqual(expected_irep, response['registration']['irep'])
        self.assertEqual(expected_update_block_height, response['registration']['irepUpdateBlockHeight'])

        # term validate
        irep: int = origin_irep
        tx: dict = self.create_set_governance_variables(self._addr_array[0], irep)
        prev_block, tx_results = self._make_and_req_block([tx])
        self.assertEqual(int(True), tx_results[0].status)
        self.assertEqual(int(False), tx_results[1].status)
        self._write_precommit_state(prev_block)

        self.make_blocks_to_next_calculation()

        # 20% below
        irep: int = origin_irep * 8 - 1 // 10
        tx: dict = self.create_set_governance_variables(self._addr_array[0], irep)
        prev_block, tx_results = self._make_and_req_block([tx])
        self.assertEqual(int(True), tx_results[0].status)
        self.assertEqual(int(False), tx_results[1].status)
        self._write_precommit_state(prev_block)

        # 20 above
        irep: int = origin_irep * 12 + 1 // 10
        tx: dict = self.create_set_governance_variables(self._addr_array[0], irep)
        prev_block, tx_results = self._make_and_req_block([tx])
        self.assertEqual(int(True), tx_results[0].status)
        self.assertEqual(int(False), tx_results[1].status)
        self._write_precommit_state(prev_block)

    def test_set_governance_variables3(self):
        origin_irep: int = IISS_INITIAL_IREP
        tx: dict = self.create_set_governance_variables(self._addr_array[0], origin_irep)
        prev_block, tx_results = self._make_and_req_block([tx])
        for tx_result in tx_results:
            self.assertEqual(int(True), tx_result.status)
        self._write_precommit_state(prev_block)

        response: dict = self.get_prep(self._addr_array[0])
        expected_irep: int = origin_irep
        expected_update_block_height: int = self._block_height
        self.assertEqual(expected_irep, response['registration']['irep'])
        self.assertEqual(expected_update_block_height, response['registration']['irepUpdateBlockHeight'])

        irep: int = origin_irep

        possible_maximum_raise_irep_count: int = 6
        for i in range(possible_maximum_raise_irep_count):
            self.make_blocks_to_next_calculation()

            irep: int = irep * 12 // 10
            tx: dict = self.create_set_governance_variables(self._addr_array[0], irep)
            prev_block, tx_results = self._make_and_req_block([tx])
            for tx_result in tx_results:
                self.assertEqual(int(True), tx_result.status)
            self._write_precommit_state(prev_block)

        # max totalsupply limitation
        self.make_blocks_to_next_calculation()
        irep: int = irep * 12 // 10
        tx: dict = self.create_set_governance_variables(self._addr_array[0], irep)
        prev_block, tx_results = self._make_and_req_block([tx])
        self.assertEqual(int(True), tx_results[0].status)
        self.assertEqual(int(False), tx_results[1].status)
        self._write_precommit_state(prev_block)

    def test_weighted_average_of_irep(self):

        delegation1: int = 1
        tx1: dict = self.create_set_delegation_tx(self._addr_array[PREP_MAIN_PREPS],
                                                 [
                                                     (
                                                         self._addr_array[0],
                                                         delegation1
                                                     )
                                                 ])
        delegation2: int = 3
        tx2: dict = self.create_set_delegation_tx(self._addr_array[PREP_MAIN_PREPS + 1],
                                                  [
                                                      (
                                                          self._addr_array[1],
                                                          delegation2
                                                      )
                                                  ])
        prev_block, tx_results = self._make_and_req_block([tx1, tx2])
        for tx_result in tx_results:
            self.assertEqual(int(True), tx_result.status)
        self._write_precommit_state(prev_block)

        irep1: int = IISS_INITIAL_IREP * 12 // 10
        tx1: dict = self.create_set_governance_variables(self._addr_array[0], irep1)
        irep2: int = IISS_INITIAL_IREP * 8 // 10
        tx2: dict = self.create_set_governance_variables(self._addr_array[1], irep2)
        prev_block, tx_results = self._make_and_req_block([tx1, tx2])
        for tx_result in tx_results:
            self.assertEqual(int(True), tx_result.status)
        self._write_precommit_state(prev_block)

        self.make_blocks_to_next_calculation()

        response: dict = self.get_iiss_info()
        expected_sum: int = IISS_INITIAL_IREP * 12 // 10 * delegation1 + IISS_INITIAL_IREP * 8 // 10 * delegation2
        expected_sum_delegation: int = delegation1 + delegation2
        expected_avg_irep: int = expected_sum // expected_sum_delegation
        self.assertEqual(expected_avg_irep, response['variable']['irep'])

    def test_sync_end_block_height_of_calc_and_term(self):
        response: dict = self.get_iiss_info()
        self.assertEqual(response['nextCalculation'], response['nextPRepTerm'])