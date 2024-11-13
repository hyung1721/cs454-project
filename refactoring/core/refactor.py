import ast
import copy
from abc import ABC, abstractmethod
from random import choice

from core.parsing import TreeDetail
from utils.ast_utils import find_normal_methods, find_instance_fields, MethodRenamer, MethodOccurrenceChecker, InstanceFieldOccurrenceChecker


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
    def __init__(self, base: dict[str, TreeDetail], location):
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
            if self.is_field_used_by_parent(field_name):
                print(f"Field '{field_name}' is used by parent class methods")
                return False
                
        return True

    def do(self):
        refactor_occurred = False
        field_node = choice(self.fields)
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
        self.result[self.file_path].refactored = refactor_occurred


class PullUpField(Refactor):
    def __init__(self, base: dict[str, TreeDetail], location):
        super().__init__(base, location)
        # Find fields in target class
        self.fields = find_instance_fields(self.target_class_node.body)
        
        # Find immediate superclass
        # Only finds the first superclass (doesn't work for multiple superclasses)
        self.superclass = None
        superclass_names = [base.id for base in self.target_class_node.bases 
                          if isinstance(base, ast.Name)]
        
        # Look for superclass definition
        for tree_detail in self.result.values():
            for node in tree_detail.nodes:
                if (isinstance(node, ast.ClassDef) and 
                    node.name in superclass_names):
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
            
        for tree_detail in self.result.values():
            for node in tree_detail.nodes:
                if isinstance(node, ast.ClassDef):
                    # Check if this class inherits from same superclass
                    if any(isinstance(base, ast.Name) and 
                          base.id == self.superclass.name 
                          for base in node.bases):
                        siblings.append(node)
        return siblings

    def get_field_info(self, field_node: ast.Assign):
        """Get field name and value"""
        field_name = field_node.targets[0].attr
        field_value = self.get_field_value(field_node)
        return field_name, field_value

    def check_field_in_siblings(self, field_name: str, field_value: str) -> bool:
        """Check if field exists with same value in sibling classes"""
        # 같은 field가 sibling에 존재하는데 다른 값이면 refactoring 불가:
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

    def do(self):
        refactored = False
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
                
                refactored = True
                break

        self.result[self.file_path].refactored = refactored

# Python doesn't strictly enforce this, so may be a problem. 
class IncreaseFieldAccess(Refactor):
   def __init__(self, base: dict[str, TreeDetail], location):
       super().__init__(base, location)
       self.fields = find_instance_fields(self.target_class_node.body)
       # Only get fields that aren't private (don't start with __)
       self.increasable_fields = [
           field for field in self.fields
           if not field.targets[0].attr.startswith("__")
       ]

   def is_possible(self):
       return len(self.increasable_fields) >= 1

   def do(self):
       field_node = choice(self.increasable_fields)
       old_name = field_node.targets[0].attr
       new_name = "_" + old_name  # Add underscore
       refactored = False

       # Change field name in target class's __init__
       for node in self.target_class_node.body:
           if isinstance(node, ast.FunctionDef) and node.name == "__init__":
               for stmt in node.body:
                   if (isinstance(stmt, ast.Assign) and 
                       isinstance(stmt.targets[0], ast.Attribute) and
                       stmt.targets[0].attr == old_name):
                       stmt.targets[0].attr = new_name
                       refactored = True

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

       self.result[self.file_path].refactored = refactored


class DecreaseFieldAccess(Refactor):
   def __init__(self, base: dict[str, TreeDetail], location):
       super().__init__(base, location)
       self.fields = find_instance_fields(self.target_class_node.body)
       # Only get fields that start with at least one underscore
       self.decreasable_fields = [
           field for field in self.fields
           if field.targets[0].attr.startswith("_")
       ]

   def is_possible(self):
       return len(self.decreasable_fields) >= 1

   def do(self):
       field_node = choice(self.decreasable_fields)
       old_name = field_node.targets[0].attr
       new_name = old_name[1:] if old_name.startswith('_') else old_name
       refactored = False

       # Change field name in target class's __init__
       for node in self.target_class_node.body:
           if isinstance(node, ast.FunctionDef) and node.name == "__init__":
               for stmt in node.body:
                   if (isinstance(stmt, ast.Assign) and 
                       isinstance(stmt.targets[0], ast.Attribute) and
                       stmt.targets[0].attr == old_name):
                       stmt.targets[0].attr = new_name
                       refactored = True

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

       self.result[self.file_path].refactored = refactored


REFACTORING_TYPES = [
    PushDownMethod,
    # PullUpMethod,
    # IncreaseMethodAccess,
    # DecreaseMethodAccess,
    PushDownField,
    PullUpField,
    IncreaseFieldAccess,
    DecreaseFieldAccess
]
