from class_parser import ClassParser, cau, intersection_of_I, union_of_I, create_structure
from itertools import combinations

ALLOWED_METRIC = ["LSCC", "TCC", "CC", "SCOM", "LCOM5"]

class _Metric:
    def __init__(self, metric_type):
        self.metric_type = metric_type
    
    def value(self, cls:ClassParser):
        if self.metric_type == "LSCC":
            return self._LSCC(cls)
        elif self.metric_type == "TCC":
            return self._TCC(cls)
        elif self.metric_type == "CC":
            return self._CC(cls)
        elif self.metric_type == "SCOM":
            return self._SCOM(cls)
        elif self.metric_type == "LCOM5":
            return self._LCOM5(cls)
        else:
            assert False
        
    def _LSCC(self, cls:ClassParser):
        l, k = cls.l(), cls.k()
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
                sigma += len(intersection_of_I(I1, I2)) / len(union_of_I(I1, I2)) / (k * (k-1))
        return 2 * sigma
    
    def _SCOM(self, cls:ClassParser):
        l, k = cls.l(), cls.k()
        if k <= 1:
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
        if k <= 1:
            print("LCOM5 requires at least two methods")
            return 0
        sigma = 0
        for a in A:
            cnt = 0
            for i in range(k):
                if a in cls.I(i):
                    cnt += 1
            sigma += cnt
        return (k - sigma / l) / (k - 1)
            
def weight_of(cls:ClassParser):
    l, k = cls.l(), cls.k()
    return l * k * (k-1)
        
def cohesion_metric(ast_cls_list, metric_type = "LSCC"):
    if metric_type not in ALLOWED_METRIC:
        print(f"[metrics.py] Not allowed metric type : {metric_type}")
        return None
    metric = _Metric(metric_type)
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
    from ast_helper import ast_parser as parser
    module_ast_node = ast.parse(source_code)

    # 테스트를 위해, input 과 동일한 List[ast.ClassDef] 형식으로 변환
    list_of_cls = parser.get_module_classes(module_ast_node)
    print(f'LSCC  : {cohesion_metric(list_of_cls, metric_type="LSCC")}')
    print(f'TCC   : {cohesion_metric(list_of_cls, metric_type="TCC")}')
    print(f'CC    : {cohesion_metric(list_of_cls, metric_type="CC")}')
    print(f'SCOM  : {cohesion_metric(list_of_cls, metric_type="SCOM")}')
    print(f'LCOM5 : {cohesion_metric(list_of_cls, metric_type="LCOM5")}')

    