import ast
import copy
from abc import ABC, abstractmethod
from itertools import combinations
from random import choice

from src.core.parsing import NodeContainer
from src.utils.ast_utils import find_normal_methods, find_instance_fields, MethodRenamer, \
    MethodOccurrenceChecker, InstanceFieldOccurrenceChecker, InitMethodInjector, is_direct_self_attr, \
    SelfAttributeOccurrenceReplacer, check_inherit_abc, AbstractMethodDecoratorChecker, \
    is_super_init_call, get_str_bases, is_property_decorated_method, check_functions_equal, add_method_to_class, \
    delete_method_from_class, SelfOccurrenceReplacer


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

    def _get_all_descendants(self, current_node: ast.ClassDef):
        current_subclasses = []

        for node_container in self.result.values():
            for node in node_container.nodes:
                if isinstance(node, ast.ClassDef):
                    if any(
                            node_container.lookup_alias(base) == current_node.name
                            for base in get_str_bases(node.bases)
                    ):
                        current_subclasses.append(node)

        more_subclasses = []
        for subclass in current_subclasses:
            more_subclasses.extend(self._get_all_descendants(subclass))

        return current_subclasses + more_subclasses

    def __execute_post_processes(self):
        # refactoring 수행 이후 후처리 작업들

        if len(self.target_class_node.body) == 0:
            self.target_class_node.body.append(ast.Pass())

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
    def _do(self):
        ...

    def do(self):
        if not self.is_possible():
            return

        self._do()
        self.__execute_post_processes()

    def undo(self):
        self.result = self.base


# Method Level Refactorings
class PushDownMethod(Refactor):
    def __init__(self, base: dict[str, NodeContainer], location):
        super().__init__(base, location)
        self.methods = find_normal_methods(self.target_class_node.body)

    def is_possible(self):
        return len(self.methods) >= 1 and len(self.subclasses) >= 1

    def _do(self):
        method_node = choice(self.methods)
        is_property_method = is_property_decorated_method(method_node)

        method_idx = self.target_class_node.body.index(method_node)
        self.target_class_node.body.pop(method_idx)

        # 다른 method에서 쓰이고 있으면 중단
        self_occurrence_checker = MethodOccurrenceChecker(method_node.name, is_property_method)
        self_occurrence_checker.visit(self.target_class_node)
        if self_occurrence_checker.occurred:
            self.target_class_node.body.insert(method_idx, method_node)
            return

        moved = False
        # add method to subclasses of target class
        for node in self.subclasses:
            # find the occurrence of method
            checker = MethodOccurrenceChecker(method_node.name, is_property_method)
            checker.visit(node)

            if checker.occurred and not checker.defined:
                new_method = copy.deepcopy(method_node)
                add_method_to_class(node, new_method)
                moved = True

        if moved:
            # remove method from target class only when a move occurs
            self.result[self.file_path].nodes[self.node_idx] = self.target_class_node
        else:
            # otherwise, revert.
            self.target_class_node.body.insert(method_idx, method_node)


class PullUpMethod(Refactor):
    def __init__(self, base: dict[str, NodeContainer], location):
        super().__init__(base, location)
        self.methods = find_normal_methods(self.target_class_node.body)

    def is_possible(self):
        return len(self.methods) >= 1 and len(self.superclasses) >= 1

    def _get_siblings(self, immediate_superclass: ast.ClassDef, method: ast.FunctionDef):
        siblings = []
        for node_container in self.result.values():
            for node in node_container.nodes:
                if isinstance(node, ast.ClassDef):
                    if any(
                            node_container.lookup_alias(base) == immediate_superclass.name
                            for base in get_str_bases(node.bases)
                    ):
                        siblings.append(node)

        siblings_with_same_method_defs = []
        for sibling in siblings:
            for node in sibling.body:
                if isinstance(node, ast.FunctionDef) and node.name == method.name:
                    if check_functions_equal(node, method):
                        siblings_with_same_method_defs.append(sibling)
                        break

        return siblings_with_same_method_defs

    def _do(self):
        method_node = choice(self.methods)
        immediate_superclass = choice(self.superclasses)
        is_property_method = is_property_decorated_method(method_node)

        # superclass에 이미 method가 있으면 pull up 안함
        checker = MethodOccurrenceChecker(method_node.name, is_property_method)
        checker.visit(immediate_superclass)
        if checker.defined:
            return

        siblings = [self.target_class_node] + self._get_siblings(immediate_superclass, method_node)
        for sibling in siblings:
            delete_method_from_class(sibling, method_node)

        add_method_to_class(
            class_node=immediate_superclass,
            method_node=copy.deepcopy(method_node)
        )


