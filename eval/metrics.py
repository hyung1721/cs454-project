from eval.class_parser import ClassParser, cau, intersection_of_I, union_of_I, create_structure
from itertools import combinations
from MetricType import MetricType

class Metric:
    def __init__(self, metric_type: MetricType):
        self.metric_type = metric_type

    def value(self, cls: ClassParser):
        if self.metric_type == MetricType.LSCC:
            return self._LSCC(cls)
        elif self.metric_type == MetricType.TCC:
            return self._TCC(cls)
        elif self.metric_type == MetricType.CC:
            return self._CC(cls)
        elif self.metric_type == MetricType.SCOM:
            return self._SCOM(cls)
        elif self.metric_type == MetricType.LCOM5:
            return self._LCOM5(cls)
        elif self.metric_type == MetricType.CBO:
            return self._CBO(cls)
        elif self.metric_type == MetricType.RFC:
            return self._RFC(cls)
        elif self.metric_type == MetricType.FANIN:
            return self._FanIn(cls)
        elif self.metric_type == MetricType.FANOUT:
            return self._FanOut(cls)
        elif self.metric_type == MetricType.CA:
            return self._Ca(cls)
        else:
            raise ValueError(f"Unsupported metric type: {self.metric_type}")

    def _LSCC(self, cls:ClassParser):
        l, k = cls.l(), cls.k()
        if l == 0 and k == 0:
            print("LSCC found empty class")
            return 1
        if l == 0 and k > 1:
            return 0
        elif (l > 0 and k == 0) or k == 1:
            return 1
        else:
            result = 0
            for i in range(k):
                x_i = cls.x(i)
                result += x_i
            return result/(l*k*(k-1))
        
    def _TCC(self, cls:ClassParser):
        k, M = cls.k(), cls.M()
        if k <= 1:
            print("TCC requires at least two methods")
            return 0
        numerator = 0
        for m1_key, m2_key in combinations(M.keys(), 2):
            m1, m2 = M[m1_key], M[m2_key]
            numerator += 1 if cau(m1, m2) else 0
        return numerator/ (k * (k-1) / 2)
    
    def _CC(self, cls:ClassParser):
        k = cls.k()
        if k <= 1:
            print("CC requires at least two methods")
            return 0
        sigma = 0
        for i in range(k-1):
            for j in range(i+1, k):
                I1, I2 = cls.I(i), cls.I(j)
                intersection_of_i = intersection_of_I(I1, I2)
                if intersection_of_i == 0:
                    return 0
                sigma += len(intersection_of_I(I1, I2)) / len(union_of_I(I1, I2)) / (k * (k-1))
        return 2 * sigma
    
    def _SCOM(self, cls:ClassParser):
        l, k = cls.l(), cls.k()
        if l == 0 or k <= 1:
            print("SCOM requires at least two methods")
            return 0
        sigma = 0
        for i in range(k-1):
            for j in range(i+1, k):
                I1, I2 = cls.I(i), cls.I(j)
                if len(I1) == 0 or len(I2) == 0:
                    print("SCOM requires at least one attributes for each methods")
                    return 0
                sigma += len(intersection_of_I(I1, I2)) * len(union_of_I(I1, I2)) / min(len(I1), len(I2)) / l / (k * (k - 1))
        return 2 * sigma

    def _LCOM5(self, cls:ClassParser):
        A = cls.A()
        l, k = cls.l(), cls.k()
        if l == 0 or k <= 1:
            print("LCOM5 requires at least two methods and at least one attribute")
            return 0
        sigma = 0
        for a in A:
            cnt = 0
            for i in range(k):
                if a in cls.I(i):
                    cnt += 1
            sigma += cnt
        return (k - sigma / l) / (k - 1)
    
    def _CBO(self, cls: ClassParser):
        count = 0
        methods = cls.M()
        for _, method in methods.items():
            for var in method['variables']:
                if '.' in var and not var.startswith(cls.cls_structure['name']):
                    count += 1
        return count

    def _RFC(self, cls: ClassParser):
        methods = cls.M()
        rfc_count = 0
        for method_name, method in methods.items():
            if not method_name.startswith('_') or method_name.startswith('__') and method_name.endswith('__'):
                # Count public methods and special methods (e.g., __init__)
                rfc_count += 1
                for var in method['variables']:
                    if '.' in var:  # Assume this means a method call to another class
                        rfc_count += 1
        return rfc_count

    def _FanIn(self, cls: ClassParser):
        fan_in_count = 0
        # TODO: CBO에 특정 모듈을 넣도록 하면 됨. input도 바뀌어야 함 - 20241120 SDG 
        return fan_in_count

    def _FanOut(self, cls: ClassParser):
        fan_out_count = 0
        # TODO: RFC에 특정 모듈을 넣도록 하면 됨. input도 바뀌어야 함 - 20241120 SDG
        return fan_out_count

    def _Ca(self, cls_list):
        ca_count = 0
        current_class_name = cls_list.cls_structure['name']
        for other_cls in cls_list:
            if other_cls == cls_list:
                continue
            for method in other_cls.M().values():
                for var in method['variables']:
                    if current_class_name in var:
                        ca_count += 1
                        break
        return ca_count
        
