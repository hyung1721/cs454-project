import pandas as pd

def compute_spearman_rank_correlation(file_path):
    with open(file_path, 'r') as file:
        lines = file.readlines()[7:]

    data = {
        "LSCC": [],
        "TCC": [],
        "SCOM": [],
        "CC": [],
        "LCOM5": []
    }

    for line in lines:
        if line.strip():
            values = line.strip().split(',')
            values = [float(value.strip()) for value in values if value]
            data["LSCC"].append(values[0])
            data["TCC"].append(values[1])
            data["SCOM"].append(values[2])
            data["CC"].append(values[3])
            data["LCOM5"].append(values[4])

    df = pd.DataFrame(data)
    correlation_matrix = df.corr(method='spearman')
    print("Spearman Rank Correlation Matrix:")
    print(correlation_matrix)

if __name__ == '__main__':
    file_path = "log/yaml_1000.log.txt"
    compute_spearman_rank_correlation(file_path)
