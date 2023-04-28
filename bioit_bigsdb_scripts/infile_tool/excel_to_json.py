import pandas as pd

#PYTHONPATH

df_data = pd.read_excel('/home/angori/PycharmProject/DeployTest/BIGSdb_Neisseria_metadata_BioIT.xlsx',engine='openpyxl')

col3name = df.columns.values[2]
col6name = df.columns.values[5]
col10name = df.columns.values[9]

df[col3name] = df[col3name].apply(lambda x: pd.to_datetime (x, format='%Y-%m-%d', errors='coerce'))
df[col6name] = df[col6name].apply(lambda x: pd.to_datetime (x, format='%Y-%m-%d %H:%M:%S', errors='coerce'))
df[col10name] = df[col10name].apply(lambda x: pd.to_datetime (x, format='%d/%m/%Y',errors='coerce'))

shuff_df = df.apply(lambda x: x.sample(frac=1).values)

json_str=df.to_json(date_format='iso')

