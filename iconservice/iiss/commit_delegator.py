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

from typing import TYPE_CHECKING

from .iiss_data_creator import IissDataCreator

if TYPE_CHECKING:
    from ..iconscore.icon_score_context import IconScoreContext
    from ..icx.icx_storage import IcxStorage
    from ..precommit_data_manager import PrecommitData
    from ..base.address import Address
    from ..prep.prep_variable.prep_variable_storage import GovernanceVariable
    from .reward_calc_proxy import RewardCalcProxy
    from .rc_data_storage import RcDataStorage
    from .iiss_msg_data import IissHeader, PrepsData
    from .iiss_variable.iiss_variable import IissVariable


class CommitDelegator:
    icx_storage: 'IcxStorage' = None
    reward_calc_proxy: 'RewardCalcProxy' = None
    rc_storage: 'RcDataStorage' = None
    variable: 'IissVariable' = None

    @classmethod
    def genesis_update_db(cls, context: 'IconScoreContext', precommit_data: 'PrecommitData'):
        context.prep_candidate_engine.update_preps(context)
        cls._put_next_calc_block_height(context, precommit_data.block.height)

        cls._put_header_for_rc(context, precommit_data)
        cls._put_gv_for_rc(context, precommit_data)
        cls._put_preps_for_rc(context, precommit_data)

    @classmethod
    def genesis_send_ipc(cls, context: 'IconScoreContext', precommit_data: 'PrecommitData'):
        pass

    @classmethod
    def update_db(cls, context: 'IconScoreContext', precommit_data: 'PrecommitData'):
        # TODO UpdateCheck PrepList
        # cls._set_preps_iiss_variable(context)

        # every block time
        cls._put_block_produce_info_for_rc(context, precommit_data)

        if not cls._check_update_calc_period(context, precommit_data):
            return

        cls._put_next_calc_block_height(context, precommit_data.block.height)

        cls._put_header_for_rc(context, precommit_data)
        cls._put_gv_for_rc(context, precommit_data)

    @classmethod
    def send_ipc(cls, context: 'IconScoreContext', precommit_data: 'PrecommitData'):
        if not cls._check_update_calc_period(context, precommit_data):
            pass

    @classmethod
    def _check_update_calc_period(cls, context: 'IconScoreContext', precommit_data: 'PrecommitData') -> bool:
        block_height: int = precommit_data.block.height
        check_next_block_height: int = cls.variable.issue.get_calc_next_block_height(context)
        return block_height > check_next_block_height

    @classmethod
    def _put_next_calc_block_height(cls, context: 'IconScoreContext', block_height: int):
        calc_period: int = cls.variable.issue.get_calc_period(context)
        cls.variable.issue.put_calc_next_block_height(context, block_height + calc_period)

    @classmethod
    def _put_header_for_rc(cls, context: 'IconScoreContext', precommit_data: 'PrecommitData'):
        data: 'IissHeader' = IissDataCreator.create_header(0, precommit_data.block.height)
        cls.rc_storage.put(precommit_data.rc_block_batch, data)

    @classmethod
    def _put_gv_for_rc(cls, context: 'IconScoreContext', precommit_data: 'PrecommitData'):
        gv: 'GovernanceVariable' = context.prep_candidate_engine.get_gv(context)
        reward_rep: int = cls.variable.common.get_reward_rep(context)

        data: 'IissHeader' = IissDataCreator.create_gv_variable(precommit_data.block.height,
                                                                gv.incentive_rep,
                                                                reward_rep)
        cls.rc_storage.put(precommit_data.rc_block_batch, data)

    @classmethod
    def _put_block_produce_info_for_rc(cls, context: 'IconScoreContext', precommit_data: 'PrecommitData'):
        # tmp implement

        candidates: list = context.prep_candidate_engine.get_preps(context)
        preps: list = candidates[:22]

        if len(preps) == 0:
            return

        generator: 'Address' = preps[0].address
        validator_list: list = [prep.address for prep in preps]

        data: 'PrepsData' = IissDataCreator.create_prep_data(precommit_data.block.height,
                                                             generator,
                                                             validator_list)
        cls.rc_storage.put(precommit_data.rc_block_batch, data)

    @classmethod
    def _put_preps_for_rc(cls, context: 'IconScoreContext', precommit_data: 'PrecommitData'):
        # tmp implement

        total_preps: list = context.prep_candidate_engine.get_preps(context)

        if len(total_preps) == 0:
            return

        # cls.rc_storage.put(precommit_data.rc_block_batch, data)