# foo() -> public, _foo() -> protected, __foo() -> private
# Decrease Accessibility: foo() -> _foo() or _foo() -> __foo()
class DecreaseMethodAccess(Refactor):
    def __init__(self, base: dict[str, NodeContainer], location):
        super().__init__(base, location)
        self.public_or_protected_methods = [
            method for method in find_normal_methods(self.target_class_node.body)
            if not method.name.startswith("__")
        ]

    def is_possible(self):
        return len(self.public_or_protected_methods) >= 1

    def _do(self):
        method_node = choice(self.public_or_protected_methods)
        is_property_method = is_property_decorated_method(method_node)

        old_name = method_node.name
        new_name = "_" + method_node.name

        for node in self.target_class_node.body:
            if isinstance(node, ast.FunctionDef):
                if method_node.name == new_name:
                    return

        renamer = MethodRenamer(old_name, new_name, is_property_method)

        # Change the all occurrence of method in classes, including all descendants
        classes = [
            self.target_class_node,
            *self._get_all_descendants(self.target_class_node)
        ]

        for item in classes:
            renamer.visit(item)


# Increase Accessibility: _foo() -> foo() or __foo() -> _foo()
class IncreaseMethodAccess(Refactor):
    def __init__(self, base: dict[str, NodeContainer], location):
        super().__init__(base, location)
        self.protected_or_private_methods = [
            method for method in find_normal_methods(self.target_class_node.body)
            if method.name.startswith("_")
        ]

    def is_possible(self):
        return len(self.protected_or_private_methods) >= 1

    def _do(self):
        method_node = choice(self.protected_or_private_methods)
        is_property_method = is_property_decorated_method(method_node)

        old_name = method_node.name
        new_name = method_node.name[1:]  # remove first underscore

        for node in self.target_class_node.body:
            if isinstance(node, ast.FunctionDef):
                if method_node.name == new_name:
                    return

        renamer = MethodRenamer(old_name, new_name, is_property_method)

        # Change the all occurrence of method in classes, including all descendants
        classes = [
            self.target_class_node,
            *self._get_all_descendants(self.target_class_node)
        ]
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

    def _do(self):
        if not self.is_possible():
            return

        refactor_occurred = False
        pushable_fields = []
        for field in self.fields:
            field_name = field.targets[0].attr
            if not self.is_field_used_by_parent(field_name):
                pushable_fields.append(field)

        # find candidate field for pushdown
        pushdown_candidates = []
        for candidate_field_name in pushable_fields:
            checker = InstanceFieldOccurrenceChecker(field_name=candidate_field_name)
            pushable_subclass = None
            is_first = True
            is_only = False
            for subclass in self.subclasses:
                checker.visit(node)
                if checker.occurred and not checker.defined:
                    if is_first:
                        pushdown_subclass = subclass
                        is_only = True
                    else:
                        is_only = False
            if is_only:
                pushdown_candidates.append((candidate_field_name, pushable_subclass))

        field_node, pushdown_subclass = choice(pushdown_candidates)
        field_name = field_node.targets[0].attr  # get name from self.field_name

        # Find __init__ method
        init_idx = None
        for idx, node in enumerate(self.target_class_node.body):
            if isinstance(node, ast.FunctionDef) and node.name == "__init__":
                init_idx = idx
                break

        # Find or create __init__ in subclass
        init_method = None
        for child in pushable_subclass.body:
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
            pushdown_subclass.body.insert(0, init_method)

        # Add field assignment after super().__init__()
        new_field = copy.deepcopy(field_node)
        init_method.body.insert(1, new_field)
        
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
        # Only finds the first superclass (doesn't work for multiple superclasses)
        self.superclass = None
        superclass_names = [
            self.target_node_container.lookup_alias(base)
            for base in get_str_bases(self.target_class_node.bases)
        ]
        
        # Look for superclass definition
        for node_container in self.result.values():
            for node in node_container.nodes:
                if isinstance(node, ast.ClassDef) and node.name in superclass_names:
                    self.superclass = node
                    break
            if self.superclass:
                break

    def create_init_method(self, has_superclass: bool) -> ast.FunctionDef:
        """Create new __init__ method, with super().__init__() only if class has superclass"""
        # Basic __init__ structure
        init_method = ast.FunctionDef(
            name='__init__',
            args=ast.arguments(
                posonlyargs=[],
                args=[ast.arg(
                    arg='self', 
                    lineno=1, 
                    col_offset=0,
                    end_lineno=1,
                    end_col_offset=4,
                    annotation=None,
                )],
                kwonlyargs=[],
                kw_defaults=[],
                defaults=[],
                vararg=None,
                kwarg=None
            ),
            body=[],  # We'll fill this based on whether there's a superclass
            decorator_list=[],
            lineno=1,
            col_offset=4,
            end_lineno=3,
            end_col_offset=4
        )

        # Add super().__init__() call only if class has a superclass
        if has_superclass:
            super_call = ast.Expr(
                value=ast.Call(
                    func=ast.Attribute(
                        value=ast.Call(
                            func=ast.Name(id='super', ctx=ast.Load()),
                            args=[],
                            keywords=[]
                        ),
                        attr='__init__',
                        ctx=ast.Load()
                    ),
                    args=[],
                    keywords=[]
                ),
                lineno=2,
                col_offset=8,
                end_lineno=2,
                end_col_offset=23,
            )
            init_method.body.append(super_call)

        return init_method

    def get_field_value(self, field_node: ast.Assign) -> str:
        """Get string representation of field's value"""
        return ast.unparse(field_node.value)

    def find_sibling_classes(self) -> list[ast.ClassDef]:
        """Find other classes that inherit from same superclass"""
        siblings = []
        if not self.superclass:
            return siblings
            
        for node_container in self.result.values():
            for node in node_container.nodes:
                if isinstance(node, ast.ClassDef):
                    # Check if this class inherits from same superclass
                    if any(
                            self.target_node_container.lookup_alias(base) == self.superclass.name
                            for base in get_str_bases(node.bases)
                    ):
                        siblings.append(node)
        return siblings

    def get_field_info(self, field_node: ast.Assign):
        """Get field name and value"""
        field_name = field_node.targets[0].attr
        field_value = self.get_field_value(field_node)
        return field_name, field_value

    def check_field_in_siblings(self, field_name: str, field_value: str) -> bool:
        """Check if field exists with same value in sibling classes"""
        # 같은 field가 sibling에 존재하는데 다른 값이면 src 불가:
        # 같은 field가 없거나, 있으면 같은 값이어야 진행
        # 아니면 같은 값을 가진 subclass에서만 삭제하고 올리면 되려나?
        can_refactor = True
        siblings = self.find_sibling_classes()
        for sibling in siblings:
            if sibling == self.target_class_node:
                continue
                
            sibling_fields = find_instance_fields(sibling.body)
            for field in sibling_fields:
                sib_name, sib_value = self.get_field_info(field)
                if sib_name == field_name and sib_value != field_value:
                    can_refactor = False
        return can_refactor

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

        # Check each field
        for field in self.fields:
            field_name, field_value = self.get_field_info(field)
            
            # Field shouldn't exist in parent # If field exists with different value in siblings, can't refactor
            if (not self.is_field_in_parent(field_name) and self.check_field_in_siblings(field_name, field_value)):
                return True
                
        return False

    def _do(self):
        # refactored = False
        remaining_fields = list(self.fields)
        while remaining_fields: # Randomly selects field.
            field = choice(remaining_fields)
            remaining_fields.remove(field)
            field_name, field_value = self.get_field_info(field)
            print(f"field_name: {field_name}")
            
            if (not self.is_field_in_parent(field_name) and 
                self.check_field_in_siblings(field_name, field_value)):
                
                # Add field to parent's __init__
                init_method = next(
                    (node for node in self.superclass.body
                     if isinstance(node, ast.FunctionDef) and 
                     node.name == "__init__"),
                    None
                )
                
                if init_method is None:
                    has_superclass = len(self.superclass.bases) > 0
                    init_method = self.create_init_method(has_superclass)
                    self.superclass.body.insert(0, init_method)
                
                new_field = copy.deepcopy(field)
                init_method.body.append(new_field)
                
                # Remove field from all subclasses
                siblings = self.find_sibling_classes()
                for sibling in siblings:
                    sibling_init = next(
                        (node for node in sibling.body
                         if isinstance(node, ast.FunctionDef) and 
                         node.name == "__init__"),
                        None
                    )
                    if sibling_init:
                        for stmt in sibling_init.body[:]:
                            if (isinstance(stmt, ast.Assign) and
                                isinstance(stmt.targets[0], ast.Attribute) and
                                stmt.targets[0].attr == field_name):
                                sibling_init.body.remove(stmt)
                
                # refactored = True
                break

        # self.result[self.file_path].refactored = refactored

