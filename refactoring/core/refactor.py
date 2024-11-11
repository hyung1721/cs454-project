import ast
import copy
from abc import ABC, abstractmethod
from random import choice

from refactoring.core.parsing import TreeDetail
from refactoring.utils.ast_utils import find_normal_methods, MethodRenamer, MethodOccurrenceChecker


class Refactor(ABC):
    def __init__(self, base: dict[str, TreeDetail], location):
        self.base = base
        self.result = copy.deepcopy(base)
        self.file_path = location[0]
        self.node_idx = location[1]

        target_class_node = self.result[self.file_path].nodes[self.node_idx]
        if not isinstance(target_class_node, ast.ClassDef):
            raise Exception(f"{target_class_node} is not an instance of ast.ClassDef")
        self.target_class_node = target_class_node

        self.subclasses = []
        for tree_detail in self.result.values():
            for node in tree_detail.nodes:
                if isinstance(node, ast.ClassDef):
                    if any(isinstance(base, ast.Name) and base.id == self.target_class_node.name for base in node.bases):
                        self.subclasses.append(node)

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
    def __init__(self, base: dict[str, TreeDetail], location):
        super().__init__(base, location)
        self.methods = find_normal_methods(self.target_class_node.body)

    def is_possible(self):
        return len(self.methods) >= 1 and len(self.subclasses) >= 1

    def do(self):
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

        self.result[self.file_path].refactored = True


class PullUpMethod(Refactor):
    def __init__(self, base: dict[str, TreeDetail], location):
        super().__init__(base, location)
        self.methods = find_normal_methods(self.target_class_node.body)

        self.superclasses = []
        superclass_names = [base.id for base in self.target_class_node.bases if isinstance(base, ast.Name)]
        for tree_detail in self.result.values():
            for node in tree_detail.nodes:
                if isinstance(node, ast.ClassDef) and node.name in superclass_names:
                    self.superclasses.append(node)

    def is_possible(self):
        return len(self.methods) >= 1 and len(self.superclasses) >= 1

    def do(self):
        method_node = choice(self.methods)

        # remove method from target class
        self.target_class_node.body.remove(method_node)
        self.result[self.file_path].nodes[self.node_idx] = self.target_class_node

        # add method to subclasses of target class
        for node in self.superclasses:
            new_method = copy.deepcopy(method_node)
            node.body.append(new_method)

        self.result[self.file_path].refactored = True


# foo() -> public, _foo() -> protected, __foo() -> private
# Increase Accessibility: foo() -> _foo() or _foo() -> __foo()
class IncreaseMethodAccess(Refactor):
    def __init__(self, base: dict[str, TreeDetail], location):
        super().__init__(base, location)
        self.public_or_protected_methods = [
            method for method in find_normal_methods(self.target_class_node.body)
            if not method.name.startswith("__")
        ]

    def is_possible(self):
        return len(self.public_or_protected_methods) >= 1

    def do(self):
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
    def __init__(self, base: dict[str, TreeDetail], location):
        super().__init__(base, location)
        self.protected_or_private_methods = [
            method for method in find_normal_methods(self.target_class_node.body)
            if method.name.startswith("_")
        ]

    def is_possible(self):
        return len(self.protected_or_private_methods) >= 1

    def do(self):
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
    def is_possible(self):
        return False

    def do(self):
        pass


class PullUpField(Refactor):
    def is_possible(self):
        return False

    def do(self):
        pass


class IncreaseFieldAccess(Refactor):
    def is_possible(self):
        return False

    def do(self):
        pass


class DecreaseFieldAccess(Refactor):
    def is_possible(self):
        return False

    def do(self):
        pass


REFACTORING_TYPES = [
    PushDownMethod,
    # PullUpMethod,
    # IncreaseMethodAccess,
    # DecreaseMethodAccess,
    # PushDownField,
    # PullUpField,
    # IncreaseFieldAccess,
    # DecreaseFieldAccess
]
