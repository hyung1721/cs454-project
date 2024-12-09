import ast
import copy
import os
from random import choice, sample, randint, random
from typing import Type

import constant
from MetricType import MetricType
from constant import Library_Name
from evaluation import Evaluation
from main import calculate_metrics
from src.core.parsing import parse_library
from src.core.refactor import REFACTORING_TYPES, Refactor, InvalidLocationException

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

INITIAL_METRIC_RESULT = calculate_metrics(
    original_node_container_dict,
    [item[0] for item in TARGET_METRICS]
)

CACHED_FITNESS = {}
CACHE_HIT = 0
CACHE_MISS = 0

SERIES_SIZE = 20
POPULATION_SIZE = 40
K = 10
MUTATION_RATE = 0.2
MAX_GENS = 100
REPEAT_FITNESS = 3


def get_weighted_sum(result: dict[str, Evaluation]):
    total = 0
    for k, v in result.items():
        multiplier = next(iter(item[1] for item in TARGET_METRICS if item[0] == k), None)
        if multiplier is not None:
            total += v.result * multiplier
        else:
            raise Exception(f"{k} is not contained in {TARGET_METRICS}")

    return total


def fitness(series: Series):
    global CACHE_HIT, CACHE_MISS

    if tuple(series) in CACHED_FITNESS:
        CACHE_HIT += 1
        return CACHED_FITNESS[tuple(series)]

    mean_fitness = 0

    for _ in range(REPEAT_FITNESS):
        node_container_dict = copy.deepcopy(original_node_container_dict)

        base = node_container_dict
        for refactoring_method, location in series:
            try:
                refactor = refactoring_method(base=base, location=location)
            except InvalidLocationException as e:
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

        mean_fitness += get_weighted_sum(result)

    mean_fitness /= REPEAT_FITNESS

    print(f"fitness for [{series[0]}...]: {mean_fitness}")
    CACHED_FITNESS[tuple(series)] = mean_fitness
    CACHE_MISS += 1

    return mean_fitness


def get_random_series() -> Series:
    return [
        (choice(REFACTORING_TYPES), choice(classes_origin))
        for _ in range(SERIES_SIZE)
    ]


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


def save_result(series: Series):
    ga_log_dir = "log/ga"
    os.makedirs(ga_log_dir, exist_ok=True)

    with open(os.path.join(ga_log_dir,f"{selected_library.value}_{SERIES_SIZE}_{POPULATION_SIZE}_{MAX_GENS}"), "w") as f:
        # Metric
        f.write(f"Metrics: {', '.join([f'{str(item[1])} * {str(item[0])}' for item in TARGET_METRICS])}\n")

        # Parameters
        f.write(f"Series size: {SERIES_SIZE}\n")
        f.write(f"Population size: {POPULATION_SIZE}\n")
        f.write(f"K: {K}\n")
        f.write(f"Mutation rate: {MUTATION_RATE}\n")
        f.write(f"Max generations: {MAX_GENS}\n")
        f.write(f"Repeat fitness: {REPEAT_FITNESS}\n")

        f.write("Series=================================================================================\n")
        for item in series:
            f.write(f"{item}\n")
        f.write("=======================================================================================\n")

        f.write(f"Before Refactoring: {get_weighted_sum(INITIAL_METRIC_RESULT)}\n")
        f.write(f"After Refactoring: {fitness(series)}\n")



if __name__ == '__main__':
    best_series = get_random_series()
    # save_result(best_series)
    population = [get_random_series() for _ in range(POPULATION_SIZE)]
    gens = 1

    while gens <= MAX_GENS:
        nextgen_pop = []

        while len(nextgen_pop) < POPULATION_SIZE:
            p1 = select(population, K)
            p2 = select(population, K)

            c1, c2 = crossover(p1, p2)

            c1 = mutate(c1, MUTATION_RATE)
            c2 = mutate(c2, MUTATION_RATE)

            nextgen_pop.append(c1)
            if len(nextgen_pop) < POPULATION_SIZE:
                nextgen_pop.append(c2)

        combined = population + nextgen_pop
        population = sorted(combined, key=lambda series: fitness(series), reverse=True)[:POPULATION_SIZE]

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

    save_result(best_series)
