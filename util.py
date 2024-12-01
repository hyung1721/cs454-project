from typing import List

from constant import Iteration_Result
from MetricType import MetricType

TEST_MODE = False

def printf(msg):
    if(TEST_MODE == True):
        print(msg)

def Log_Save_Path(library_name):
    return library_name+".log.txt"

def write_log(library_name, result_logs: List[Iteration_Result], metric_types: List[MetricType]):
    with open(Log_Save_Path(library_name), "w") as file:
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