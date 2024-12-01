import os
import ast
import copy
from abc import ABC, abstractmethod
from random import choice
from itertools import combinations


from src.core.parsing import NodeContainer
from src.utils.ast_utils import find_normal_methods, find_instance_fields, MethodRenamer, \
    MethodOccurrenceChecker, InstanceFieldOccurrenceChecker, InitMethodInjector, SelfMethodOccurrenceReplacer, \
    is_direct_self_attr, SelfAttributeOccurrenceReplacer, check_inherit_abc, AbstractMethodDecoratorChecker, \
    is_super_init_call, get_str_bases, create_super_init_call, DependencyVisitor, find_self_dependencies, \
    class_redefines_field, update_field_references, get_all_subclasses, \
    update_descendant_chain, find_method_in_class, method_exists_in_class, get_container_for_node


class Refactor(ABC):
    def __construct_subclasses(self):
        self.class_names = []
        self.subclasses = []
        for node_container in self.result.values():
            for node in node_container.nodes:
                if isinstance(node, ast.ClassDef):
                    self.class_names.append(node.name)
                    if any(
                            node_container.lookup_alias(base) == self.target_class_node.name
                            for base in get_str_bases(node.bases)
                    ):
                        self.subclasses.append(node)

    def __construct_superclasses(self):
        self.superclasses = []
        superclass_names = [
            self.target_node_container.lookup_alias(base)
            for base in get_str_bases(self.target_class_node.bases)
        ]
        for node_container in self.result.values():
            for node in node_container.nodes:
                if isinstance(node, ast.ClassDef) and node.name in superclass_names:
                    self.superclasses.append(node)

    def __init__(self, base: dict[str, NodeContainer], location):
        self.base = base
        self.result = copy.deepcopy(base)
        self.file_path = location[0]
        self.node_idx = location[1]

        self.target_node_container = self.result[self.file_path]
        target_class_node = self.target_node_container.nodes[self.node_idx]
        if not isinstance(target_class_node, ast.ClassDef):
            raise Exception(f"{target_class_node} is not an instance of ast.ClassDef")
        self.target_class_node = target_class_node

        self.__construct_subclasses()
        self.__construct_superclasses()

    @abstractmethod
    def is_possible(self):
        ...

    @abstractmethod
    def do(self):
        ...

    def undo(self):
        self.result = self.base


# Method Level Refactorings
class PushDownMethod(Refactor):
    def __init__(self, base: dict[str, NodeContainer], location):
        super().__init__(base, location)
        self.methods = find_normal_methods(self.target_class_node.body)

    def is_possible(self):
        return len(self.methods) >= 1 and len(self.subclasses) >= 1

    def do(self):
        if not self.is_possible():
            return

        method_node = choice(self.methods)

        # remove method from target class
        self.target_class_node.body.remove(method_node)
        self.result[self.file_path].nodes[self.node_idx] = self.target_class_node

        # add method to subclasses of target class
        for node in self.subclasses:
            # find the occurrence of method
            checker = MethodOccurrenceChecker(method_name=method_node.name)
            checker.visit(node)

            if checker.occurred and not checker.overridden:
                new_method = copy.deepcopy(method_node)
                node.body.append(new_method)

        # self.result[self.file_path].refactored = True


class PullUpMethod(Refactor):
    def __init__(self, base: dict[str, NodeContainer], location):
        super().__init__(base, location)
        self.methods = find_normal_methods(self.target_class_node.body)

    def is_possible(self):
        return len(self.methods) >= 1 and len(self.superclasses) >= 1

    def do(self):
        if not self.is_possible():
            return

        method_node = choice(self.methods)

        # remove method from target class
        self.target_class_node.body.remove(method_node)
        self.result[self.file_path].nodes[self.node_idx] = self.target_class_node

        # add method to subclasses of target class
        for node in self.superclasses:
            new_method = copy.deepcopy(method_node)
            node.body.append(new_method)

        # self.result[self.file_path].refactored = True