# Python doesn't strictly enforce this, so may be a problem. 
class IncreaseFieldAccess(Refactor):
   def __init__(self, base: dict[str, NodeContainer], location):
       super().__init__(base, location)
       self.fields = find_instance_fields(self.target_class_node.body)
       # Only get fields that aren't private (don't start with __)
       self.increasable_fields = [
           field for field in self.fields
           if not field.targets[0].attr.startswith("__")
       ]

   def is_possible(self):
       return len(self.increasable_fields) >= 1

   def _do(self):
       field_node = choice(self.increasable_fields)
       old_name = field_node.targets[0].attr
       new_name = "_" + old_name  # Add underscore
       # refactored = False

       # Change field name in target class's __init__
       for node in self.target_class_node.body:
           if isinstance(node, ast.FunctionDef) and node.name == "__init__":
               for stmt in node.body:
                   if (isinstance(stmt, ast.Assign) and 
                       isinstance(stmt.targets[0], ast.Attribute) and
                       stmt.targets[0].attr == old_name):
                       stmt.targets[0].attr = new_name
                       # refactored = True

               # Also update any field usage within __init__
               for stmt in ast.walk(node):
                   if (isinstance(stmt, ast.Attribute) and 
                       isinstance(stmt.value, ast.Name) and
                       stmt.value.id == 'self' and 
                       stmt.attr == old_name):
                       stmt.attr = new_name

       # Update field usage in all methods of target class and subclasses
       classes_to_update = [self.target_class_node] + self.subclasses
       for class_node in classes_to_update:
           for node in class_node.body:
               if isinstance(node, ast.FunctionDef):
                   for stmt in ast.walk(node):
                       if (isinstance(stmt, ast.Attribute) and 
                           isinstance(stmt.value, ast.Name) and
                           stmt.value.id == 'self' and 
                           stmt.attr == old_name):
                           stmt.attr = new_name

       # self.result[self.file_path].refactored = refactored


