import pandas as pd

df = pd.read_excel('/home/angori/PycharmProject/DeployTest/BIGSdb_Neisseria_metadata_BioIT.xlsx',engine='openpyxl')

df=df.loc[df['uploader'] != 'jolein.laumen@sciensano.be']
df=df.loc[df['id'] != 226]
df=df.loc[df['id'] != 154]
shuff_df = df.apply(lambda x: x.sample(frac=1).values)
shuff_df.to_json('/home/angori/PycharmProject/DeployTest/BIGSdb_Neisseria_metadata_BioITshuff.json')

for col in df:
    print(df[col].unique())

