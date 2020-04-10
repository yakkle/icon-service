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


import threading
from typing import Optional, List, TYPE_CHECKING

from ...base.exception import FatalException

if TYPE_CHECKING:
    from ..icon_score_context import IconScoreContext

_thread_local_data = threading.local()


class ContextContainer(object):
    """ContextContainer mixin

    Every class which inherits ContextContainer can share IconScoreContext instance
    in the current thread.
    """

    @staticmethod
    def _get_context() -> Optional["IconScoreContext"]:
        context_stack: List["IconScoreContext"] = getattr(
            _thread_local_data, "context_stack", None
        )

        if context_stack is not None and len(context_stack) > 0:
            return context_stack[-1]
        else:
            return None

    @staticmethod
    def _push_context(context: "IconScoreContext") -> None:
        context_stack: List["IconScoreContext"] = getattr(
            _thread_local_data, "context_stack", None
        )

        if context_stack is None:
            context_stack = []
            setattr(_thread_local_data, "context_stack", context_stack)

        context_stack.append(context)

    @staticmethod
    def _pop_context() -> "IconScoreContext":
        """Delete the last pushed context of the current thread
        """
        context_stack: List["IconScoreContext"] = getattr(
            _thread_local_data, "context_stack", None
        )

        if context_stack is not None and len(context_stack) > 0:
            return context_stack.pop()
        else:
            raise FatalException("Failed to pop a context out of context_stack")

    @staticmethod
    def _clear_context() -> None:
        setattr(_thread_local_data, "context_stack", None)

    @staticmethod
    def _get_context_stack_size() -> int:
        context_stack: List["IconScoreContext"] = getattr(
            _thread_local_data, "context_stack", None
        )
        return 0 if context_stack is None else len(context_stack)


class ContextGetter(object):
    """The class which refers to IconScoreContext should inherit ContextGetter
    """

    @property
    def _context(self) -> "IconScoreContext":
        return ContextContainer._get_context()