class Weight:
    def __init__(self, metric_type: MetricType):
        self.metric_type = metric_type

    def value(self, cls: ClassParser):
        if self.metric_type == MetricType.LSCC:
            return self._LSCC(cls)
        elif self.metric_type == MetricType.TCC:
            return self._TCC(cls)
        elif self.metric_type == MetricType.CC:
            return self._CC(cls)
        elif self.metric_type == MetricType.SCOM:
            return self._SCOM(cls)
        elif self.metric_type == MetricType.LCOM5:
            return self._LCOM5(cls)
        elif self.metric_type == MetricType.CBO:
            return self._CBO(cls)
        elif self.metric_type == MetricType.RFC:
            return self._RFC(cls)
        elif self.metric_type == MetricType.FANIN:
            return self._FanIn(cls)
        elif self.metric_type == MetricType.FANOUT:
            return self._FanOut(cls)
        elif self.metric_type == MetricType.CA:
            return self._Ca(cls)
        else:
            raise ValueError(f"Unsupported metric type: {self.metric_type}")
        
    def _LSCC(self, cls:ClassParser):
        l, k = cls.l(), cls.k()
        return (l*k*(k-1)) if k!=1 else 1
        
    def _TCC(self, cls:ClassParser):
        k = cls.k()
        return k * (k-1)
    
    def _CC(self, cls:ClassParser):
        k = cls.k()
        return k * (k-1)
        
    def _SCOM(self, cls:ClassParser):
        l, k = cls.l(), cls.k()
        return (l*k*(k-1))

    def _LCOM5(self, cls:ClassParser):
        l, k = cls.l(), cls.k()
        return l * k
    
    def _CBO(self, cls: ClassParser):
        return NotImplemented

    def _RFC(self, cls: ClassParser):
        return NotImplemented

    def _FanIn(self, cls: ClassParser):
        return NotImplemented

    def _FanOut(self, cls: ClassParser):
        return NotImplemented

    def _Ca(self, cls_list):
        return NotImplemented

def evaluate_improvement(metric_type, before_metrics, after_metrics) -> str:
    lower_is_better = {MetricType.CBO, MetricType.FANOUT, MetricType.CA}
    higher_is_better = {MetricType.LSCC, MetricType.TCC, MetricType.CC, MetricType.SCOM, MetricType.LCOM5, MetricType.RFC, MetricType.FANIN}

    if metric_type in lower_is_better:
        return True if after_metrics < before_metrics else False
    elif metric_type in higher_is_better:
        return True if after_metrics > before_metrics else False
    else:
        raise ValueError(f"Unsupported metric type: {self.metric_type}")
            
def cohesion_metric(ast_cls_list, metric_type):
    # if metric_type not in ALLOWED_METRIC: # ALLWED_METRIC?? - 20241120 신동환
    #     print(f"[metrics.py] Not allowed metric type : {metric_type}")
    #     return None
    metric = Metric(metric_type)
    # total_weight = 0
    result = []
    for ast_cls in ast_cls_list:
        cls:ClassParser = create_structure(ast_cls)
        # weight = weight_of(cls)
        # total_weight += weight
        result.append(metric.value(cls))
    return result

if __name__ == "__main__":
    # Example Usage
    source_code = """
class ExampleClass1(object):
    class_variable1 = 5
    class_variable2 = 6

    def func1(self):
        self.instance_variable = 6

        def inner_func(b):
            return b + 5

        local_variable = self.class_variable1

        return local_variable

    def func2(self):
        print(self.class_variable2 + self.class_variable1)

    @staticmethod
    def func3(variable):
        return variable + 7

class ExampleClass2(object):
    def func1(self):
        self.instance_variable1 = 7
"""
    import ast
    import eval.ast_helper.ast_parser as parser
    module_ast_node = ast.parse(source_code)

    # 테스트를 위해, input 과 동일한 List[ast.ClassDef] 형식으로 변환
    list_of_cls = parser.get_module_classes(module_ast_node)
    for metric_type in MetricType:
        print(f'{metric_type} : {cohesion_metric(list_of_cls, metric_type)}')