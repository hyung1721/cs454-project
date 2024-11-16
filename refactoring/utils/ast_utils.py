import ast


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


def is_direct_self_attr(node):
    return isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name) and node.value.id == "self"


class MethodRenamer(ast.NodeTransformer):
    def __init__(self, old_name: str, new_name: str):
        self.old_name = old_name
        self.new_name = new_name

    def visit_FunctionDef(self, node):
        if node.name == self.old_name:
            node.name = self.new_name

        return self.generic_visit(node)

    def visit_Call(self, node):
        if isinstance(node.func, ast.Attribute):
            if node.func.attr == self.old_name:
                node.func.attr = self.new_name
        return self.generic_visit(node)


class MethodOccurrenceChecker(ast.NodeVisitor):
    def __init__(self, method_name: str):
        self.method_name = method_name
        self.occurred = False
        self.overridden = False

    def visit_FunctionDef(self, node):
        if not self.overridden and node.name == self.method_name:
            self.overridden = True
        self.generic_visit(node)

    def visit_Call(self, node):
        if not self.occurred and isinstance(node.func, ast.Attribute):
            if node.func.attr == self.method_name:
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


class SelfMethodOccurrenceReplacer(ast.NodeTransformer):
    def __init__(self, methods_to_be_replaced: list[str], attr_name: str):
        self.methods_to_be_replaced = methods_to_be_replaced
        self.attr_name = attr_name

    def visit_Call(self, node):
        if is_direct_self_attr(node.func):
            # self.foo() 같은 형태만 고려 -> node.func.value가 무조건 ast.Name 노드
            # self.x.foo()는 inheritance가 아님
            if node.func.attr in self.methods_to_be_replaced:
                node.func.value = ast.Attribute(
                    value=ast.Name(id='self', ctx=ast.Load()),
                    attr=self.attr_name,
                    ctx=ast.Load()
                )

        return self.generic_visit(node)


class SelfAttributeOccurrenceReplacer(ast.NodeTransformer):
    def __init__(self, attr_name: str):
        self.attr_name = attr_name

    def visit_Attribute(self, node):
        if isinstance(node.value, ast.Name):
            if node.value.id == "self" and node.attr == self.attr_name:
                node = ast.Name(id="self", ctx=ast.Load)
        return self.generic_visit(node)
