import pandas as pd
from constant import Library_Name

def compute_spearman_rank_correlation(library_name: Library_Name, file_name):
    file_path = f"log/{library_name.value}/{file_name}"
    with open(file_path, 'r') as file:
        lines = file.readlines()[7:]

    data = {
        "LSCC": [],
        "TCC": [],
        "SCOM": [],
        "CC": [],
        "LCOM5": [],
        "CBO": [],
        "RFC": [],
        "DIT": []
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
            data["CBO"].append(values[5])
            data["RFC"].append(values[6])
            data["DIT"].append(values[7])

    # for datas in data:
    #     print(data[datas])
    df = pd.DataFrame(data)
    correlation_matrix = df.corr(method='spearman')
    print("Spearman Rank Correlation Matrix:")
    print(correlation_matrix)

def compute_spearman_rank_correlation_coupling(library_name):
    file_path = f"log/{library_name.value}/Coupling_Log.txt"
    with open(file_path, 'r') as file:
        lines = file.readlines()

    data = {
        "CBO": [],
        "RFC": [],
        "DIT": []
    }

    for line in lines:
        if line.strip():
            values = line.strip().split(',')
            values = [float(value.strip()[:17]) for value in values if value]
            data["CBO"].append(values[0])
            data["RFC"].append(values[1])
            data["DIT"].append(values[2])

    # for datas in data:
    #     print(data[datas])
    df = pd.DataFrame(data)
    correlation_matrix = df.corr(method='spearman')
    print(f"{library_name.value}'s Spearman Rank Correlation Matrix:")
    print(correlation_matrix)

def compute_coupling_correlation_all_library():
    for library in Library_Name:
        compute_spearman_rank_correlation_coupling(library)



if __name__ == '__main__':
    compute_coupling_correlation_all_library()