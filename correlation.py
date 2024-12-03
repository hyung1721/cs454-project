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

    # lines = list(set(lines))

    for line in lines:
        if line.strip():
            values = line.strip().split(',')
            values = [float(value.strip()[:17]) for value in values if value]
            data["LSCC"].append(values[0])
            data["TCC"].append(values[1])
            data["SCOM"].append(values[2])
            data["CC"].append(values[3])
            data["LCOM5"].append(values[4])

    # for datas in data:
    #     print(data[datas])
    df = pd.DataFrame(data)
    correlation_matrix = df.corr(method='spearman')
    print("Spearman Rank Correlation Matrix:")
    print(correlation_matrix)

if __name__ == '__main__':
    file_path = "log/asciimatics_1400.log.txt"
    compute_spearman_rank_correlation(file_path)
