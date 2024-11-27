import ast
from random import choice

from src.core.parsing import parse_library
from src.core.refactor import REFACTORING_TYPES
from collections import namedtuple
import eval.metrics as mt

Metric_Log = namedtuple('Metric_Log', ['before', 'after'])

if __name__ == '__main__':
    node_container_dict = parse_library("./target_libraries/library_example1")

    # collect all classes from library
    classes = []
    # Metric Eval
    metric_types = mt.get_metric_types_in_paper()

    for file_path, node_container in node_container_dict.items():
        for idx, node in enumerate(node_container.nodes):
            if isinstance(node, ast.ClassDef):
                classes.append((file_path, idx))

    refactoring_count = 0

    # target_class_location = choice(classes)
    target_class_location = classes[2]
    _refactoring = choice(REFACTORING_TYPES)
    print(target_class_location, _refactoring)

    metric_values_before = mt.calculate_metrices(target_class_location, metric_types)

    refactor = _refactoring(base=node_container_dict, location=target_class_location)

    if refactor.is_possible():
        refactor.do()

        for item in refactor.result.values():
            for node in item.nodes:
                print(ast.unparse(node))
   
        metric_values_after = mt.calculate_metrices(refactor.result.values(), metric_types)
        better_metric = {}
        stable_metric = {}
        worse_metric = {}

        # TODO: 비교 과정 자체도 함수화 - 신동환, 2024-11-27
        for metric_value_type in metric_values_after:
            metric_value_before = metric_values_before[metric_value_type]
            metric_value_after = metric_values_after[metric_value_type]
            if metric_value_after > metric_value_before:
                better_metric[metric_value_type] = Metric_Log(metric_value_before, metric_value_after)
            elif metric_value_after == metric_value_before: #오차율 0.1%까지 고려해야할지도?
                stable_metric[metric_value_type] = Metric_Log(metric_value_before, metric_value_after)
            else:
                worse_metric[metric_value_type] = Metric_Log(metric_value_before, metric_value_after)
        
        # TODO: metric 계산 & metric이 오르지 않으면 undo   
        # refactor.undo()
        #
        # print("##### After undo #####")
        # for node in list(refactor.result.values())[0].nodes:
        #     print(ast.unparse(node))
