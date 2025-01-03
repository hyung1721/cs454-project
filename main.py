import ast
from random import shuffle
from typing import List, Dict

from src.core.parsing import parse_library
from src.core.refactor import REFACTORING_TYPES
import constant
from constant import Iteration_Result, Statistics_Unit, DESIRED_REFACTORING_COUNT, Library_Name
from constant import Better_Idx, Static_Idx, Worse_Idx
from constant import Agreement_Idx, Dissonant_Idx, Conflicted_Idx
from evaluation import Evaluation
from MetricType import MetricType
from util import printf, Log_Save_Path
import os

def get_metric_types_in_paper():
    metric_paper_list = []
    for metric_Type in MetricType:
        if metric_Type == MetricType.PAPER:
            break
        metric_paper_list.append(metric_Type)
    return metric_paper_list

def get_coupling_metric_types():
    metric_types = []
    metric_types.append(MetricType.CBO)
    metric_types.append(MetricType.RFC)
    metric_types.append(MetricType.DIT)
    return metric_types

def get_all_metric_types():
    metric_types = []
    for metric_Type in MetricType:
        if(metric_Type == MetricType.PAPER):
            continue
        metric_types.append(metric_Type)
    return metric_types

def calculate_metrics(node_container_dict, metric_type_list):
    result = {}
    for metric_type in metric_type_list:
        result[metric_type] = Evaluation(node_container_dict, metric_type)
    return result

def compare_metrics(metrics_dict_before, metrics_dict_after):
    iteration_result = Iteration_Result({}, {}, {})
    printf("========================================")
    for metric_type, evaluation_after in metrics_dict_after.items():
        evaluation_before = metrics_dict_before[metric_type]
        printf(f"{metric_type } value is before:{evaluation_before}, after:{evaluation_after}")
        if evaluation_after > evaluation_before:
            iteration_result.better_metric[metric_type] = evaluation_after
        elif evaluation_after == evaluation_before:
            printf(f"equal value is {evaluation_after}")
            iteration_result.static_metric[metric_type] = evaluation_after
        else:
            iteration_result.worse_metric[metric_type] = evaluation_after
    return iteration_result

def make_table3_statistics(result_logs: List[Iteration_Result], metric_type_list):
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

def fitness_function_improves(iteration_result: Iteration_Result, improve_check_metric_types):
    for improve_check_metric_type in improve_check_metric_types:
        if improve_check_metric_type in iteration_result.better_metric:
            return True
    return False

def is_finish_cycle(refactoring_count):
    return refactoring_count >= constant.DESIRED_REFACTORING_COUNT

def check_static_refactoring(iteration_result: Iteration_Result, improve_check_metric_types, whole_metic_types):
    not_improve_check_metric_count = len(whole_metic_types) - len(improve_check_metric_types)
    if not_improve_check_metric_count == 0:
        return 0
    
    static_count = 0
    for metric_type in iteration_result.static_metric:
        if metric_type not in improve_check_metric_types:
            static_count+=1
    
    if static_count == not_improve_check_metric_count:
        return 1
    return 0


def check_conflicted_refactoring(iteration_result: Iteration_Result, improve_check_metric_types, whole_metic_types):
    not_improve_check_metric_count = len(whole_metic_types) - len(improve_check_metric_types)
    if not_improve_check_metric_count == 0:
        return 0
    
    conflicted_count = 0
    for metric_type in iteration_result.worse_metric:
        if metric_type not in improve_check_metric_types:
            conflicted_count+=1
            
    for metric_type in iteration_result.static_metric:
        if metric_type not in improve_check_metric_types:
            conflicted_count+=1
    
    if conflicted_count == not_improve_check_metric_count:
        return 1
    return 0


