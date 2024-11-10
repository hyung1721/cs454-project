import ast
import copy
from abc import ABC, abstractmethod
from random import choice

from refactoring.core.parsing import TreeDetail


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

    @abstractmethod
    def is_possible(self):
        ...

    @abstractmethod
    def do(self):
        ...

    @abstractmethod
    def undo(self):
        ...


# Method Level Refactorings
class PushDownMethod(Refactor):
    def __init__(self, base: dict[str, TreeDetail], location):
        super().__init__(base, location)
        self.methods = [item for item in self.target_class_node.body
                        if isinstance(item, ast.FunctionDef) and not item.name.startswith("_")]

        self.subclasses = []
        for node in self.result[self.file_path].nodes:
            if isinstance(node, ast.ClassDef):
                if any(isinstance(base, ast.Name) and base.id == self.target_class_node.name for base in node.bases):
                    self.subclasses.append(node)

    def is_possible(self):
        return len(self.methods) >= 1 and len(self.subclasses) >= 1

    def do(self):
        method_node = choice(self.methods)

        # remove method from target class
        self.target_class_node.body.remove(method_node)
        self.result[self.file_path].nodes[self.node_idx] = self.target_class_node

        # add method to subclasses of target class
        for node in self.subclasses:
            # TODO: method를 사용하는 subclass에만 추가?
            new_method = copy.deepcopy(method_node)
            node.body.append(new_method)

        # 다른 파일에서 target class를 상속하는 경우 고려해야함

        self.result[self.file_path].refactored = True

    def undo(self):
        self.result = self.base


class PullUpMethod(Refactor):
    def __init__(self, base: dict[str, TreeDetail], location):
        super().__init__(base, location)
        self.methods = [item for item in self.target_class_node.body
                        if isinstance(item, ast.FunctionDef) and not item.name.startswith("_")]

        self.superclasses = []
        superclass_names = [base.id for base in self.target_class_node.bases if isinstance(base, ast.Name)]
        for node in self.result[self.file_path].nodes:
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
            # TODO: 모든 superclass에 추가?
            new_method = copy.deepcopy(method_node)
            node.body.append(new_method)

        # 다른 파일에 있는 class를 상속하는 경우 고려해야함 -> import문을 통해서 location을 알아내자

        self.result[self.file_path].refactored = True

    def undo(self):
        self.result = self.base


class IncreaseMethodAccess(Refactor):
    def is_possible(self):
        return False

    def do(self):
        pass

    def undo(self):
        pass


class DecreaseMethodAccess(Refactor):
    def is_possible(self):
        return False

    def do(self):
        pass

    def undo(self):
        pass


# Field Level Refactorings
class PushDownField(Refactor):
    def is_possible(self):
        return False

    def do(self):
        pass

    def undo(self):
        pass


class PullUpField(Refactor):
    def is_possible(self):
        return False

    def do(self):
        pass

    def undo(self):
        pass

class IncreaseFieldAccess(Refactor):
    def is_possible(self):
        return False

    def do(self):
        pass

    def undo(self):
        pass


class DecreaseFieldAccess(Refactor):
    def is_possible(self):
        return False

    def do(self):
        pass

    def undo(self):
        pass


REFACTORING_TYPES = [
    PushDownMethod, PullUpMethod, IncreaseMethodAccess, DecreaseMethodAccess,
    PushDownField, PullUpField, IncreaseFieldAccess, DecreaseFieldAccess
]