class DecreaseFieldAccess(Refactor):
   def __init__(self, base: dict[str, NodeContainer], location):
       super().__init__(base, location)
       self.fields = find_instance_fields(self.target_class_node.body)
       # Only get fields that start with at least one underscore
       self.decreasable_fields = [
           field for field in self.fields
           if field.targets[0].attr.startswith("_")
       ]

   def is_possible(self):
       return len(self.decreasable_fields) >= 1

   def _do(self):
       field_node = choice(self.decreasable_fields)
       old_name = field_node.targets[0].attr
       new_name = old_name[1:] if old_name.startswith('_') else old_name
       # refactored = False

       # Change field name in target class's __init__
       for node in self.target_class_node.body:
           if isinstance(node, ast.FunctionDef) and node.name == "__init__":
               for stmt in node.body:
                   if (isinstance(stmt, ast.Assign) and 
                       isinstance(stmt.targets[0], ast.Attribute) and
                       stmt.targets[0].attr == old_name):
                       stmt.targets[0].attr = new_name
                       # refactored = True

               # Also update any field usage within __init__
               for stmt in ast.walk(node):
                   if (isinstance(stmt, ast.Attribute) and 
                       isinstance(stmt.value, ast.Name) and
                       stmt.value.id == 'self' and 
                       stmt.attr == old_name):
                       stmt.attr = new_name

       # Update field usage in all methods of target class and subclasses
       classes_to_update = [self.target_class_node] + self.subclasses
       for class_node in classes_to_update:
           for node in class_node.body:
               if isinstance(node, ast.FunctionDef):
                   for stmt in ast.walk(node):
                       if (isinstance(stmt, ast.Attribute) and 
                           isinstance(stmt.value, ast.Name) and
                           stmt.value.id == 'self' and 
                           stmt.attr == old_name):
                           stmt.attr = new_name

       # self.result[self.file_path].refactored = refactored


