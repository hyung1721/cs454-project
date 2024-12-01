import ast

from eval.metrics import Weight, Metric
from eval.class_parser import ClassParser, create_structure
from src.core.parsing import NodeContainer
from MetricType import MetricType

class Evaluation:
    def __init__(self, node_containers, metric_type:MetricType):
        self.metric_type = metric_type
        self.result = self._evaluate(node_containers)

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
        
    def _is_higher_better(self)->bool:
        if self.metric_type in {MetricType.LSCC, MetricType.TCC, MetricType.CC, MetricType.SCOM, MetricType.LCOM5, MetricType.RFC, MetricType.FANIN}:
            return True
        elif self.metric_type in {MetricType.CBO, MetricType.FANOUT, MetricType.CA}:
            return False
        assert False

    def __lt__(self, other):
        boolean_holder = self._is_higher_better()
        return boolean_holder if self.result < other.result else not boolean_holder
    
    def __le__(self, other):
        boolean_holder = self._is_higher_better()
        return boolean_holder if self.result <= other.result else not boolean_holder
    
    def __gt__(self, other):
        boolean_holder = self._is_higher_better()
        return boolean_holder if self.result > other.result else not boolean_holder
    
    def __ge__(self, other):
        boolean_holder = self._is_higher_better()
        return boolean_holder if self.result >= other.result else not boolean_holder
    
    def __eq__(self, other):
        return True if self.result == other.result else not False
    
    def __ne__(self, other):
        return True if self.result != other.result else not False

    def __str__(self):
        return str(self.result)