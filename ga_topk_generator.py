import os
import re
from collections import Counter


def process_txt_file(file_path, top_k=10):
    with open(file_path, encoding='utf-8') as file:
        content = file.read()

    series_pattern = re.compile(r"Series=+([\s\S]+?)=+")
    series_block = series_pattern.search(content)
    if not series_block:
        return None
    series_block = series_block.group(1).strip()

    method_pattern = re.compile(r"src\.core\.refactor\.([A-Za-z]+)")
    methods = method_pattern.findall(series_block)

    method_counts = Counter(methods)
    top_methods = method_counts.most_common(top_k)

    return top_methods


def process_directory(directory_path, output_file="statistics.txt", top_k=10):
    results = []

    for root, _, files in os.walk(directory_path):
        for file in files:
            if file.endswith(".txt"):
                file_path = os.path.join(root, file)
                top_methods = process_txt_file(file_path, top_k)
                if top_methods:
                    results.append((file, top_methods))

    # Save results to statistics.txt
    with open(output_file, 'w', encoding='utf-8') as output:
        for file_name, methods in results:
            output.write(f"{file_name}\n")
            output.write(f"{methods}\n\n")

if __name__ == '__main__':
    directory_path = "log/ga"
    output_file = "ga_topk_stats.txt"
    process_directory(directory_path, output_file=output_file, top_k=4)