## Class Level Refactorings
# Just accounts for simple field assignments and not all kinds of initializations
# 1. Is it okay to just do pass if there are no common methods and fields? Shouldn't we do super init?
class ExtractHierarchy(Refactor):
    def __init__(self, base: dict[str, NodeContainer], location):
        super().__init__(base, location)
        # Initialize dictionaries to store methods and fields for each subclass
        self.subclass_methods = {}  # class_node -> list of method nodes (excluding __init__)
        self.subclass_fields = {}  # class_node -> list of field assignments

        for node in self.subclasses:
            # Collect methods excluding __init__
            methods = [n for n in node.body if isinstance(n, ast.FunctionDef) and n.name != '__init__']
            self.subclass_methods[node] = methods
            # Collect instance fields
            self.subclass_fields[node] = find_instance_fields(node.body)

    def count_common_features(self, class1: ast.ClassDef, class2: ast.ClassDef) -> tuple[int, list, list]:
        """Count common methods and fields between two classes."""
        # Get methods from both classes
        methods1 = {m.name: m for m in self.subclass_methods[class1]}
        methods2 = {m.name: m for m in self.subclass_methods[class2]}
        common_methods = []

        # Compare methods with the same name for identical bodies
        for name in methods1:
            if name in methods2:
                if ast.dump(methods1[name]) == ast.dump(methods2[name]):
                    common_methods.append(methods1[name])

        # Get fields from both classes
        fields1 = {self.get_field_info(f)[0]: f for f in self.subclass_fields[class1]}
        fields2 = {self.get_field_info(f)[0]: f for f in self.subclass_fields[class2]}
        common_fields = []

        # Compare fields with the same name and value
        for name in set(fields1.keys()) & set(fields2.keys()):
            if self.get_field_info(fields1[name])[1] == self.get_field_info(fields2[name])[1]:
                common_fields.append(fields1[name])

        # Total common features
        total_common_features = len(common_methods) + len(common_fields)
        return total_common_features, common_methods, common_fields

    def get_field_info(self, field_node: ast.Assign) -> tuple[str, str]:
        """Extract field name and value from an assignment node."""
        field_name = field_node.targets[0].attr
        field_value = ast.unparse(field_node.value)
        return field_name, field_value

    def find_best_subclass_group(self) -> tuple[set[ast.ClassDef], list[ast.FunctionDef], list[ast.Assign]]:
        """Identify the largest group of subclasses sharing common features."""
        if len(self.subclasses) < 2:
            return set(), [], []

        # Initialize variables to track the best group
        best_score = -1
        best_pair = None
        best_methods = []
        best_fields = []

        # Compare all pairs to find the best initial pair
        for c1, c2 in combinations(self.subclasses, 2):
            score, methods, fields = self.count_common_features(c1, c2)
            if score > best_score:
                best_score = score
                best_pair = (c1, c2)
                best_methods = methods
                best_fields = fields

        if not best_pair:
            return set(), [], []

        # Start building the group with the best pair
        best_group = set(best_pair)
        current_methods = best_methods
        current_fields = best_fields

        # Try adding more classes to the group
        for cls in set(self.subclasses) - best_group:
            # Check if the class shares all current common methods
            methods_in_cls = {m.name: m for m in self.subclass_methods[cls]}
            shares_all_methods = all(
                cm.name in methods_in_cls and ast.dump(cm) == ast.dump(methods_in_cls[cm.name])
                for cm in current_methods
            )

            # Check if the class shares all current common fields
            fields_in_cls = {self.get_field_info(f)[0]: f for f in self.subclass_fields[cls]}
            shares_all_fields = all(
                field_name in fields_in_cls and
                field_value == self.get_field_info(fields_in_cls[field_name])[1]
                for field_name, field_value in (self.get_field_info(cf) for cf in current_fields)
            )

            # Add class to the group if it shares all common features
            if shares_all_methods and shares_all_fields:
                best_group.add(cls)

        return best_group, current_methods, current_fields

    def create_super_init_call(self) -> ast.Expr:
        """Create a super().__init__() call expression."""
        return ast.Expr(
            value=ast.Call(
                func=ast.Attribute(
                    value=ast.Call(
                        func=ast.Name(id='super', ctx=ast.Load()),
                        args=[],
                        keywords=[]
                    ),
                    attr='__init__',
                    ctx=ast.Load()
                ),
                args=[],
                keywords=[]
            )
        )

    def create_new_init_method(self, fields: list[ast.Assign]) -> ast.FunctionDef:
        """Create a new __init__ method with super().__init__() and field assignments."""
        return ast.FunctionDef(
            name='__init__',
            args=ast.arguments(
                posonlyargs=[],
                args=[ast.arg(arg='self')],
                kwonlyargs=[],
                kw_defaults=[],
                defaults=[]
            ),
            body=[self.create_super_init_call()] + fields,
            decorator_list=[]
        )

    def create_new_class(self, name: str, methods: list[ast.FunctionDef], fields: list[ast.Assign]) -> ast.ClassDef:
        """Create a new class with the given methods and fields."""
        body = methods.copy()
        if fields:
            init_method = self.create_new_init_method(fields)
            body.insert(0, init_method)
        elif not body:
            body = [ast.Pass()]

        return ast.ClassDef(
            name=name,
            bases=[ast.Name(id=self.target_class_node.name, ctx=ast.Load())],
            keywords=[],
            body=body,
            decorator_list=[]
        )

    def ensure_subclass_init_calls_super(self, subclass: ast.ClassDef):
        """Ensure the subclass's __init__ method calls super().__init__()."""
        init_method = next(
            (m for m in subclass.body if isinstance(m, ast.FunctionDef) and m.name == '__init__'),
            None
        )
        if init_method and not any(is_super_init_call(stmt) for stmt in init_method.body):
            init_method.body.insert(0, self.create_super_init_call())

    def is_possible(self):
        """Check if src is possible."""
        return len(self.subclasses) >= 2

    def _do(self):
        """Perform the Extract Hierarchy src."""
        # Find best group using greedy approach
        group, methods, fields = self.find_best_subclass_group()

        if group:
            new_class_name = f"Sub{self.target_class_node.name}"

            # Create new class with common features
            new_class = self.create_new_class(
                new_class_name,
                copy.deepcopy(methods),
                copy.deepcopy(fields)
            )

            # Update selected subclasses
            for subclass in group:
                # Update inheritance
                subclass.bases = [ast.Name(id=new_class_name, ctx=ast.Load())]

                # Remove common methods and fields
                self.remove_common_features(subclass, methods, fields)
                # Ensure __init__ calls super().__init__()
                self.ensure_subclass_init_calls_super(subclass)

            # Add new class after the target class
            insert_idx = next(
                i for i, node in enumerate(self.result[self.file_path].nodes)
                if node == self.target_class_node
            ) + 1
            self.result[self.file_path].nodes.insert(insert_idx, new_class)

            # Fix missing locations in the modified nodes
            for item in self.result.values():
                for idx, node in enumerate(item.nodes):
                    item.nodes[idx] = ast.fix_missing_locations(node)

    def remove_common_features(self, cls: ast.ClassDef,
                               methods: list[ast.FunctionDef],
                               fields: list[ast.Assign]):
        """Remove common methods and fields from the subclass."""
        # Remove common methods
        common_method_names = {m.name for m in methods}
        cls.body = [
            node for node in cls.body
            if not (
                    isinstance(node, ast.FunctionDef) and
                    node.name in common_method_names and
                    any(ast.dump(node) == ast.dump(m) for m in methods)
            )
        ]

        # Remove common fields from __init__
        init_method = next(
            (m for m in cls.body if isinstance(m, ast.FunctionDef) and m.name == "__init__"),
            None
        )
        if init_method:
            common_field_info = {self.get_field_info(f) for f in fields}
            init_method.body = [
                stmt for stmt in init_method.body
                if not (
                        isinstance(stmt, ast.Assign) and
                        self.get_field_info(stmt) in common_field_info
                )
            ]


