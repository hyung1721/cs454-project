import collections
import operator

import eval.ast_helper.ast_parser as parser

import ast
from itertools import combinations
from typing import List, Dict

class ClassParser:
    def __init__(self, cls):
        self.cls_structure = list(cls.values())[0]
        self.funcs_name = list(self.cls_structure['functions'].keys())
        self.vars_name = self.cls_structure['variables']

    def k(self) -> int:
        return len(self.cls_structure["functions"])
    
    def l(self) -> int:
        return len(self.cls_structure["variables"])
    
    def x(self, i) -> int: # x_i
        func_name = self.funcs_name[i]
        func = self.cls_structure['functions'][func_name]
        return len(func['variables'])
    
    def M(self): # M_I(c)
        # return dict of methods(dict[dict])
        return self.cls_structure['functions']
    
    def I(self, i) -> List[str]: # I_i
        func_name = self.funcs_name[i]
        func = self.cls_structure['functions'][func_name]
        return func['variables']
    
    def A(self) -> List[str]:
        return self.cls_structure['variables']
    
    def CBO_count(self):
        return self.cls_structure['cbo_count']
    
    def RFC_count(self):
        return self.cls_structure['rfc_count']
       
def cau(m1:Dict, m2:Dict) -> int:
    if len(set(m1['variables']) & set(m2['variables'])) > 0:
        return 1
    return 0
    
def intersection_of_I(I1:List[str], I2:List[str]) -> List[str]:
    return list(set(I1) & set(I2))

def union_of_I(I1:List[str], I2:List[str]) -> List[str]:
    return list(set(I1) | set(I2))

def create_structure(file_ast_node):
    # file_ast_node : ast.classDef
    module_classes = parser.get_module_classes(file_ast_node)

    result = collections.defaultdict(dict)

    for module_class in module_classes:
        class_name = parser.get_object_name(module_class)

        class_variable_names = list(parser.get_all_class_variable_names(module_class))

        class_methods = parser.get_class_methods(module_class)

        class_method_name_to_method = {
            method.name: method
            for method in class_methods
        }

        class_method_name_to_variable_names = {
            method_name: list(parser.get_all_class_variable_names_used_in_method(method))
            for method_name, method in class_method_name_to_method.items()
        }

        class_method_name_to_boundedness = {
            method_name: parser.is_class_method_bound(method)
            for method_name, method in class_method_name_to_method.items()
        }

        class_method_name_to_staticmethodness = {
            method_name: parser.is_class_method_staticmethod(method)
            for method_name, method in class_method_name_to_method.items()
        }

        class_method_name_to_classmethodness = {
            method_name: parser.is_class_method_classmethod(method)
            for method_name, method in class_method_name_to_method.items()
        }

        # new: CBO,RFC counting logic
        referenced_classes = set()
        referenced_methods = set()
        for method in class_methods:
            for node in ast.walk(method):
                if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
                    # Check if the call is on an instance or class
                    if isinstance(node.func.value, ast.Name):
                        referenced_classes.add(node.func.value.id)
                        referenced_methods.add(f"{node.func.value.id}.{node.func.attr}")
        referenced_classes.discard(class_name)
        referenced_methods = {
            method for method in referenced_methods
            if not method.startswith(f"{class_name}.")
        }

        # Calculate RFC count
        rfc_count = len(referenced_methods) + len(class_method_name_to_method)

        result[class_name]["cohesion"] = None
        result[class_name]["lineno"] = module_class.lineno
        result[class_name]["col_offset"] = module_class.col_offset
        result[class_name]["variables"] = class_variable_names
        result[class_name]["functions"] = {
            method_name: {
                "variables": class_method_name_to_variable_names[method_name],
                "bounded": class_method_name_to_boundedness[method_name],
                "staticmethod": class_method_name_to_staticmethodness[method_name],
                "classmethod": class_method_name_to_classmethodness[method_name],
            }
            for method_name in class_method_name_to_method.keys()
        }
        result[class_name]["cbo_count"] = len(referenced_classes)
        result[class_name]["rfc_count"] = rfc_count

    return ClassParser(result)

if __name__ == "__main__":
    # Example usage
    source_code = """
    class ExampleClass1(object):
        class_variable1 = 5
        class_variable2 = 6

        def func1(self):
            self.instance_variable = 6

            def inner_func(b):
                return b + 5

            local_variable = self.class_variable1

            return local_variable

        def func2(self):
            print(self.class_variable2)

        @staticmethod
        def func3(variable):
            return variable + 7

    class ExampleClass2(object):
        def func1(self):
            self.instance_variable1 = 7
    """

    module_ast_node = parser.get_ast_node_from_string(source_code)
    create_structure(module_ast_node)