# foo() -> public, _foo() -> protected, __foo() -> private
# Increase Accessibility: foo() -> _foo() or _foo() -> __foo()
class IncreaseMethodAccess(Refactor):
    def __init__(self, base: dict[str, NodeContainer], location):
        super().__init__(base, location)
        self.public_or_protected_methods = [
            method for method in find_normal_methods(self.target_class_node.body)
            if not method.name.startswith("__")
        ]

    def is_possible(self):
        return len(self.public_or_protected_methods) >= 1

    def do(self):
        if not self.is_possible():
            return

        method_node = choice(self.public_or_protected_methods)

        old_name = method_node.name
        new_name = "_" + method_node.name
        renamer = MethodRenamer(old_name=old_name, new_name=new_name)

        # Change the all occurrence of method in classes, including subclasses
        classes = [self.target_class_node] + self.subclasses
        for item in classes:
            renamer.visit(item)


# Decrease Accessibility: _foo() -> foo() or __foo() -> _foo()
class DecreaseMethodAccess(Refactor):
    def __init__(self, base: dict[str, NodeContainer], location):
        super().__init__(base, location)
        self.protected_or_private_methods = [
            method for method in find_normal_methods(self.target_class_node.body)
            if method.name.startswith("_")
        ]

    def is_possible(self):
        return len(self.protected_or_private_methods) >= 1

    def do(self):
        if not self.is_possible():
            return

        method_node = choice(self.protected_or_private_methods)

        old_name = method_node.name
        new_name = method_node.name[1:]  # remove first underscore
        renamer = MethodRenamer(old_name=old_name, new_name=new_name)

        # Change the all occurrence of method in classes, including subclasses
        classes = [self.target_class_node] + self.subclasses
        for item in classes:
            renamer.visit(item)


# Field Level Refactorings
class PushDownField(Refactor):
    def __init__(self, base: dict[str, NodeContainer], location):
        super().__init__(base, location)
        self.fields = find_instance_fields(self.target_class_node.body)

    def is_field_used_by_parent(self, field_name: str) -> bool:
        """Check if any non-init method in parent class uses this field"""
        checker = InstanceFieldOccurrenceChecker(field_name)
        for node in self.target_class_node.body:
            if isinstance(node, ast.FunctionDef) and node.name != "__init__":
                checker.visit(node)
        return checker.occurred

    def is_possible(self):
        if not (len(self.fields) >= 1 and len(self.subclasses) >= 1):
            return False

        # Check each field
        for field in self.fields:
            field_name = field.targets[0].attr
            if not self.is_field_used_by_parent(field_name):
                return True
        print(f"All fields used by parent method")
        return False

    def do(self):
        if not self.is_possible():
            return

        refactor_occurred = False
        pushable_fields = []
        for field in self.fields:
            field_name = field.targets[0].attr
            if not self.is_field_used_by_parent(field_name):
                pushable_fields.append(field)

        field_node = choice(pushable_fields)
        field_name = field_node.targets[0].attr  # get name from self.field_name

        # Find __init__ method
        init_idx = None
        for idx, node in enumerate(self.target_class_node.body):
            if isinstance(node, ast.FunctionDef) and node.name == "__init__":
                init_idx = idx
                break

        # Add to subclasses that use but don't define it
        for node in self.subclasses:
            checker = InstanceFieldOccurrenceChecker(field_name=field_name)
            checker.visit(node)

            if checker.occurred and not checker.defined:
                refactor_occurred = True
                # Find or create __init__ in subclass
                init_method = None
                for child in node.body:
                    if isinstance(child, ast.FunctionDef) and child.name == "__init__":
                        init_method = child
                        break

                if init_method is None:
                    # Create new __init__ with super().__init__() call
                    init_method = ast.FunctionDef(
                        name='__init__',
                        args=ast.arguments(
                            posonlyargs=[],
                            args=[ast.arg(arg='self', lineno=1, col_offset=0)],
                            kwonlyargs=[],
                            kw_defaults=[],
                            defaults=[]
                        ),
                        body=[
                            ast.Expr(
                                value=ast.Call(
                                    func=ast.Attribute(
                                        value=ast.Call(
                                            func=ast.Name(id='super'),
                                            args=[],
                                            keywords=[]
                                        ),
                                        attr='__init__'
                                    ),
                                    args=[],
                                    keywords=[]
                                )
                            )
                        ],
                        decorator_list=[],
                        lineno=1,
                        col_offset=0,
                        end_lineno=1,
                        end_col_offset=0
                    )
                    node.body.insert(0, init_method)

                # Add field assignment after super().__init__()
                new_field = copy.deepcopy(field_node)
                init_method.body.insert(1, new_field)
        if refactor_occurred:
            if init_idx is not None:
                # Remove field from parent's __init__
                # Shouldn't always remove it: only when we actually push down?
                init_body = self.target_class_node.body[init_idx].body
                init_body.remove(field_node)
        # self.result[self.file_path].refactored = refactor_occurred


