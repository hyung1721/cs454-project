import ast
from random import shuffle
from typing import List, Dict

from src.core.parsing import parse_library
from src.core.refactor import REFACTORING_TYPES
import constant as Constant
from constant import Iteration_Result, Statistics_Unit
from evaluation import Evaluation
from MetricType import MetricType

def get_metric_types_in_paper():
    metric_paper_list = []
    for metric_Type in MetricType:
        if metric_Type == MetricType.PAPER:
            break
        metric_paper_list.append(metric_Type)
    return metric_paper_list

def calculate_metrics(node_container_dict, metric_type_list):
    result = {}
    for metric_type in metric_type_list:
        result[metric_type] = Evaluation(node_container_dict, metric_type)
    return result

def compare_metrics(metrics_dict_before, metrics_dict_after):
    iteration_result = Iteration_Result({}, {}, {})
    for metric_type, evaluation_after in metrics_dict_after.items():
        evaluation_before = metrics_dict_before[metric_type]
        if evaluation_after > evaluation_before:
            iteration_result.better_metric[metric_type] = evaluation_after
        elif evaluation_after == evaluation_before:
            iteration_result.static_metric[metric_type] = evaluation_after
        else:
            iteration_result.worse_metric[metric_type] = evaluation_after
    return iteration_result

def make_statistics(result_logs: List[Iteration_Result], metric_type_list):
    statistics: Dict[MetricType, Statistics_Unit] = {}
    
    for metric_type in metric_type_list:
        statistics[metric_type] = Statistics_Unit(0, 0, 0)

    for result_log in result_logs:
        for metric_type in metric_type_list:
            if metric_type in result_log.better_metric:
                statistics[metric_type].better_count+=1
            elif metric_type in result_log.static_metric:
                statistics[metric_type].static_count+=1
            elif metric_type in result_log.worse_metric:
                statistics[metric_type].worse_count+=1
    return statistics

def fitness_function_improves(iteration_result: Iteration_Result):
    return not iteration_result.better_metric

# Main Function
if __name__ == '__main__':
    node_container_dict = parse_library(Constant.Target_Library)
    classes_origin = []
    # collect all classes from library
    for file_path, node_container in node_container_dict.items():
        for idx, node in enumerate(node_container.nodes):
            if isinstance(node, ast.ClassDef):
                classes_origin.append((file_path, idx))
    # Metric Types for Eval
    metric_types = get_metric_types_in_paper()
    
    # Paper Algorithm Start
    refactoring_count = 0

    metrics_origin = calculate_metrics(node_container_dict, metric_types)
    result_logs: List[Iteration_Result] = []

    while(refactoring_count < Constant.DESIRED_REFACTORING_COUNT):
        is_first = True
        classes = classes_origin.copy()
        while(classes.count > 0):
            target_class = classes.pop()
            
            refactoring_methods = REFACTORING_TYPES.copy()
            shuffle(refactoring_methods)
            while(refactoring_methods.count > 0):
                refactoring_method = refactoring_methods.pop()
                refactor = refactoring_method(base=node_container_dict, location=target_class)
                if refactor.is_possible():
                    refactor.do()
                    metrics_before = metrics_origin if is_first else result_logs[refactoring_count-1]
                    metrics_after = calculate_metrics(refactor.result, metric_types)
                    iteration_result = Iteration_Result(metrics_before, metrics_after)
                    if(fitness_function_improves(iteration_result)):
                        is_first = False
                        result_logs.append(iteration_result)
                        refactoring_count+=1
                    else:
                        refactor.undo()
    
    # Print Table3 in Paper
    statistics = make_statistics(result_logs)
    for metric_type, statistic in statistics.items():
        print(f"{metric_type} {statistic.better_count}↑ {statistic.worse_count}↓")