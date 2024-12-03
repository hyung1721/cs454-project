import ast
# Add src. when merging
from ast import ClassDef, FunctionDef, Assign, Attribute, Name

from src.core.parsing import NodeContainer


# Utility functions
def find_method_in_class(method_name: str, class_node: ast.ClassDef):
    """Find method with given name in class"""
    for node in class_node.body:
        if isinstance(node, ast.FunctionDef) and node.name == method_name:
            return node
    return None

def method_exists_in_class(method: ast.FunctionDef, class_node: ast.ClassDef) -> bool:
    """Check if method exists in class by name"""
    return find_method_in_class(method.name, class_node) is not None

def get_container_for_node(node: ast.AST, containers: dict[str, NodeContainer]):
    """Find which container has the given node and return (file_path, container)"""
    for file_path, container in containers.items():
        if node in container.nodes:
            return file_path, container
    return None, None


def class_redefines_field(class_node: ClassDef, field_name: str) -> bool:
    """Check if class redefines the given field in its __init__"""
    for node in class_node.body:
        if isinstance(node, FunctionDef) and node.name == "__init__":
            for stmt in node.body:
                if (isinstance(stmt, Assign) and 
                    isinstance(stmt.targets[0], Attribute) and
                    isinstance(stmt.targets[0].value, Name) and
                    stmt.targets[0].value.id == 'self' and
                    stmt.targets[0].attr == field_name):
                    return True
    return False

def update_field_references(class_node: ClassDef, old_name: str, new_name: str):
    """Update all references to the field in a class's methods"""
    for node in class_node.body:
        if isinstance(node, FunctionDef):
            for stmt in ast.walk(node):
                if (isinstance(stmt, Attribute) and 
                    isinstance(stmt.value, Name) and
                    stmt.value.id == 'self' and 
                    stmt.attr == old_name):
                    stmt.attr = new_name

def get_all_subclasses(class_node: ClassDef, containers: dict[str, NodeContainer]) -> list[ClassDef]:
    """Get all direct subclasses from any file in the project"""
    subclasses = []
    for container in containers.values():
        for node in container.nodes:
            if isinstance(node, ClassDef):
                if any(
                    container.lookup_alias(base) == class_node.name
                    for base in get_str_bases(get_valid_bases(node))
                ):
                    subclasses.append(node)
    return subclasses

def update_descendant_chain(class_node: ClassDef, old_name: str, new_name: str, containers: dict[str, NodeContainer]):
    """Recursively update field references in descendants until a redefinition is found"""
    subclasses = get_all_subclasses(class_node, containers)
    
    for subclass in subclasses:
        if class_redefines_field(subclass, old_name):
            continue
        
        update_field_references(subclass, old_name, new_name)
        update_descendant_chain(subclass, old_name, new_name, containers)

def create_super_init_call() -> ast.Expr:
    """Create ast node for super().__init__() call"""
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

def find_method_in_class(method_name: str, class_node: ast.ClassDef):
    """Find method with given name in class"""
    for node in class_node.body:
        if isinstance(node, ast.FunctionDef) and node.name == method_name:
            return node
    return None

def method_exists_in_class(method: ast.FunctionDef, class_node: ast.ClassDef) -> bool:
    """Check if method exists in class by name"""
    return find_method_in_class(method.name, class_node) is not None

def get_container_for_node(node: ast.AST, containers):
    """Find which container has the given node and return (file_path, container)"""
    for file_path, container in containers.items():
        if node in container.nodes:
            return file_path, container
    return None, None


def find_normal_methods(body: list[ast.stmt]):
    return [item for item in body if isinstance(item, ast.FunctionDef) and not (item.name.startswith("__") and item.name.endswith("__"))]

