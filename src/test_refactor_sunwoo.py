import os
import ast
from pprint import pprint
from core.parsing import parse_library
from core.refactor import REFACTORING_TYPES, PushDownMethod, PushDownField, PullUpField, IncreaseFieldAccess, DecreaseFieldAccess, \
    ExtractHierarchy, CollapseHierarchy


def test_refactoring(library_path, refactoring_type=None, output_dir="refactored_library"):
    """Test a specific or random src on a library and save refactored code to a new directory."""
    # Parse the library
    node_container_dict = parse_library(library_path)

    # Ensure output directory exists
    os.makedirs(output_dir, exist_ok=True)

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

    results = []
    for class_location in classes:  
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

                # Do refactoring
                refactor.do()

                # Write the refactored code to the output directory
                for file_path, item in refactor.result.items():
                    # Determine the relative path to preserve structure
                    relative_path = os.path.relpath(file_path, start=library_path)
                    output_path = os.path.join(output_dir, relative_path)

                    # Ensure the subdirectories exist
                    os.makedirs(os.path.dirname(output_path), exist_ok=True)

                    # Write refactored code
                    with open(output_path, "w") as f:
                        for node in item.nodes:
                            f.write(ast.unparse(node) + "\n\n")

                # Store result
                results.append({
                    'class_name': class_name,
                    'src': refactoring_class.__name__,
                    'success': True
                })
        break
                

            # else:
            #     print(f"Refactoring not possible")
            #     results.append({
            #         'class_name': class_name,
            #         'src': refactoring_class.__name__,
            #         'success': False
            #     })


    # Print summary
    print("\nTest Summary:")
    print("-" * 40)
    for result in results:
        status = "✓" if result['success'] else "✗"
        print(f"{status} {result['src']} on {result['class_name']}")


if __name__ == '__main__':
    # Test example
    test_refactoring("refactoring/target_libraries/decreasefieldaccess_test", IncreaseFieldAccess)
