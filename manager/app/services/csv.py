import pandas as pd
def readCSV(csvPath):
    csv_data = pd.read_csv(csvPath, low_memory=False, index_col=0)
    csv_data = csv_data.loc[:, ~csv_data.columns.str.contains('^Unnamed')]
    return csv_data