def find_instance_fields(body: list[ast.stmt]) -> list[ast.Assign]:
    """Find all instance field definitions (self.field) in __init__"""
    fields = []
    
    # Find the __init__ method
    for node in body:
        if isinstance(node, ast.FunctionDef) and node.name == "__init__":
            # Look for self.field assignments in __init__ body
            for stmt in node.body:
                if isinstance(stmt, ast.Assign):
                    # Check if assigning to self.something
                    for target in stmt.targets:
                        if (isinstance(target, ast.Attribute) and 
                            isinstance(target.value, ast.Name) and 
                            target.value.id == 'self'):
                            fields.append(stmt)
            break  # No need to look further after finding __init__
                            
    return fields


def is_super_init_call(stmt: ast.stmt) -> bool:
    """Check if a statement is a call to super().__init__()."""
    return (
        isinstance(stmt, ast.Expr) and
        isinstance(stmt.value, ast.Call) and
        isinstance(stmt.value.func, ast.Attribute) and
        isinstance(stmt.value.func.value, ast.Call) and
        isinstance(stmt.value.func.value.func, ast.Name) and
        stmt.value.func.value.func.id == 'super' and
        stmt.value.func.attr == '__init__'
    )


def is_direct_self_attr(node: ast.expr):
    return isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name) and node.value.id == "self"


def check_inherit_abc(node: ast.ClassDef, remove_abc: bool = False):
    result = False

    abc_base_idx = -1
    for base_idx, base in enumerate(get_valid_bases(node)):
        if isinstance(base, ast.Name) and base.id == "ABC":
            abc_base_idx = base_idx
            result = True
            break

        if isinstance(base, ast.Attribute):
            if isinstance(base.value, ast.Name) and base.value.id == "abc" and base.attr == "ABC":
                abc_base_idx = base_idx
                result = True
                break

    abc_keyword_idx = -1
    for keyword_idx, keyword in enumerate(node.keywords):
        if keyword.arg == "metaclass":
            if isinstance(keyword.value, ast.Name) and keyword.value.id == "ABCMeta":
                abc_keyword_idx = keyword_idx
                result = True
                break

            if isinstance(keyword.value, ast.Attribute):
                if isinstance(keyword.value.value, ast.Name) and keyword.value.value.id == "abc" and keyword.value.attr == "ABCMeta":
                    abc_keyword_idx = keyword_idx
                    result = True
                    break

    if remove_abc:
        if abc_base_idx != -1:
            node.bases.pop(abc_base_idx)
        if abc_keyword_idx != -1:
            node.keywords.pop(abc_keyword_idx)

    return result


def get_valid_bases(node: ast.ClassDef):
    return [base for base in node.bases if isinstance(base, ast.Name | ast.Attribute)]


def get_str_bases(bases: list[ast.expr]):
    for base in bases:
        if isinstance(base, ast.Name):
            yield base.id
        elif isinstance(base, ast.Attribute):
            yield base.attr
        elif isinstance(base, ast.Subscript):
            continue
        else:
            raise Exception(f"{base} is not an ast.Name or ast.Attribute")
        
class DependencyVisitor(ast.NodeVisitor):
    def __init__(self):
        super().__init__()
        self.dependencies = set()

    def visit_Attribute(self, node):
        if isinstance(node.value, ast.Name) and node.value.id == 'self':
            self.dependencies.add(node.attr)
        self.generic_visit(node)
        
    def visit_Call(self, node):
        if isinstance(node.func, ast.Attribute) and \
           isinstance(node.func.value, ast.Name) and \
           node.func.value.id == 'self':
            self.dependencies.add(node.func.attr)
        self.generic_visit(node)

def find_self_dependencies(ast_node: ast.AST) -> set[str]:
    """Find all attribute and method references through 'self' in an AST node"""
    visitor = DependencyVisitor()
    visitor.visit(ast_node)
    return visitor.dependencies


def is_property_decorated_method(node: ast.FunctionDef):
    return any(
        decorator.id == "property"
        for decorator in node.decorator_list
        if isinstance(decorator, ast.Name)
    )

