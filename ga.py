import ast
import copy
from random import choice, sample, randint, random
from typing import Type

import constant
from MetricType import MetricType
from constant import Library_Name
from main import calculate_metrics
from src.core.parsing import parse_library
from src.core.refactor import REFACTORING_TYPES, Refactor, LocationInconsistencyError

selected_library = Library_Name.Jinja2

original_node_container_dict = parse_library(constant.Target_Library_Path(selected_library))

Location = tuple[str, int]
Series = list[tuple[Type[Refactor], Location]]

classes_origin: list[Location] = []
# collect all classes from library
for file_path, node_container in original_node_container_dict.items():
    for idx, node in enumerate(node_container.nodes):
        if isinstance(node, ast.ClassDef):
            classes_origin.append((file_path, idx))

TARGET_METRICS = [
    (MetricType.LSCC, 1),
    # (MetricType.SCOM, 1),
    # (MetricType.LCOM5, -1),
    (MetricType.CBO, 1)
]

INITIAL_METRIC = {
    k: v.result
    for k, v in calculate_metrics(
        original_node_container_dict,
        [item[0] for item in TARGET_METRICS]
    ).items()
}

SERIES_SIZE = 15
CACHED_FITNESS = {}
CACHE_HIT = 0
CACHE_MISS = 0


def get_random_series() -> Series:
    return [
        (choice(REFACTORING_TYPES), choice(classes_origin))
        for _ in range(SERIES_SIZE)
    ]



def fitness(series: Series):
    global CACHE_HIT, CACHE_MISS

    if tuple(series) in CACHED_FITNESS:
        CACHE_HIT += 1
        return CACHED_FITNESS[tuple(series)]

    node_container_dict = copy.deepcopy(original_node_container_dict)

    base = node_container_dict
    for refactoring_method, location in series:
        try:
            refactor = refactoring_method(base=base, location=location)
        except LocationInconsistencyError as e:
            print("---Can be ignored---")
            print(e)
            print(f"{location} is no longer valid since prior refactorings modify the structure.")
            print("---")
            continue
        refactor.do()
        base = refactor.result

    result = calculate_metrics(
        base,
        [item[0] for item in TARGET_METRICS]
    )

    total = 0
    for k, v in result.items():
        multiplier = next(iter(item[1] for item in TARGET_METRICS if item[0] == k), None)
        if multiplier is not None:
            total += v.result * multiplier
        else:
            raise Exception(f"{k} is not contained in {TARGET_METRICS}")

    print(f"fitness for {series[:1]}...: {total}")
    CACHED_FITNESS[tuple(series)] = total
    CACHE_MISS += 1

    return total


def select(population: list[Series], k):
    chosen = sample(population, k)
    return sorted(chosen, key=lambda series: fitness(series), reverse=True)[0]


def crossover(p1: Series, p2: Series):
    cross_idx = randint(0, SERIES_SIZE - 1)
    c1 = p1[:cross_idx] + p2[cross_idx:]
    c2 = p2[:cross_idx] + p1[cross_idx:]
    return c1, c2


def mutate(c: Series, mutate_rate):
    mutated_c = copy.deepcopy(c)

    for idx in range(len(mutated_c)):
        if random() < mutate_rate:
            mutated_c[idx] = (choice(REFACTORING_TYPES), choice(classes_origin))

    return mutated_c


if __name__ == '__main__':
    pop_size = 20
    k = 5
    mutate_rate = 0.2

    best_series = get_random_series()

    population = [get_random_series() for _ in range(pop_size)]

    gens = 1
    max_gens = 10

    while gens <= max_gens:
        nextgen_pop = []

        while len(nextgen_pop) < pop_size:
            p1 = select(population, k)
            p2 = select(population, k)

            c1, c2 = crossover(p1, p2)

            c1 = mutate(c1, mutate_rate)
            c2 = mutate(c2, mutate_rate)

            nextgen_pop.append(c1)
            if len(nextgen_pop) < pop_size:
                nextgen_pop.append(c2)

        combined = population + nextgen_pop
        population = sorted(combined, key=lambda series: fitness(series), reverse=True)[:pop_size]

        if fitness(population[0]) > fitness(best_series):
            best_series = population[0]
            print("Generation " + str(gens) + ", best series: ", best_series)
            print("fitness: ", fitness(best_series))
        else:
            print("Generation " + str(gens))

        print(f"fitness cache hit: {CACHE_HIT}, miss: {CACHE_MISS} for Generation {gens}.")
        CACHE_HIT = 0
        CACHE_MISS = 0

        gens += 1

    print(best_series, fitness(best_series))
