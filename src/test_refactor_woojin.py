import ast
from random import choice

from src.core.parsing import parse_library
from src.core.refactor import REFACTORING_TYPES

if __name__ == '__main__':
    node_container_dict = parse_library("./target_libraries/library_example1")

    # collect all classes from library
    classes = []
    for file_path, node_container in node_container_dict.items():
        for idx, node in enumerate(node_container.nodes):
            if isinstance(node, ast.ClassDef):
                classes.append((file_path, idx))

    refactoring_count = 0

    # target_class_location = choice(classes)
    print(classes)
    target_class_location = classes[5]
    _refactoring = choice(REFACTORING_TYPES)
    print(target_class_location, _refactoring)

    refactor = _refactoring(base=node_container_dict, location=target_class_location)

    if refactor.is_possible():
        refactor.do()

        for item in refactor.result.values():
            for node in item.nodes:
                print(ast.unparse(node))

        # TODO: metric 계산 & metric이 오르지 않으면 undo
        # refactor.undo()
        #
        # print("##### After undo #####")
        # for node in list(refactor.result.values())[0].nodes:
        #     print(ast.unparse(node))
