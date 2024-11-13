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
