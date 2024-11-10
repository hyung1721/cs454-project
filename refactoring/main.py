import ast
from random import choice

from refactoring.core.parsing import parse_library
from refactoring.core.refactor import REFACTORING_TYPES

if __name__ == '__main__':
    parsed_library = parse_library("./target_libraries/library_example1")

    # collect all classes from library
    classes = []
    for file_path, tree_detail in parsed_library.items():
        for idx, node in enumerate(tree_detail.nodes):
            if isinstance(node, ast.ClassDef):
                classes.append((file_path, idx))

    refactoring_count = 0

    target_class_location = choice(classes)
    _refactoring = choice(REFACTORING_TYPES)

    refactor = _refactoring(base=parsed_library, location=target_class_location)

    if refactor.is_possible():
        refactor.do()

        for node in list(refactor.result.values())[0].nodes:
            print(ast.unparse(node))

        # TODO: metric 계산 & metric이 오르지 않으면 undo
        # refactor.undo()
        #
        # print("##### After undo #####")
        # for node in list(refactor.result.values())[0].nodes:
        #     print(ast.unparse(node))