class CollapseHierarchy(Refactor):
    def __init__(self, base: dict[str, NodeContainer], location):
        super().__init__(base, location)
        # Get target's parent class
        self.parent_class = None
        parent_names = [
            self.target_node_container.lookup_alias(base)
            for base in get_str_bases(self.target_class_node.bases)
        ]
        # Need to handle case of multiple classes with same name
        for node_container in self.result.values():
            for node in node_container.nodes:
                if isinstance(node, ast.ClassDef) and node.name in parent_names:
                    self.parent_class = node
                    break

    def is_possible(self):
        # Must have parent class and subclasses
        return bool(self.parent_class and self.subclasses)

    def _do(self):
        # Move target's methods to parent class
        for method in self.target_class_node.body:
            if isinstance(method, ast.FunctionDef):
                if method.name == '__init__':
                    # Find parent's __init__
                    parent_init = next((m for m in self.parent_class.body
                                        if isinstance(m, ast.FunctionDef) and
                                        m.name == '__init__'), None)

                    if parent_init:
                        # Get target's field initializations (excluding super call)
                        target_statements = [
                            stmt for stmt in method.body
                            if not is_super_init_call(stmt)
                        ]

                        # Find where super().__init__() is called in target
                        super_call_index = next(
                            (i for i, stmt in enumerate(method.body)
                             if is_super_init_call(stmt)),
                            0
                        )

                        # Split target's statements into before and after super call -> Is this okay?
                        before_super = target_statements[:super_call_index]
                        after_super = target_statements[super_call_index:]

                        # Create new init method with properly ordered initialization
                        new_init = ast.FunctionDef(
                            name='__init__',
                            args=parent_init.args,
                            body=(before_super +
                                  parent_init.body +
                                  after_super),
                            decorator_list=[],
                            # Add location information
                            lineno=1,
                            col_offset=4,
                            end_lineno=1,
                            end_col_offset=4
                        )

                        # Fix location info for all nodes in the new method
                        ast.fix_missing_locations(new_init)

                        # Replace parent's init with merged init
                        self.parent_class.body.remove(parent_init)
                        self.parent_class.body.insert(0, new_init)

                        # Fix locations for the entire class
                        ast.fix_missing_locations(self.parent_class)

        # Update subclasses to inherit from parent
        for subclass in self.subclasses:
            subclass.bases = [ast.Name(id=self.parent_class.name, ctx=ast.Load())]

        # Remove target class
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

    def _do(self):
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

    def _do(self):
        superclass = choice(self.abstract_superclasses)

        checker = AbstractMethodDecoratorChecker()
        checker.visit(superclass)

        if not checker.found:
            check_inherit_abc(superclass, remove_abc=True)


