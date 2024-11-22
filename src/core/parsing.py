import ast
import os
from pprint import pprint

IGNORE_PYTHON_FILE = ["__init__.py", "__main__.py"]


class NodeContainer:
    def __init__(self):
        self.nodes: list[ast.ClassDef | ast.Import | ast.ImportFrom] = []
        self.metric = None
        self.aliases: list[ast.alias] = []
        # self.refactored = False

    def lookup_alias(self, class_name: str):
        # Find the original class name which may be aliased
        for alias in self.aliases:
            if alias.asname == class_name:
                return alias.name

        return class_name


def parse_library(library_path):
    container_dict = {}

    for root, dirs, files in os.walk(library_path):
        for file in files:
            if file.endswith('.py') and file not in IGNORE_PYTHON_FILE:
                file_path = f"{root}/{file}"

                with open(file_path, "r") as f:
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

    return container_dict


if __name__ == '__main__':
    # src/target_library_zips 폴더에 있는 pyflakes.zip 파일을 src/target_libraries 경로에 압축 풀기
    # -> src/target_libraries/pyflakes 경로가 생기도록
    result = parse_library("../target_libraries/pyflakes")
    pprint(result)