# Main Function
if __name__ == '__main__':
    # Target Library 설정 
    selected_library = Library_Name.Arrow
    node_container_dict = parse_library(constant.Target_Library_Path(selected_library))
    
    classes_origin = []
    # collect all classes from library
    for file_path, node_container in node_container_dict.items():
        for idx, node in enumerate(node_container.nodes):
            if isinstance(node, ast.ClassDef):
                classes_origin.append((file_path, idx))

    # Metric Types 설정
    metric_types = get_all_metric_types()
    # refactoring 적용을 결정할 때 기준이 되는 type들 아래 둘 중 1택
    metric_types_for_refactoring_check = get_metric_types_in_paper()
    # metric_types_for_refactoring_check = get_coupling_metric_types()
    
    # Main Algorithm Start
    refactoring_count = 0
    try_count = 0
    conflicted_refactoring_count = 0
    static_refactoring_count = 0

    metrics_origin = calculate_metrics(node_container_dict, metric_types)
    result_logs: List[Iteration_Result] = []
    disagreement_statistics: Dict[MetricType, Dict[MetricType, List[int]]] = {}

    for metric_type in metric_types:
        disagreement_statistics[metric_type] = {}
        for metric_type_another in metric_types:
            if(metric_type != metric_type_another):
                disagreement_statistics[metric_type][metric_type_another] = [0, 0, 0]

    log_path = Log_Save_Path(selected_library.value, DESIRED_REFACTORING_COUNT, "fix-ver2-paper")
    os.makedirs(os.path.dirname(log_path), exist_ok=True)
    with open(log_path, "w") as file:
        #Log File에 Metric 순서 적는 코드
        metric_type_order = ""
        for metric_type in metric_types:
            metric_type_order += f"{metric_type}    "
        metric_type_order += "\n"
        file.write(metric_type_order)
        # End
        while(is_finish_cycle(refactoring_count) == False):
            print(f"Start New: {refactoring_count}")
            is_first = True
            #새로운 Cycle 시작
            classes = classes_origin.copy()
            while(len(classes) > 0 and is_finish_cycle(refactoring_count) == False):
                target_class = classes.pop()
                refactoring_methods = REFACTORING_TYPES.copy()
                shuffle(refactoring_methods) # refactoring methods 랜덤 순서 섞기
                while(len(refactoring_methods) > 0 and is_finish_cycle(refactoring_count) == False):
                    refactoring_method = refactoring_methods.pop()
                    refactor = refactoring_method(base=node_container_dict, location=target_class)
                    if refactor.is_possible():
                        refactor.do() # refactoring 진행
                        try_count+=1
                        metrics_before = metrics_origin if is_first else metrics_before
                        metrics_after = calculate_metrics(refactor.result, metric_types)
                        iteration_result = compare_metrics(metrics_before, metrics_after)
                        # refactoring 성공 여부 확인
                        if(fitness_function_improves(iteration_result, metric_types_for_refactoring_check)):
                            print(f"{refactoring_count}th Refactoring_Success: {refactoring_method}")
                            is_first = False
                            result_logs.append(iteration_result)
                            refactoring_count+=1
                            conflicted_refactoring_count += check_conflicted_refactoring(iteration_result, metric_types_for_refactoring_check, metric_types)
                            static_refactoring_count += check_static_refactoring(iteration_result, metric_types_for_refactoring_check, metric_types)
                            #disagreement 통계 과정
                            for metric_type in iteration_result.better_metric:
                                for metric_type_another in iteration_result.better_metric:
                                    if(metric_type != metric_type_another):
                                        disagreement_statistics[metric_type][metric_type_another][Agreement_Idx]+=1
                                for metric_type_another in iteration_result.static_metric:
                                    disagreement_statistics[metric_type][metric_type_another][Dissonant_Idx]+=1
                                for metric_type_another in iteration_result.worse_metric:
                                    disagreement_statistics[metric_type][metric_type_another][Conflicted_Idx]+=1

                            for metric_type in iteration_result.worse_metric:
                                for metric_type_another in iteration_result.worse_metric:
                                    if(metric_type != metric_type_another):
                                        disagreement_statistics[metric_type][metric_type_another][Agreement_Idx]+=1
                                for metric_type_another in iteration_result.static_metric:
                                    disagreement_statistics[metric_type][metric_type_another][Dissonant_Idx]+=1
                                for metric_type_another in iteration_result.better_metric:
                                    disagreement_statistics[metric_type][metric_type_another][Conflicted_Idx]+=1

                            for metric_type in iteration_result.static_metric:
                                for metric_type_another in iteration_result.static_metric:
                                    if(metric_type != metric_type_another):
                                        disagreement_statistics[metric_type][metric_type_another][Agreement_Idx]+=1
                                for metric_type_another in iteration_result.better_metric:
                                    disagreement_statistics[metric_type][metric_type_another][Dissonant_Idx]+=1
                                for metric_type_another in iteration_result.worse_metric:
                                    disagreement_statistics[metric_type][metric_type_another][Dissonant_Idx]+=1
                            metrics_before = metrics_after
                            #log file에 결과 적기
                            metric_values = ""
                            for metric_type in metric_types:
                                if(metric_type in iteration_result.better_metric):
                                    metric_values += f"{iteration_result.better_metric[metric_type].result}, "
                                elif(metric_type in iteration_result.static_metric):
                                    metric_values += f"{iteration_result.static_metric[metric_type].result}, "
                                elif(metric_type in iteration_result.worse_metric):
                                    metric_values += f"{iteration_result.worse_metric[metric_type].result}, "
                            metric_values += "\n"
                            file.write(metric_values)
                        else:
                            refactor.undo()
                        if(try_count%100 == 0):
                            print(f"We tried {try_count} times and succeed {refactoring_count} times")
                            print(f"classes remains {len(classes)} and refactoring_methods remains {len(refactoring_methods)}")
                
    
        # Print Table3 in Paper
        statistics = make_table3_statistics(result_logs, metric_types)
        for metric_type, statistic in statistics.items():
            print(f"{metric_type} {statistic[Better_Idx]}↑ {statistic[Static_Idx]}= {statistic[Worse_Idx]}↓")
            file.write(f"{metric_type.value} {statistic[Better_Idx]}up {statistic[Static_Idx]}= {statistic[Worse_Idx]}down\n")

        file.write("==========================Disagreement Statistics=============================\n")
        for metric_type, statistics in disagreement_statistics.items():
            for metric_type_another, statistic in statistics.items():
                file.write(f"Disagreement Statistics: {metric_type.value} vs {metric_type_another}\n")
                file.write(f"Agreement: {statistic[Agreement_Idx]}, Dissonant:: {statistic[Dissonant_Idx]}, Conflicted: {statistic[Conflicted_Idx]}\n")
        
        file.write(f"conflicted refactoring counts: {conflicted_refactoring_count}/{refactoring_count}\n")
        file.write(f"static refactoring counts: {static_refactoring_count}/{refactoring_count}\n")
    
    # Log 저장과정
    # 저장 위치: log Folder
    # file이름 형식: [selected_library]_[refactoring_count]_[additional_naming].log.txt
    # Ex) asciimatics_3_test.log.txt
    # write_log(statistics, result_logs, metric_types, selected_library, refactoring_count, additional_naming="")