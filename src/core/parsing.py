import ast
import os
import sys
from pprint import pprint

IGNORE_PYTHON_FILE = ["__init__.py", "__main__.py"]
ENCODING = "utf-8"


class NodeContainer:
    def __init__(self):
        self.nodes: list[ast.ClassDef | ast.Import | ast.ImportFrom] = []
        self.metric = None
        self.aliases: list[ast.alias] = []
        # self.refactored = False

        # {"file1.Class1": ["file1.Parent1", "file2.Parent1"]}
        self.inheritance_dict: dict[str, list[str]] = {}

    def lookup_alias(self, class_name: str):
        # Find the original class name which may be aliased
        for alias in self.aliases:
            if alias.asname is None:
                continue

            if alias.asname == class_name:
                return alias.name

        return class_name


def get_class_names_with_path(node_container_dict: dict[str, NodeContainer], class_names: list[str]):
    results = []

    for file_path, node_container in node_container_dict.items():
        for node in node_container.nodes:
            if isinstance(node, ast.ClassDef):
                if node.name in class_names:
                    results.append(f"{file_path}:{node.name}")

    return results


def refresh_inheritance_dict(node_container_dict: dict[str, NodeContainer]):
    from src.utils.ast_utils import get_valid_bases, get_str_bases

    for file_path, node_container in node_container_dict.items():
        for node in node_container.nodes:
            if isinstance(node, ast.ClassDef):
                current_class_name_with_path = f"{file_path}:{node.name}"

                bases = list(get_str_bases(get_valid_bases(node)))
                bases_with_path = get_class_names_with_path(node_container_dict, bases)
                node_container.inheritance_dict[current_class_name_with_path] = bases_with_path


def get_full_inheritance_dict(node_container_dict: dict[str, NodeContainer]):
    result_dict = {}
    for node_container in node_container_dict.values():
        result_dict.update(node_container.inheritance_dict)
    return result_dict


def parse_library(library_path):
    container_dict = {}

    for root, dirs, files in os.walk(library_path):
        for file in files:
            if file.endswith('.py') and file not in IGNORE_PYTHON_FILE:
                file_path = f"{root}/{file}"

                with open(file_path, "r", encoding=ENCODING) as f:
                    code = f.read()

                tree = ast.parse(code)

                has_class_node = False
                node_container = NodeContainer()
                for node in tree.body:
                    if isinstance(node, ast.ClassDef):
                        has_class_node = True
                        node_container.nodes.append(node)
                    elif isinstance(node, ast.Import | ast.ImportFrom):
                        node_container.nodes.append(node)
                        node_container.aliases.extend(node.names)

                if has_class_node:
                    container_dict[file_path] = node_container

    refresh_inheritance_dict(container_dict)

    return container_dict


if __name__ == '__main__':
    # src/target_library_zips 폴더에 있는 pyflakes.zip 파일을 src/target_libraries 경로에 압축 풀기
    # -> src/target_libraries/pyflakes 경로가 생기도록
    result = parse_library("../target_libraries/pyflakes")
    pprint(result)
