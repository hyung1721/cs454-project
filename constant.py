from collections import namedtuple
import os

Iteration_Result = namedtuple('Iteration_Result', ['better_metric', 'static_metric', 'worse_metric'])
Statistics_Unit = namedtuple('Statistics_Unit', ['better_count', 'static_count', 'worse_count'])

Better_Idx = 0
Static_Idx = 1
Worse_Idx = 2

Base_Path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # src의 상위 폴더 refactoring 기준
Target_Library_Path = os.path.join("refactoring", "target_libraries", "asciimatics")

DESIRED_REFACTORING_COUNT = 10