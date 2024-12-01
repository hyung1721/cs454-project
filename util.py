from typing import List

from constant import Iteration_Result
from MetricType import MetricType
from constant import Better_Idx, Static_Idx, Worse_Idx
import os

TEST_MODE = False

def printf(msg):
    if(TEST_MODE == True):
        print(msg)

def Log_Save_Path(library_name, total_cycles, additional_naming):
    if(len(additional_naming) > 0):
        return os.path.join("log", f"{library_name}_{total_cycles}_{additional_naming}.log.txt")
    else:
        return os.path.join("log", f"{library_name}_{total_cycles}.log.txt")

def write_log(statistics, result_logs: List[Iteration_Result], metric_types: List[MetricType], library_name, total_cycles, additional_naming = ""):
    with open(Log_Save_Path(library_name.value, total_cycles, additional_naming), "w") as file:
        
        for metric_type, statistic in statistics.items():
            file.write(f"{metric_type} {statistic[Better_Idx]}↑ {statistic[Static_Idx]}= {statistic[Worse_Idx]}↓\n")
        file.write("\n")
        
        metric_type_order = ""
        for metric_type in metric_types:
            metric_type_order += f"{metric_type}    "
        metric_type_order += "\n"
        file.write(metric_type_order)
        for result_log in result_logs:
            metric_values = ""
            for metric_type in metric_types:
                if(metric_type in result_log.better_metric):
                    metric_values += f"{result_log.better_metric[metric_type].result}, "
                elif(metric_type in result_log.static_metric):
                    metric_values += f"{result_log.static_metric[metric_type].result}, "
                elif(metric_type in result_log.worse_metric):
                    metric_values += f"{result_log.worse_metric[metric_type].result}, "
            metric_values += "\n"
            file.write(metric_values)