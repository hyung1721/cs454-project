from collections import namedtuple

Iteration_Result = namedtuple('Iteration_Result', ['better_metric', 'static_metric', 'worse_metric'])
Statistics_Unit = namedtuple('Statistics_Unit', ['better_count', 'static_count', 'worse_count'])

Target_Library = "./target_libraries/asciimatics"

DESIRED_REFACTORING_COUNT = 200