class PullUpField(Refactor):
    def __init__(self, base: dict[str, NodeContainer], location):
        super().__init__(base, location)
        # Find fields in target class
        self.fields = find_instance_fields(self.target_class_node.body)
        
        # Find immediate superclass 
        superclass_names = [
            self.target_node_container.lookup_alias(base)
            for base in get_str_bases(self.target_class_node.bases)
        ]
        
        # Look for superclass definition
        self.superclass = None
        for node_container in self.result.values():
            for node in node_container.nodes:
                if isinstance(node, ast.ClassDef) and node.name in superclass_names:
                    self.superclass = node
                    break
            if self.superclass:
                break

    def get_field_info(self, field_node: ast.Assign):
        """Get field name and value"""
        field_name = field_node.targets[0].attr
        field_value = ast.unparse(field_node.value)
        return field_name, field_value

    def get_independent_fields(self):
        """Return fields that don't depend on other fields or methods in the class"""
        independent_fields = []
        
        for field in self.fields:
            field_name = field.targets[0].attr
            
            # Get dependencies and remove self reference if exists
            dependencies = find_self_dependencies(field.value)
            dependencies.discard(field_name)
            
            # If no dependencies found, field is independent
            if not dependencies:
                independent_fields.append(field)
                
        return independent_fields

    def find_sibling_classes(self) -> list[ast.ClassDef]:
        """Find other classes that inherit from same superclass"""
        siblings = []
        if not self.superclass:
            return siblings
            
        for container in self.result.values():
            for node in container.nodes:
                if isinstance(node, ast.ClassDef):
                    if any(
                            container.lookup_alias(base) == self.superclass.name
                            for base in get_str_bases(node.bases)
                    ):
                        siblings.append(node)
        return siblings

    def is_field_in_parent(self, field_name: str) -> bool:
        """Check if field is already defined in parent class"""
        if not self.superclass:
            return False
            
        checker = InstanceFieldOccurrenceChecker(field_name)
        checker.visit(self.superclass)
        return checker.defined

    def is_possible(self):
        if not (len(self.fields) >= 1 and self.superclass):
            return False

        independent_fields = self.get_independent_fields()
        if not independent_fields:
            return False

        # Only check if field exists in parent
        for field in independent_fields:
            field_name, _ = self.get_field_info(field)
            if not self.is_field_in_parent(field_name):
                return True
                
        return False

    def do(self):
        if not self.is_possible():
            return

        independent_fields = self.get_independent_fields()
        field = choice(independent_fields)
        field_name, field_value = self.get_field_info(field)
        
        # Add field to parent's __init__
        init_method = find_method_in_class("__init__", self.superclass)
        
        if init_method is None:
            has_superclass = bool(self.superclass.bases)
            if has_superclass:
                init_body = [create_super_init_call()]
            else:
                init_body = []
                
            init_method = ast.FunctionDef(
                name='__init__',
                args=ast.arguments(
                    posonlyargs=[],
                    args=[ast.arg(arg='self')],
                    kwonlyargs=[],
                    kw_defaults=[],
                    defaults=[]
                ),
                body=init_body,
                decorator_list=[]
            )
            self.superclass.body.insert(0, init_method)
        
        new_field = copy.deepcopy(field)
        init_method.body.append(new_field)
        
        # Only remove field from siblings that have the same value
        siblings = self.find_sibling_classes()
        for sibling in siblings:
            # Find which file/container has this sibling
            sibling_file, sibling_container = get_container_for_node(sibling, self.result)
            if not sibling_container:
                continue
                
            sibling_init = find_method_in_class("__init__", sibling)
            if sibling_init:
                for stmt in sibling_init.body[:]:
                    if (isinstance(stmt, ast.Assign) and
                        isinstance(stmt.targets[0], ast.Attribute) and
                        stmt.targets[0].attr == field_name and
                        ast.unparse(stmt.value) == field_value):
                        sibling_init.body.remove(stmt)

