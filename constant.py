from collections import namedtuple
from enum import Enum
import os

class Library_Name(str, Enum):
    Arrow = "arrow"
    ASCIIMatics = "asciimatics"
    Jinja2 = 'jinja2'
    Pygments = 'pygments'
    Sphinx = "sphinx"
    Tweepy = "tweepy"
    Yaml = "yaml"

DESIRED_REFACTORING_COUNT = 1000

Iteration_Result = namedtuple('Iteration_Result', ['better_metric', 'static_metric', 'worse_metric'])
Statistics_Unit = namedtuple('Statistics_Unit', ['better_count', 'static_count', 'worse_count'])

Better_Idx = 0
Static_Idx = 1
Worse_Idx = 2

Agreement_Idx = 0
Dissonant_Idx = 1
Conflicted_Idx = 2

Base_Path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # src의 상위 폴더 refactoring 기준

def Target_Library_Path(library_name):
    return os.path.join("refactoring", "target_libraries", library_name)