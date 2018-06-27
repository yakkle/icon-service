# -*- coding: utf-8 -*-
# Copyright 2017-2018 theloop Inc.
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

from enum import IntFlag
from collections import namedtuple
from os import path, symlink, makedirs

from ..base.address import Address
from ..base.exception import InvalidParamsException
from ..base.type_converter import TypeConverter
from ..logger import Logger
from ..iconscore.icon_score_context import ContextContainer
from ..icx.icx_storage import IcxStorage
from .icon_score_deployer import IconScoreDeployer

from typing import TYPE_CHECKING, Optional, Callable
if TYPE_CHECKING:
    from ..iconscore.icon_score_context import IconScoreContext
    from ..iconscore.icon_score_info_mapper import IconScoreInfoMapper


class IconScoreDeployEngine(ContextContainer):
    """It handles transactions to install, update and audit a SCORE
    """

    class Flag(IntFlag):
        NONE = 0
        # To complete to install or update a SCORE,
        # some specified address owner like genesis address owner
        # MUST approve install or update SCORE transactions.
        ENABLE_DEPLOY_AUDIT = 1

    # This namedtuple should be used only in IconScoreDeployEngine.
    _Task = namedtuple(
        'Task',
        ('block', 'tx', 'msg', 'icon_score_address', 'data_type', 'data'))

    _SUPPORT_DATA_TYPES = ['install', 'update']

    def __init__(self,
                 icon_score_root_path: str,
                 flags: 'Flag',
                 icx_storage: 'IcxStorage',
                 icon_score_mapper: 'IconScoreInfoMapper') -> None:
        """Constructor

        :param icon_score_root_path:
        :param flags: flags composed by IconScoreDeployEngine
        """
        self._flags = flags
        self._icx_storage = icx_storage
        self._icon_score_mapper = icon_score_mapper

        self._deferred_tasks = []
        self._icon_score_deployer: IconScoreDeployer =\
            IconScoreDeployer(icon_score_root_path)

        if self.is_flag_on(self.Flag.ENABLE_DEPLOY_AUDIT):
            self._SUPPORT_DATA_TYPES.append('audit')

    def is_flag_on(self, flag: 'Flag') -> bool:
        return (self._flags & flag) == flag

    def is_data_type_supported(self, data_type: str) -> bool:
        """Check if IconScoreDeployEngine supports the given data_type or not

        :param data_type:
        :return:
        """
        return data_type in self._SUPPORT_DATA_TYPES

    def invoke(self,
               context: 'IconScoreContext',
               icon_score_address: 'Address',
               data_type: str,
               data: dict) -> None:
        """Handle calldata contained in icx_sendTransaction message

        :param icon_score_address:
        :param context:
        :param data_type:
        :param data: calldata
        """
        if not self.is_data_type_supported(data_type):
            raise InvalidParamsException(f'Invalid dataType: {data_type}')

        self._deploy_on_invoke(context, icon_score_address, data_type, data)

    def _deploy_on_invoke(self,
                          context: 'IconScoreContext',
                          icon_score_address: 'Address',
                          data_type: str,
                          data: dict):
        content_type = data.get('contentType')

        if content_type == 'application/tbears':
            # Install a score which is under development on tbears
            pass
        elif content_type == 'application/zip':
            # Remove '0x' prefix
            # Assume that pre validation has been already done
            data['content'] = bytes.fromhex(data['content'][2:])
        else:
            raise InvalidParamsException(
                f'Invalid contentType: {content_type}')

        self._put_deferred_task(
            context=context,
            icon_score_address=icon_score_address,
            data_type=data_type,
            data=data)

    def _put_deferred_task(self,
                           context: 'IconScoreContext',
                           icon_score_address: 'Address',
                           data_type: str,
                           data: dict) -> None:
        """Queue a deferred task to install, update or remove a score

        :param context:
        :param data_type:
        :param icon_score_address:
        :param data:
        """
        task = self._Task(
            block=context.block,
            tx=context.tx,
            msg=context.msg,
            icon_score_address=icon_score_address,
            data_type=data_type,
            data=data)

        self._deferred_tasks.append(task)

    def commit(self, context: 'IconScoreContext') -> None:
        """It is called when the previous block has been confirmed

        Execute a deferred tasks in queue (install, update or remove a score)

        Process Order
        - Install IconScore package file to file system
        - Load IconScore wrapper
        - Create Database
        - Create an IconScore instance with owner and database
        - Execute IconScoreBase.genesis_invoke() only if task.type is 'install'
        - Add IconScoreInfo to IconScoreInfoMapper
        - Write the owner of score to icx database

        """
        for task in self._deferred_tasks:
            context.block = task.block
            context.tx = task.tx
            context.msg = task.msg
            icon_score_address = task.icon_score_address
            data_type = task.data_type
            data = task.data

            try:
                if data_type == 'install':
                    self._install_on_commit(context, icon_score_address, data)
                elif data_type == 'update':
                    self._update_on_commit(context, icon_score_address, data)
                # Invalid task.type has been already filtered in invoke()
            except BaseException as e:
                Logger.exception(e)

        self._deferred_tasks.clear()

    def _install_on_commit(self,
                           context: Optional['IconScoreContext'],
                           icon_score_address: 'Address',
                           data: dict) -> None:
        """Install an icon score on commit

        Owner check has been already done in IconServiceEngine
        - Install IconScore package file to file system

        """
        content_type = data.get('contentType')
        content = data.get('content')
        params = data.get('params', {})

        if content_type == 'application/tbears':
            self._icon_score_mapper.delete_icon_score(icon_score_address)
            score_root_path = self._icon_score_mapper.score_root_path
            target_path = path.join(score_root_path,
                                    icon_score_address.body.hex())
            makedirs(target_path, exist_ok=True)
            target_path = path.join(
                target_path, f'{context.block.height}_{context.tx.index}')
            try:
                symlink(content, target_path, target_is_directory=True)
            except FileExistsError:
                pass
        else:
            pass

        self._icx_storage.put_score_owner(
            context, icon_score_address, context.tx.origin)

        db_exist = self._icon_score_mapper.is_exist_db(icon_score_address)
        score = self._icon_score_mapper.get_icon_score(icon_score_address)

        if not db_exist:
            self._call_on_init_of_score(
                context=context,
                on_init=score.on_install,
                params=params)

    def _update_on_commit(self,
                          context: Optional['IconScoreContext'],
                          icon_score_address: 'Address',
                          data: dict) -> None:
        """Update an icon score

        Owner check has been already done in IconServiceEngine
        """
        raise NotImplementedError('Score update is not implemented')

    def _call_on_init_of_score(self,
                               context: 'IconScoreContext',
                               on_init: Callable[[dict], None],
                               params: dict) -> None:
        """on_install() or on_update() of score is called
        only once when installed or updated

        :param context:
        :param on_init: score.on_install() or score.on_update()
        :param params: paramters passed to on_install or on_update()
        """

        annotations = TypeConverter.make_annotations_from_method(on_init)
        TypeConverter.convert_params(annotations, params)

        try:
            self._put_context(context)
            on_init(**params)
        except Exception as e:
            Logger.exception(str(e))
        finally:
            self._delete_context(context)

    def rollback(self) -> None:
        """It is called when the previous block has been canceled

        Rollback install, update or remove tasks cached in the previous block
        """
        self._deferred_tasks.clear()