class DecreaseFieldAccess(Refactor):
    def __init__(self, base: dict[str, NodeContainer], location):
        super().__init__(base, location)
        self.fields = find_instance_fields(self.target_class_node.body)
        self.decreasable_fields = [
            field for field in self.fields
            if not field.targets[0].attr.startswith("__")
        ]

    def is_possible(self):
        return len(self.decreasable_fields) >= 1

    def do(self):
        if not self.is_possible():
            return

        field_node = choice(self.decreasable_fields)
        old_name = field_node.targets[0].attr
        new_name = "_" + old_name

        # Update target class
        update_field_references(self.target_class_node, old_name, new_name)

        # Update entire descendant chain until redefinitions
        update_descendant_chain(
            self.target_class_node, 
            old_name, 
            new_name, 
            self.result
        )


class IncreaseFieldAccess(Refactor):
    def __init__(self, base: dict[str, NodeContainer], location):
        super().__init__(base, location)
        self.fields = find_instance_fields(self.target_class_node.body)
        self.increasable_fields = [
            field for field in self.fields
            if field.targets[0].attr.startswith("_")
        ]

    def is_possible(self):
        return len(self.increasable_fields) >= 1

    def do(self):
        if not self.is_possible():
            return

        field_node = choice(self.increasable_fields)
        old_name = field_node.targets[0].attr
        new_name = old_name[1:]  # Remove one underscore

        # Update target class
        update_field_references(self.target_class_node, old_name, new_name)

        # Update entire descendant chain until redefinitions
        update_descendant_chain(
            self.target_class_node, 
            old_name, 
            new_name, 
            self.result
        )



