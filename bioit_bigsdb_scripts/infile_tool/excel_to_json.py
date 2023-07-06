import pandas as pd

df = pd.read_excel('/home/angori/BIGSdb_Neisseria_metadata_BioIT_26062023.xlsx',engine='openpyxl')

#shuff_df = df.apply(lambda x: x.sample(frac=1).values)
shuff_df.to_json('/home/angori/BIGSdb_Neisseria_metadata_BioITshuff.json')