class ReplaceInheritanceWithDelegation(Refactor):
    def __init__(self, base: dict[str, NodeContainer], location):
        super().__init__(base, location)


    def is_possible(self):
        return len(self.superclasses) >= 1

    def _do(self):
        superclass_expr = choice(self.target_class_node.bases) # this may be aliased
        delegate_attr_name = f"riwd_{ast.unparse(superclass_expr).replace('.', '_')}"

        # Create delegation
        assignment_node = ast.Assign(
            targets=[
                ast.Attribute(
                    value=ast.Name(id="self", ctx=ast.Load()),
                    attr=delegate_attr_name,
                    ctx=ast.Store()
                )
            ],
            value=ast.Call(
                func=superclass_expr,
                args=[],
                keywords=[],
            )
        )

        init_method_injector = InitMethodInjector(content=assignment_node)
        init_method_injector.visit(self.target_class_node)

        # Delete inheritance
        self.target_class_node.bases.remove(superclass_expr)

        superclass_name = self.target_node_container.lookup_alias(list(get_str_bases([superclass_expr]))[0])
        superclass_node = None
        for superclass in self.superclasses:
            if superclass.name == superclass_name:
                superclass_node = superclass
                break

        if superclass_node is None:
            raise Exception("Cannot find superclass '%s'" % superclass_name)

        superclass_methods = [method.name for method in find_normal_methods(superclass_node.body)]
        ignore_methods = [method.name for method in find_normal_methods(self.target_class_node.body)]
        methods_to_be_replaced = [item for item in superclass_methods if item not in ignore_methods]

        # does not consider the case len(targets) >= 2
        superclass_fields = [
            field.targets[0].attr
            for field in find_instance_fields(superclass_node.body)
            if len(field.targets) == 1
        ]
        ignore_fields = [
            field.targets[0].attr
            for field in find_instance_fields(self.target_class_node.body)
            if len(field.targets) == 1
        ]
        fields_to_be_replaced = [item for item in superclass_fields if item not in ignore_fields]

        replacer = SelfOccurrenceReplacer(
            methods_to_be_replaced,
            fields_to_be_replaced,
            delegate_attr_name
        )
        replacer.visit(self.target_class_node)


