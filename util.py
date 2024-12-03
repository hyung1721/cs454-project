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
    # Create the log directory if it doesn't exist
    log_dir = "log"
    os.makedirs(log_dir, exist_ok=True)
    
    if(len(additional_naming) > 0):
        return os.path.join(log_dir, f"{library_name}_{total_cycles}_{additional_naming}.log.txt")
    else:
        return os.path.join(log_dir, f"{library_name}_{total_cycles}.log.txt")

def write_log(statistics, result_logs: List[Iteration_Result], metric_types: List[MetricType], library_name, total_cycles, additional_naming = ""):
    # Get the log path
    log_path = Log_Save_Path(library_name.value, total_cycles, additional_naming)
    # Ensure the directory exists (in case it was deleted between path creation and file opening)
    os.makedirs(os.path.dirname(log_path), exist_ok=True)
    with open(log_path, "w") as file:
        for metric_type, statistic in statistics.items():
            file.write(f"{metric_type.value} {statistic[Better_Idx]}up {statistic[Static_Idx]}= {statistic[Worse_Idx]}down\n")
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