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

import ast
import importlib.util
import os
from typing import List

from ..base.exception import IllegalFormatException

BLACKLIST_RESERVED_KEYWORD = ['exec', 'eval', 'compile', '__import__']
BASE_PACKAGE = 'iconservice'


class ClassAnalyzer(ast.NodeVisitor):
    def __init__(self):
        self.imps: List['ImportInfo'] = []
        self.imps_with_from: List['FromImportInfo'] = []

    def visit_Import(self, node):
        for alias in node.names:
            self.imps.append(ImportInfo(alias.name))
        self.generic_visit(node)

    def visit_ImportFrom(self, node):
        imports: list = []
        for alias in node.names:
            imports.append(alias.name)
        self.imps_with_from.append(FromImportInfo(node.level, node.module, imports))
        self.generic_visit(node)

    def visit_Name(self, node):
        keyword: str = node.id
        if keyword in BLACKLIST_RESERVED_KEYWORD:
            raise IllegalFormatException(f'Blacklist keyword found: keyword({keyword})')
        self.generic_visit(node)


class ImportInfo:
    def __init__(self, import_info: str):
        self._import_info = import_info

    @property
    def import_info(self):
        return self._import_info


class FromImportInfo:
    def __init__(self, level: int, from_info: str, import_infos: list):
        self._level = level
        self._from_info: str = from_info
        self._import_infos: List[str] = import_infos

    @property
    def level(self) -> int:
        return self._level

    @property
    def from_info(self) -> str:
        return self._from_info

    @property
    def import_infos(self) -> List[str]:
        return self._import_infos

    def is_sub_module(self) -> bool:
        return self._level > 0


class ImportValidator:
    @classmethod
    def validate(cls,
                 info: 'ImportInfo',
                 whitelist: dict):
        if info.import_info not in whitelist:
            raise IllegalFormatException(f'Invalid import: import({info.import_info})')


class FromImportValidator:
    @classmethod
    def validate(cls,
                 info: 'FromImportInfo',
                 gv_whitelist: dict):
        if not info.is_sub_module():
            cls._module_validate(info, gv_whitelist)

    @classmethod
    def _module_validate(cls,
                         info: 'FromImportInfo',
                         gv_whitelist: dict):

        if info.from_info == BASE_PACKAGE:
            return

        if info.from_info not in gv_whitelist:
            cls._raise_exception(info)
        else:
            for imp in info.import_infos:
                if imp not in gv_whitelist[info.from_info]:
                    cls._raise_exception(info)

    @classmethod
    def _raise_exception(cls,
                         info: 'FromImportInfo'):
        raise IllegalFormatException(f'Invalid import_with_from: '
                                     f'from({info.from_info}), '
                                     f'import({info.import_infos}), '
                                     f'is_sub: ({info.is_sub_module()})')


class BaseImportValidator:
    @classmethod
    def validate(cls,
                 info: 'FromImportInfo',
                 root_whitelist: set):

        if info.from_info != BASE_PACKAGE or '*' in info.import_infos:
            return

        for imp in info.import_infos:
            if imp not in root_whitelist:
                raise IllegalFormatException(f'Invalid permission import: '
                                             f'from({info.from_info}), '
                                             f'import({info.import_infos})')


def get_iconservice_whitelist() -> set:
    whitelist: set = set()
    spec = importlib.util.find_spec(BASE_PACKAGE)
    with open(spec.origin) as file:
        tree = ast.parse(file.read())
        analyzer = ClassAnalyzer()
        analyzer.visit(tree)

        for info in analyzer.imps_with_from:
            if info.is_sub_module():
                for imp in info.import_infos:
                    whitelist.add(imp)
        return whitelist


class ScorePackageValidator:
    root_whitelist: set = get_iconservice_whitelist()

    @classmethod
    def execute(cls,
                gv_whitelist: dict,
                pkg_root_path: str,
                pkg_root_package: str) -> callable:

        import_list: list = cls._get_custom_import_list(pkg_root_path)

        for imp in import_list:
            full_name = f'{pkg_root_package}.{imp}'
            spec = importlib.util.find_spec(full_name)

            with open(spec.origin) as file:
                tree = ast.parse(file.read())
                analyzer: 'ClassAnalyzer' = ClassAnalyzer()
                analyzer.visit(tree)
                cls._import_validate(analyzer, gv_whitelist)

    @classmethod
    def _get_custom_import_list(cls,
                                pkg_root_path: str) -> list:
        import_list = []
        for dirpath, _, filenames in os.walk(pkg_root_path):
            for file in filenames:
                file_name, extension = os.path.splitext(file)
                if extension != '.py':
                    continue
                sub_pkg_path = os.path.relpath(dirpath, pkg_root_path)
                if sub_pkg_path == '.':
                    pkg_path = file_name
                else:
                    # sub_package
                    sub_pkg_path = sub_pkg_path.replace('/', '.')
                    pkg_path = f'{sub_pkg_path}.{file_name}'
                import_list.append(pkg_path)
        return import_list

    @classmethod
    def _import_validate(cls,
                         analyzer: 'ClassAnalyzer',
                         gv_whitelist: dict):
        for info in analyzer.imps:
            ImportValidator.validate(info, gv_whitelist)

        for info in analyzer.imps_with_from:
            FromImportValidator.validate(info, gv_whitelist)
            BaseImportValidator.validate(info, cls.root_whitelist)
