import ast
import os
from pprint import pprint

IGNORE_PYTHON_FILE = ["__init__.py", "__main__.py"]


class TreeDetail:
    def __init__(self, nodes, metric = 0.0):
        self.nodes = nodes
        self.metric = metric


def parse_library(library_name):
    library_tree_dict = {}

    for root, dirs, files in os.walk(f"../target_libraries/{library_name}"):
        for file in files:
            if file.endswith('.py') and file not in IGNORE_PYTHON_FILE:
                file_path = f"{root}/{file}"

                with open(file_path, "r") as f:
                    code = f.read()

                tree = ast.parse(code)

                filtered_nodes = [node for node in tree.body if
                                  isinstance(node, ast.ClassDef | ast.Import | ast.ImportFrom)]
                has_class_node = not all([not isinstance(node, ast.ClassDef) for node in filtered_nodes])

                if has_class_node:
                    library_tree_dict[file_path] = TreeDetail(nodes=filtered_nodes)

    return library_tree_dict


if __name__ == '__main__':
    # refactoring/target_library_zips 폴더에 있는 pyflakes.zip 파일을 refactoring/target_libraries 경로에 압축 풀기
    # -> refactoring/target_libraries/pyflakes 경로가 생기도록
    result = parse_library("pyflakes")
    pprint(result)
