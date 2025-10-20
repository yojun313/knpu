import pandas as pd
import dtale

df = pd.DataFrame({'a': [1, 2, 3], 'b': [4, 5, 6]})
d = dtale.show(df)
d.open_browser() # 새 탭에서 열기