## Class Level Refactorings
class ExtractHierarchy(Refactor):
    def __init__(self, base: dict[str, NodeContainer], location):
        super().__init__(base, location)
        # Track methods and fields for each subclass
        self.subclass_methods = {
            node: find_normal_methods(node.body) 
            for node in self.subclasses
        }
        self.subclass_fields = {
            node: find_instance_fields(node.body)
            for node in self.subclasses
        }

    def is_possible(self):
        return len(self.subclasses) >= 2

    def do(self):
        if not self.is_possible():
            return

        # Find group of similar classes and their common features
        group, shared_methods, shared_fields = self._find_best_subclass_group()

        if not group:
            group = self.subclasses

        # Create and insert new intermediate class
        new_class_name = f"RefactoredSub{self.target_class_node.name}"
        new_class = self._create_intermediate_class(new_class_name, shared_methods, shared_fields)
        
        # Add new class after target class
        target_idx = self.result[self.file_path].nodes.index(self.target_class_node)
        self.result[self.file_path].nodes.insert(target_idx + 1, new_class)

        # Update each subclass in the group
        for subclass in group:
            # Find container for this subclass
            file_path, container = get_container_for_node(subclass, self.result)
            if not container:
                continue

            # Handle import if needed
            if file_path != self.file_path:
                self._add_import(container, new_class_name, file_path)

            # Update inheritance
            self._update_inheritance(subclass, container, new_class_name) 
            
            # Remove features that were moved to intermediate class
            self._remove_common_features(subclass, shared_methods, shared_fields)
            
            # Ensure proper initialization: Don't need for static analysis?
            # self._ensure_proper_init(subclass)

    def _find_best_subclass_group(self, min_similarity=0.3):
        """Find subclasses with sufficient common features"""

        # Find most similar pair first
        best_pair = None
        best_score = -1
        best_features = None

        for c1, c2 in combinations(self.subclasses, 2):
            score, methods, fields = self._count_common_features(c1, c2)
            if score > best_score:
                best_score = score
                best_pair = (c1, c2)
                best_features = (methods, fields)

        if not best_pair or best_score == 0:
            print("No pair of classes have anything in common")
            return set(), [], [] 

        # Start group with best pair
        group = {best_pair[0], best_pair[1]}
        methods, fields = best_features

        # Try adding other classes that are similar enough
        remaining = set(self.subclasses) - group
        for cls in remaining:
            matches = self._count_matching_features(cls, methods, fields)
            total = len(methods) + len(fields)
            if total > 0 and matches / total >= min_similarity:
                group.add(cls)

        return group, methods, fields

    def _count_common_features(self, class1: ast.ClassDef, class2: ast.ClassDef):
        """Count features (methods and fields) common to both classes"""
        common_methods = []
        common_fields = []

        # Compare methods
        methods1 = {m.name: m for m in self.subclass_methods[class1]}
        methods2 = {m.name: m for m in self.subclass_methods[class2]}
        
        for name, method1 in methods1.items():
            if name in methods2 and ast.dump(method1) == ast.dump(methods2[name]):
                common_methods.append(method1)

        # Compare fields
        fields1 = {f.targets[0].attr: f for f in self.subclass_fields[class1]}
        fields2 = {f.targets[0].attr: f for f in self.subclass_fields[class2]}
        
        for name, field1 in fields1.items():
            if name in fields2 and ast.dump(field1.value) == ast.dump(fields2[name].value):
                common_fields.append(field1)

        return len(common_methods) + len(common_fields), common_methods, common_fields

    def _count_matching_features(self, cls: ast.ClassDef, methods: list, fields: list):
        """Count how many of the given features match in the class"""
        matches = 0
        
        # Check methods
        cls_methods = {m.name: m for m in self.subclass_methods[cls]}
        for method in methods:
            if (method.name in cls_methods and 
                ast.dump(method) == ast.dump(cls_methods[method.name])):
                matches += 1

        # Check fields
        cls_fields = {f.targets[0].attr: f for f in self.subclass_fields[cls]}
        for field in fields:
            field_name = field.targets[0].attr
            if (field_name in cls_fields and 
                ast.dump(field.value) == ast.dump(cls_fields[field_name].value)):
                matches += 1

        return matches

    def _create_intermediate_class(self, name: str, methods: list, fields: list):
        """Create new intermediate class with the shared features"""
        # Create __init__ method
        init_body = [create_super_init_call()]  # Using utility function
        init_body.extend(copy.deepcopy(fields))
        
        init_method = ast.FunctionDef(
            name='__init__',
            args=ast.arguments(
                posonlyargs=[],
                args=[ast.arg(arg='self')],
                kwonlyargs=[],
                kw_defaults=[],
                defaults=[]
            ),
            body=init_body,
            decorator_list=[]
        )

        # Create class body
        body = [init_method]
        body.extend(copy.deepcopy(methods))

        # Create class
        new_class = ast.ClassDef(
            name=name,
            bases=[ast.Name(id=self.target_class_node.name, ctx=ast.Load())],
            keywords=[],
            body=body or [ast.Pass()],
            decorator_list=[]
        )

        return ast.fix_missing_locations(new_class)

    def _add_import(self, container: NodeContainer, class_name: str, file_path: str):
        """Add import statement if needed"""
        # Check if import already exists
        for node in container.nodes:
            if isinstance(node, ast.ImportFrom):
                if any(alias.name == class_name for alias in node.names):
                    return

        # Create new import
        module_name = os.path.splitext(os.path.basename(self.file_path))[0]
        import_node = ast.ImportFrom(
            module=module_name,
            names=[ast.alias(name=class_name, asname=None)],
            level=0
        )
        container.nodes.insert(0, import_node)

    def _update_inheritance(self, subclass: ast.ClassDef, container: NodeContainer, new_class_name: str):
        """Update the inheritance of a subclass"""
        for base in subclass.bases:
            if isinstance(base, ast.Name):
                if container.lookup_alias(base.id) == self.target_class_node.name:
                    base.id = new_class_name

    def _remove_common_features(self, subclass: ast.ClassDef, methods: list, fields: list):
        """Remove features that were moved to intermediate class"""
        # Remove methods
        method_names = {m.name for m in methods}
        subclass.body = [
            node for node in subclass.body
            if not (
                isinstance(node, ast.FunctionDef) and 
                node.name in method_names and
                any(ast.dump(node) == ast.dump(m) for m in methods)
            )
        ]

        # Remove fields from __init__
        init_method = next(
            (m for m in subclass.body if isinstance(m, ast.FunctionDef) and m.name == "__init__"),
            None
        )
        if init_method:
            field_info = {(f.targets[0].attr, ast.dump(f.value)) for f in fields}
            init_method.body = [
                stmt for stmt in init_method.body
                if not (
                    isinstance(stmt, ast.Assign) and
                    isinstance(stmt.targets[0], ast.Attribute) and
                    (stmt.targets[0].attr, ast.dump(stmt.value)) in field_info
                )
            ]

