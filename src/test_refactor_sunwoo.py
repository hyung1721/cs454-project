import ast
from pprint import pprint
from core.parsing import parse_library
from core.refactor import REFACTORING_TYPES, PushDownField, PullUpField, IncreaseFieldAccess, DecreaseFieldAccess, \
    ExtractHierarchy, CollapseHierarchy


def test_refactoring(library_path, refactoring_type=None):
    """Test a specific or random src on a library"""
    # Parse the library
    node_container_dict = parse_library(library_path)

    # Collect all classes
    classes = []
    for file_path, node_container in node_container_dict.items():
        for idx, node in enumerate(node_container.nodes):
            if isinstance(node, ast.ClassDef):
                classes.append((file_path, idx, node.name))  # Added class name for better reporting

    print(f"Found {len(classes)} classes in library")
    for file_path, idx, name in classes:
        print(f"- {name} in {file_path}")
    print()

    # Try src each class
    results = []
    for class_location in classes:  # Tries to do src on all classes
        file_path, idx, class_name = class_location

        # Use specified src type or try all types
        refactoring_types = [refactoring_type] if refactoring_type else REFACTORING_TYPES

        for refactoring_class in refactoring_types:
            print(f"\nTrying {refactoring_class.__name__} on {class_name}...")

            # Create src instance
            refactor = refactoring_class(
                base=node_container_dict,
                location=(file_path, idx)
            )

            # Check if src is possible
            if refactor.is_possible():
                print("Refactoring is possible")

                # Show original code
                print("\nBefore src:")
                for node in node_container_dict[file_path].nodes:
                    print(ast.unparse(node))
                    print("-" * 40)

                # Do src
                refactor.do()

                # Show refactored code
                print("\nAfter src:")
                for item in refactor.result.values():
                    for node in item.nodes:
                        print(ast.unparse(node))
                        print("-" * 40)

                # Store result
                results.append({
                    'class_name': class_name,
                    'src': refactoring_class.__name__,
                    'success': True
                })

                # # Test undo
                # print("\nTesting undo...")
                # refactor.undo()
                # print("After undo:")
                # for node in node_container_dict[file_path].nodes:
                #     print(ast.unparse(node))
                #     print("-" * 40)

            else:
                print(f"Refactoring not possible")
                results.append({
                    'class_name': class_name,
                    'src': refactoring_class.__name__,
                    'success': False
                })

    # Print summary
    print("\nTest Summary:")
    print("-" * 40)
    for result in results:
        status = "✓" if result['success'] else "✗"
        print(f"{status} {result['src']} on {result['class_name']}")


if __name__ == '__main__':
    # Test data structure for fields
    #     example_code = """
    # class Animal:
    #     def __init__(self):
    #         self.alive = True

    # class Mammal(Animal):
    #     def __init__(self):
    #         self.warm_blooded = True
    #         super().__init__()
    #         # Complex initialization logic
    #         if self.warm_blooded:
    #             self.fur_type = "thick"
    #         for i in range(self.metabolism_rate()):
    #             self.eat()
    #         try:
    #             self.initialize_system()
    #         except:
    #             self.default_init()
    # class Human(Mammal):
    #     def __init__(self):
    #         super().__init__()
    #         self.single = False
    #     """

    #     # Write example code to a test file
    #     with open("src/target_libraries/test_library/test_code.py", "w") as f:
    #         f.write(example_code)

    # Test src types; test if actually works with imports
    test_refactoring("src/target_libraries/pushdownfield_test", PushDownField)
