import ast


def find_normal_methods(body: list[ast.stmt]):
    return [item for item in body if isinstance(item, ast.FunctionDef) and not (item.name.startswith("__") and item.name.endswith("__"))]


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