class ReplaceDelegationWithInheritance(Refactor):
    def __init__(self, base: dict[str, NodeContainer], location):
        super().__init__(base, location)

        self.delegations = []
        self.target_class_init_method = None
        for node in self.target_class_node.body:
            if isinstance(node, ast.FunctionDef) and node.name == "__init__":
                self.target_class_init_method = node
                break

        if self.target_class_init_method is not None:
            for idx, stmt in enumerate(self.target_class_init_method.body):
                if isinstance(stmt, ast.Assign) and is_direct_self_attr(stmt.targets[0]) and isinstance(stmt.value, ast.Call):
                    class_expr = stmt.value.func
                    class_name = self.target_node_container.lookup_alias(
                        list(get_str_bases([class_expr]))[0]
                    )
                    if class_name in self.class_names:
                        self.delegations.append((idx, stmt.targets[0].attr, class_expr))

    def is_possible(self):
        return self.target_class_init_method is not None and len(self.delegations) >= 1

    def _do(self):
        idx, attr, class_expr = choice(self.delegations)

        # delegation 제거
        if self.target_class_init_method:
            self.target_class_init_method.body.pop(idx)
            if len(self.target_class_init_method.body) == 0:
                self.target_class_init_method.body.append(ast.Pass())

        # inheritance 추가
        self.target_class_node.bases.append(class_expr)

        # occurrence 찾아서 self.으로 변경
        replacer = SelfAttributeOccurrenceReplacer(attr_name=attr)
        replacer.visit(self.target_class_node)


REFACTORING_TYPES = [
    # PushDownMethod,
    # PullUpMethod,
    # DecreaseMethodAccess,
    # IncreaseMethodAccess,
    # PushDownField,
    # PullUpField,
    # IncreaseFieldAccess,
    # DecreaseFieldAccess,
    # ExtractHierarchy,
    # CollapseHierarchy,
    # MakeSuperclassAbstract,
    # MakeSuperclassConcrete,
    # ReplaceInheritanceWithDelegation,
    ReplaceDelegationWithInheritance,
]