def check_nodes_equal(node1, node2):
    if type(node1) != type(node2):
        return False

    if not hasattr(node1, "_fields"):
        return node1 == node2

    for field in node1._fields:
        value1 = getattr(node1, field)
        value2 = getattr(node2, field)

        if isinstance(value1, list):
            if len(value1) != len(value2):
                return False

            for v1, v2 in zip(value1, value2):
                if not check_nodes_equal(v1, v2):
                    return False
        else:
            if not check_nodes_equal(value1, value2):
                return False

    return True


def check_functions_equal(node1: ast.FunctionDef, node2: ast.FunctionDef):
    if len(node1.body) != len(node2.body):
        return False

    for body1, body2 in zip(node1.body, node2.body):
        if not check_nodes_equal(body1, body2):
            return False

    for decorator1, decorator2 in zip(node1.decorator_list, node2.decorator_list):
        if not check_nodes_equal(decorator1, decorator2):
            return False

    if not check_nodes_equal(node1.args, node2.args):
        return False

    if not check_nodes_equal(node1.returns, node2.returns):
        return False

    if node1.type_comment != node2.type_comment:
        return False

    return True


def is_pass_like_node(node: ast.AST):
    if isinstance(node, ast.Pass):
        return True
    elif isinstance(node, ast.Expr) and isinstance(node.value, ast.Constant) and node.value == ast.Ellipsis:
        return True
    else:
        return False


def add_method_to_class(class_node: ast.ClassDef, method_node: ast.FunctionDef):
    class_node.body.append(method_node)

    class_node.body = [
        node
        for node in class_node.body
        if not is_pass_like_node(node)
    ]


def delete_method_from_class(class_node: ast.ClassDef, method_node: ast.FunctionDef):
    for idx, node in enumerate(class_node.body):
        if isinstance(node, ast.FunctionDef) and node.name == method_node.name:
            class_node.body.pop(idx)
            break

    if len(class_node.body) == 0:
        class_node.body.append(ast.Pass())


class MethodRenamer(ast.NodeTransformer):
    def __init__(self, old_name: str, new_name: str, as_property: bool = False):
        self.old_name = old_name
        self.new_name = new_name
        self.as_property = as_property

    def visit_FunctionDef(self, node):
        if node.name == self.old_name:
            node.name = self.new_name

        return self.generic_visit(node)

    def visit_Call(self, node):
        if not self.as_property:
            if isinstance(node.func, ast.Attribute):
                if node.func.attr == self.old_name:
                    node.func.attr = self.new_name
        return self.generic_visit(node)

    def visit_Attribute(self, node):
        if self.as_property:
            if is_direct_self_attr(node) and node.attr == self.old_name:
                node.attr = self.new_name
        return self.generic_visit(node)


class MethodOccurrenceChecker(ast.NodeVisitor):
    def __init__(self, method_name: str, as_property: bool = False):
        self.method_name = method_name
        self.as_property = as_property
        self.occurred = False
        self.defined = False

    def visit_FunctionDef(self, node):
        if not self.defined and node.name == self.method_name:
            self.defined = True
        self.generic_visit(node)

    def visit_Call(self, node):
        if not self.as_property:
            if not self.occurred and is_direct_self_attr(node.func) and node.func.attr == self.method_name:
                    self.occurred = True
        self.generic_visit(node)

    def visit_Attribute(self, node):
        if self.as_property:
            if not self.occurred and is_direct_self_attr(node) and node.attr == self.method_name:
                self.occurred = True
        self.generic_visit(node)


# This checks the occurrence of callings of method in the class
class MethodSelfOccurrenceChecker(ast.NodeVisitor):
    def __init__(self, method_name: str):
        self.method_name = method_name
        self.occurred = False

    def visit_Call(self, node):
        if not self.occurred and is_direct_self_attr(node.func) and node.func.attr == self.method_name:
            self.occurred = True
        self.generic_visit(node)



