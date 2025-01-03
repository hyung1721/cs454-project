import ast

from eval.metrics import Weight, Metric
from eval.class_parser import ClassParser, create_structure
from src.core.parsing import NodeContainer
from MetricType import MetricType
from src.core.parsing import parse_library, get_full_inheritance_dict

class Evaluation:
    def __init__(self, node_containers, metric_type:MetricType):
        self.metric_type = metric_type
        if metric_type != MetricType.DIT:
            self.result = self._evaluate(node_containers)
        else:
            self.result = self._evaluate_dit(node_containers)

    def _metric(self, cls_parser:ClassParser):
        return Metric(self.metric_type).value(cls_parser)
    
    def _weight(self, cls_parser:ClassParser):
        return Weight(self.metric_type).value(cls_parser)

    def _evaluate(self, node_containers):
        total_weight = 0
        total_metric = 0
        for node_container in node_containers.values():
            node_list = node_container.nodes
            for node in node_list:
                if not isinstance(node, ast.ClassDef):
                    continue

                cls_parser:ClassParser = create_structure(node)
                metric = self._metric(cls_parser)
                weight = self._weight(cls_parser)
                total_metric += weight * metric
                total_weight += weight
        return total_metric/total_weight
    
    def _evaluate_dit(self, node_containers):
        inheritance_dict = get_full_inheritance_dict(node_containers)
        cache = {}
        def dfs(class_path):
            if class_path in cache:
                return cache[class_path]
            if not inheritance_dict[class_path]:
                cache[class_path] = 0
                return 0
            max_depth = max(dfs(parent) for parent in inheritance_dict[class_path])
            cache[class_path] = max_depth + 1
            return max_depth + 1
        return max(dfs(cls) for cls in inheritance_dict)
        
    def _is_higher_better(self)->bool:
        if self.metric_type in {MetricType.LSCC, MetricType.TCC, MetricType.CC, MetricType.SCOM, MetricType.RFC}:
            return True
        elif self.metric_type in {MetricType.LCOM5, MetricType.CBO, MetricType.RFC, MetricType.DIT}:
            return False
        assert False

    def __lt__(self, other):
        boolean_holder = self._is_higher_better()
        return self.result < other.result if boolean_holder else self.result > other.result
    
    def __le__(self, other):
        boolean_holder = self._is_higher_better()
        return self.result <= other.result if boolean_holder else self.result >= other.result
    
    def __gt__(self, other):
        boolean_holder = self._is_higher_better()
        return self.result > other.result if boolean_holder else self.result < other.result
    
    def __ge__(self, other):
        boolean_holder = self._is_higher_better()
        return self.result >= other.result if boolean_holder else self.result <= other.result
    
    def __eq__(self, other):
        return self.result == other.result
    
    def __ne__(self, other):
        return self.result != other.result

    def __str__(self):
        return str(self.result)