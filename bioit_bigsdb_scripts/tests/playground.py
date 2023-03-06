import sys
from pathlib import Path

PYTHONPATH = Path(__file__).resolve().parent.parent.parent
sys.path.append(str(PYTHONPATH))

from bioit_bigsdb_scripts.components.psql import TblProfiles


with TblProfiles('listeria') as seqdef_profiles_psql_tbl:
    # the following queries return empty lists: []
    print('###', seqdef_profiles_psql_tbl.execute(f"SELECT profile_id FROM profiles WHERE scheme_id=(SELECT id FROM schemes WHERE name='test');"))
    print('###', seqdef_profiles_psql_tbl.select_profile(('test',)))