class CollapseHierarchy(Refactor):
    def __init__(self, base: dict[str, NodeContainer], location):
        super().__init__(base, location)
        # Get target's immediate parent classes
        self.parent_classes = self._get_parent_classes()
        
    def _get_parent_classes(self) -> list[ast.ClassDef]:
        """Get immediate parent classes of target class"""
        parents = []
        base_names = [
            self.target_node_container.lookup_alias(base)
            for base in get_str_bases(self.target_class_node.bases)
        ]
        
        for container in self.result.values():
            for node in container.nodes:
                if isinstance(node, ast.ClassDef) and node.name in base_names:
                    parents.append(node)
        return parents

    def is_possible(self) -> bool:
        """Check if hierarchy collapse is possible"""
        # Must have both parents and subclasses
        return len(self.parent_classes) >= 1 and len(self.subclasses) >= 1

    def _update_inheritance(self, subclass: ast.ClassDef):
        """Update subclass to inherit from parent instead of target"""
        subclass_file, subclass_container = get_container_for_node(subclass, self.result)
        if not subclass_container:
            return

        # For each base class in subclass that references our target
        for base in subclass.bases:
            if isinstance(base, ast.Name):
                if subclass_container.lookup_alias(base.id) == self.target_class_node.name:
                    parent_class = self.parent_classes[0]  # Using first parent for now
                    parent_file, parent_container = get_container_for_node(parent_class, self.result)

                    # If parent is in different file, need to add/check import
                    if parent_file != subclass_file:
                        module_name = os.path.splitext(os.path.basename(parent_file))[0]
                        
                        # Check for existing import and alias
                        import_alias = None
                        import_exists = False
                        for node in subclass_container.nodes:
                            if isinstance(node, ast.ImportFrom):
                                if node.module == module_name:
                                    for alias in node.names:
                                        if alias.name == parent_class.name:
                                            import_exists = True
                                            import_alias = alias.asname if alias.asname else alias.name
                                            break
                                    if import_exists:
                                        break
                        
                        if not import_exists:
                            # Add new import
                            import_node = ast.ImportFrom(
                                module=module_name,
                                names=[ast.alias(name=parent_class.name, asname=None)],
                                level=0
                            )
                            subclass_container.nodes.insert(0, import_node)
                            import_alias = parent_class.name
                        
                        # Update inheritance to use correct name/alias
                        base.id = import_alias
                    else:
                        # Same file, use parent class name directly
                        base.id = parent_class.name

    def _push_down_features(self, subclass: ast.ClassDef):
        """Push target's methods and fields to subclass if not already defined"""
        # Push down methods
        target_methods = find_normal_methods(self.target_class_node.body)
        for method in target_methods:
            if not method_exists_in_class(method, subclass):
                subclass.body.append(copy.deepcopy(method))

        # Push down fields
        target_fields = find_instance_fields(self.target_class_node.body)
        for field in target_fields:
            # Check if field exists or is used in subclass
            field_name = field.targets[0].attr
            checker = InstanceFieldOccurrenceChecker(field_name)
            checker.visit(subclass)
            
            if not checker.defined and checker.occurred:
                # Use InitMethodInjector to properly add field
                injector = InitMethodInjector(content=copy.deepcopy(field))
                injector.visit(subclass)

    def do(self):
        """Perform the hierarchy collapse refactoring"""
        if not self.is_possible():
            return

        # Process each subclass
        for subclass in self.subclasses:
            # Update inheritance to skip target class
            self._update_inheritance(subclass)
            
            # Push down features from target class
            self._push_down_features(subclass)

            # Fix any missing locations in modified nodes
            ast.fix_missing_locations(subclass)

        # Remove the target class
        self.result[self.file_path].nodes.remove(self.target_class_node)

class MakeSuperclassAbstract(Refactor):
    def __init__(self, base: dict[str, NodeContainer], location):
        super().__init__(base, location)

        self.non_abstract_superclasses = [
            superclass
            for superclass in self.superclasses
            if not check_inherit_abc(superclass)
        ]

    def is_possible(self):
        return len(self.non_abstract_superclasses) >= 1

    def do(self):
        if not self.is_possible():
            return

        superclass = choice(self.non_abstract_superclasses)

        checker = AbstractMethodDecoratorChecker()
        checker.visit(superclass)

        if checker.found:
            superclass.bases.append(
                ast.Name(
                    id="ABC",
                    ctx=ast.Load()
                )
            )


class MakeSuperclassConcrete(Refactor):
    def __init__(self, base: dict[str, NodeContainer], location):
        super().__init__(base, location)

        self.abstract_superclasses = [
            superclass
            for superclass in self.superclasses
            if check_inherit_abc(superclass)
        ]

    def is_possible(self):
        return len(self.abstract_superclasses) >= 1

    def do(self):
        if not self.is_possible():
            return

        superclass = choice(self.abstract_superclasses)

        checker = AbstractMethodDecoratorChecker()
        checker.visit(superclass)

        if not checker.found:
            check_inherit_abc(superclass, remove_abc=True)


