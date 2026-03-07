import pandas as pd
from libs.path import safe_path
def readCSV(csvPath):
    csv_data = pd.read_csv(safe_path(csvPath), low_memory=False, index_col=0)
    csv_data = csv_data.loc[:, ~csv_data.columns.str.contains('^Unnamed')]
    return csv_data