class InstanceFieldOccurrenceChecker(ast.NodeVisitor):
    def __init__(self, field_name: str):
        self.field_name = field_name
        self.occurred = False  # Field is used
        self.defined = False   # Field is defined in __init__

    def visit_FunctionDef(self, node):
        if node.name == "__init__":
            for stmt in node.body:
                if isinstance(stmt, ast.Assign):
                    for target in stmt.targets:
                        # For __init__, we check for definitions
                        if self.is_self_attr(target):
                            self.defined = True
        self.generic_visit(node)

    def visit_Attribute(self, node):
        # For any attribute access, we check for usage
        if self.is_self_attr(node):
            self.occurred = True
        self.generic_visit(node)
        
    def is_self_attr(self, node):
        """Check if node is self.field_name"""
        return (isinstance(node, ast.Attribute) and 
                isinstance(node.value, ast.Name) and 
                node.value.id == 'self' and 
                node.attr == self.field_name)


class InitMethodInjector(ast.NodeTransformer):
    def __init__(self, content: ast.Assign):
        if not isinstance(content, ast.Assign):
            raise Exception(f"The content of init method must be an assignment, but {type(content)} is given")

        self.content = content

    def visit_ClassDef(self, node):
        has_init_method = False
        for item in node.body:
            if isinstance(item, ast.FunctionDef) and item.name == "__init__":
                has_init_method = True
                item.body.append(self.content)
                break

        if not has_init_method:
            init_method = ast.FunctionDef(
                name="__init__",
                args=ast.arguments(
                    args=[ast.arg(arg='self', annotation=None)],
                    posonlyargs=[],
                    kwonlyargs=[],
                    kw_defaults=[],
                    defaults=[]
                ),
                body=[self.content],
                decorator_list=[]
            )
            node.body.insert(0, init_method)

        ast.fix_missing_locations(node)

        return self.generic_visit(node)


class SelfAttributeOccurrenceReplacer(ast.NodeTransformer):
    def __init__(self, attr_name: str):
        self.attr_name = attr_name

    def visit_Attribute(self, node):
        if isinstance(node.value, ast.Name):
            if node.value.id == "self" and node.attr == self.attr_name:
                node = ast.Name(id="self", ctx=ast.Load())
        return self.generic_visit(node)


# With given attr_name
# Replace occurrences like self.a, self.foo()
# to self.{attr_name}.a, self.{attr_name}.foo()
class SelfOccurrenceReplacer(ast.NodeTransformer):
    def __init__(self, methods_to_be_replaced: list[str], fields_to_be_replaced: list[str], attr_name: str):
        self.methods_to_be_replaced = methods_to_be_replaced
        self.fields_to_be_replaced = fields_to_be_replaced
        self.attr_name = attr_name

    def visit_Attribute(self, node):
        # self.a -> self.{attr_name}.a
        if is_direct_self_attr(node) and node.attr in self.fields_to_be_replaced:
            node.value = ast.Attribute(
                value=ast.Name(id='self', ctx=ast.Load()),
                attr=self.attr_name,
                ctx=ast.Load()
            )
        return self.generic_visit(node)

    def visit_Call(self, node):
        # self.foo() -> self.{attr_name}.foo()
        if is_direct_self_attr(node.func) and node.func.attr in self.methods_to_be_replaced:
            node.func.value = ast.Attribute(
                value=ast.Name(id='self', ctx=ast.Load()),
                attr=self.attr_name,
                ctx=ast.Load()
            )
        return self.generic_visit(node)


class AbstractMethodDecoratorChecker(ast.NodeVisitor):
    def __init__(self):
        self.found = False

    def visit_FunctionDef(self, node):
        for decorator in node.decorator_list:
            if isinstance(decorator, ast.Name) and decorator.id == "abstractmethod":
                self.found = True
                break

            if isinstance(decorator, ast.Attribute):
                if isinstance(decorator.value, ast.Name) and decorator.value.id == "abc" and decorator.attr == "abstractmethod":
                    self.found = True
                    break

        self.generic_visit(node)