class ReplaceInheritanceWithDelegation(Refactor):
    def __init__(self, base: dict[str, NodeContainer], location):
        super().__init__(base, location)

        self.methods = find_normal_methods(self.target_class_node.body)

    def is_possible(self):
        return len(self.superclasses) >= 1

    def do(self):
        if not self.is_possible():
            return

        superclass = choice(self.superclasses)
        delegate_attribute_name = f'riwd_{superclass.name}'

        # create delegation
        assignment_node = ast.Assign(
            targets=[
                ast.Attribute(
                    value=ast.Name(id='self', ctx=ast.Load()),
                    attr=delegate_attribute_name,
                    ctx=ast.Store()
                )
            ],
            value=ast.Call(
                func=ast.Name(id=superclass.name,ctx=ast.Load()),
                args=[],
                keywords=[]
            )
        )

        init_method_injector = InitMethodInjector(content=assignment_node)
        init_method_injector.visit(self.target_class_node)

        # delete inheritance
        superclass_index = -1
        for idx, base in enumerate(self.superclasses):
            if base.name == superclass.name:
                superclass_index = idx
                break
        self.target_class_node.bases.pop(superclass_index)

        superclass_methods = find_normal_methods(superclass.body)
        methods_to_be_replaced = []

        target_class_method_names = [method.name for method in self.methods]

        for method in superclass_methods:
            if not (method.name in target_class_method_names):
                methods_to_be_replaced.append(method.name)

        replacer = SelfMethodOccurrenceReplacer(
            methods_to_be_replaced=methods_to_be_replaced,
            attr_name=delegate_attribute_name
        )
        replacer.visit(self.target_class_node)


class ReplaceDelegationWithInheritance(Refactor):
    def __init__(self, base: dict[str, NodeContainer], location):
        super().__init__(base, location)

        self.delegation_infos = []  # (idx, self attr name, class name)
        self.target_class_init_method = None
        for node in self.target_class_node.body:
            if isinstance(node, ast.FunctionDef) and node.name == "__init__":
                self.target_class_init_method = node
                break

        if self.target_class_init_method is not None:
            for idx, stmt in enumerate(self.target_class_init_method.body):
                if isinstance(stmt, ast.Assign) and is_direct_self_attr(stmt.targets[0]) and isinstance(stmt.value, ast.Call):
                    if isinstance(stmt.value.func, ast.Name):
                        # case 1: self.a = A()
                        # check A is a real class
                        if stmt.value.func.id in self.class_names:
                            self.delegation_infos.append((idx, stmt.targets[0].attr, stmt.value.func.id))
                    elif isinstance(stmt.value.func, ast.Attribute):
                        # case 2: self.a = module.A()
                        if stmt.value.func.attr in self.class_names:
                            self.delegation_infos.append((idx, stmt.targets[0].attr, stmt.value.func.attr))
                    else:
                        raise Exception(f"stmt.value.func with {type(stmt.value.func)} is not handled.")


    def is_possible(self):
        return len(self.delegation_infos) >= 1

    def do(self):
        if not self.is_possible():
            return

        idx, attr, class_name = choice(self.delegation_infos)

        # delegation 제거
        if self.target_class_init_method:
            self.target_class_init_method.body.pop(idx)
            if len(self.target_class_init_method.body) == 0:
                self.target_class_init_method.body.append(ast.Pass())

        # inheritance 추가
        self.target_class_node.bases.append(
            ast.Name(
                id=class_name,
                ctx=ast.Load()
            )
        )

        # occurrence 찾아서 self.으로 변경
        replacer = SelfAttributeOccurrenceReplacer(attr_name=attr)
        replacer.visit(self.target_class_node)


REFACTORING_TYPES = [
    PushDownMethod,
    PullUpMethod,
    IncreaseMethodAccess,
    DecreaseMethodAccess,
    PushDownField,
    PullUpField,
    IncreaseFieldAccess,
    DecreaseFieldAccess,
    ExtractHierarchy,
    CollapseHierarchy,
    MakeSuperclassAbstract,
    MakeSuperclassConcrete,
    ReplaceInheritanceWithDelegation,
    ReplaceDelegationWithInheritance,
]
