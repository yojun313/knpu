import pandas as pd
import chardet
from libs.path import safe_path

def readCSV(csvPath, **kwargs):
    path = safe_path(csvPath)
    
    with open(path, 'rb') as f:
        raw_data = f.read(10000)
        detected = chardet.detect(raw_data)
        encoding = detected['encoding']
    
    current_encoding = kwargs.pop('encoding', encoding)
    kwargs['low_memory'] = False
    
    try:
        csv_data = pd.read_csv(path, encoding=current_encoding, **kwargs)
    except (UnicodeDecodeError, TypeError):
        csv_data = pd.read_csv(path, encoding='cp949', **kwargs)
    
    csv_data = csv_data.loc[:, ~csv_data.columns.str.contains('^Unnamed')]
    
    return csv_data

def getCSVHeaders(csvPath):
    path = safe_path(csvPath)
    
    with open(path, 'rb') as f:
        raw_data = f.read(10000)
        detected = chardet.detect(raw_data)
        encoding = detected['encoding']

    try:
        df_headers = pd.read_csv(path, encoding=encoding, nrows=0)
    except (UnicodeDecodeError, TypeError):
        df_headers = pd.read_csv(path, encoding='cp949', nrows=0)
    
    column_names = [col for col in df_headers.columns if not col.startswith('Unnamed')]
    
    return column_names
