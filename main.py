import ast
from random import shuffle
from typing import List, Dict

from src.core.parsing import parse_library
from src.core.refactor import REFACTORING_TYPES
import constant
from constant import Iteration_Result, Statistics_Unit
from constant import Better_Idx, Static_Idx, Worse_Idx
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
        statistics[metric_type] = [0, 0, 0]

    for result_log in result_logs:
        for metric_type in metric_type_list:
            if metric_type in result_log.better_metric:
                statistics[metric_type][Better_Idx]+=1
            elif metric_type in result_log.static_metric:
                statistics[metric_type][Static_Idx]+=1
            elif metric_type in result_log.worse_metric:
                statistics[metric_type][Worse_Idx]+=1
    return statistics

def fitness_function_improves(iteration_result: Iteration_Result):
    return len(iteration_result.better_metric) > 0

def is_finish_cycle(refactoring_count):
    return refactoring_count >= constant.DESIRED_REFACTORING_COUNT

# Main Function
if __name__ == '__main__':
    node_container_dict = parse_library(constant.Target_Library_Path)
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
    try_count = 0

    metrics_origin = calculate_metrics(node_container_dict, metric_types)
    result_logs: List[Iteration_Result] = []

    while(is_finish_cycle(refactoring_count) == False):
        print(f"Start New: {refactoring_count}")
        is_first = True
        classes = classes_origin.copy()
        while(len(classes) > 0 and is_finish_cycle(refactoring_count) == False):
            target_class = classes.pop()
            refactoring_methods = REFACTORING_TYPES.copy()
            shuffle(refactoring_methods) # Random
            while(len(refactoring_methods) > 0 and is_finish_cycle(refactoring_count) == False):
                refactoring_method = refactoring_methods.pop()
                refactor = refactoring_method(base=node_container_dict, location=target_class)
                if refactor.is_possible():
                    refactor.do()
                    try_count+=1
                    metrics_before = metrics_origin if is_first else metrics_before
                    metrics_after = calculate_metrics(refactor.result, metric_types)
                    iteration_result = compare_metrics(metrics_before, metrics_after)
                    if(fitness_function_improves(iteration_result)):
                        is_first = False
                        result_logs.append(iteration_result)
                        refactoring_count+=1
                        metrics_before = metrics_after
                        print(f"{refactoring_count}th Refactoring_Success: {refactoring_method}")
                    else:
                        refactor.undo()
                    if(try_count%100 == 0):
                        print(f"We tried {try_count} times and succeed {refactoring_count} times")
                        print(f"classes remains {len(classes)} and refactoring_methods remains {len(refactoring_methods)}")
                
    
    # Print Table3 in Paper
    statistics = make_statistics(result_logs, metric_types)
    for metric_type, statistic in statistics.items():
        print(f"{metric_type} {statistic[Better_Idx]}↑ {statistic[Static_Idx]}= {statistic[Worse_Idx]}↓")