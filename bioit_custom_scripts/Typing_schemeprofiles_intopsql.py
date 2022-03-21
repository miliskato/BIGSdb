import os
import psycopg2
# For this script I am assuming that profiles do not retire.
# It is important to keep in mind that ST do not neccesarily follow each other up continuosly, there can be gaps

# the first element in the fields list should be an integer/primary_key
schemedict = {#'listeria_mlst': {'seqdefdb': 'bigsdb_listeria_seqdef', 'dirdb': '/db/sequence_typing/listeria/mlst', 'fields': ['ST', 'CC', 'Lineage'], 'schemename_bigsdb': 'MLST'},
              #'listeria_serogroup': {'seqdefdb': 'bigsdb_listeria_seqdef', 'dirdb': '/db/sequence_typing/listeria/serogroup', 'fields': ['profile_id', 'serogroup'], 'schemename_bigsdb': 'PCR serogroup'}#,
              'mycobacterium_mlst': {'seqdefdb': 'bigsdb_mycobacterium_seqdef', 'dirdb': '/db/sequence_typing/mycobacterium/mlst', 'fields': ['ST'], 'schemename_bigsdb': 'MLST'}
             }

profile_file = 'profiles.tsv'

# three tables are important:

# 1. profiles:
#  scheme_id | profile_id | sender | curator | date_entered | datestamp
# -----------+------------+--------+---------+--------------+------------
#          1 | 1          |      1 |       1 | 2022-03-03   | 2022-03-03

# 2. profile_fields:
#  scheme_id | scheme_field | profile_id | value | curator | datestamp
# -----------+--------------+------------+-------+---------+------------
#          1 | testextra    | 1          | GZ5   |       1 | 2022-03-03
#          1 | ST           | 1          | 1     |       1 | 2022-03-03

# 3. profile_members:
#  scheme_id | locus | profile_id | allele_id | curator | datestamp
# -----------+-------+------------+-----------+---------+------------
#          1 | aroC  | 1          | 1         |       1 | 2022-03-03
#          1 | dnaN  | 1          | 1         |       1 | 2022-03-03
#          1 | hemD  | 1          | 1         |       1 | 2022-03-03
#          1 | hisD  | 1          | 5         |       1 | 2022-03-03
#          1 | purE  | 1          | 6         |       1 | 2022-03-03
#          1 | sucA  | 1          | 8         |       1 | 2022-03-03
#          1 | thrA  | 1          | 4         |       1 | 2022-03-03
#

def insert_profiles(scheme, indexdict):
    # since we only need one db per scheme, it can stay open during the entire definition
    con = psycopg2.connect(database=f"{schemedict[scheme]['seqdefdb']}", user='apache', password='remote',
                           host='127.0.0.1', port='')
    con.autocommit = True
    cur = con.cursor()
    #print(list_to_be_inserted)
    for profile in list_to_be_inserted:
        # first table (profiles):
        print(schemedict[scheme]['schemename_bigsdb'])
        cur.execute(f"INSERT INTO profiles(scheme_id, "
                    f"profile_id, sender, curator, "
                    f"date_entered, datestamp) "
                    f"VALUES((SELECT id FROM schemes WHERE name = '{schemedict[scheme]['schemename_bigsdb']}'),"
                    f"'{profile}', 1, 1, "
                    f"(SELECT CURRENT_DATE),(SELECT CURRENT_DATE))")
        # second table (profile fields):
        handle = open('/'.join([schemedict[scheme]['dirdb'], profile_file]), 'r').readlines()
        for field in schemedict[scheme]['fields']:
            for line in handle[1:-1]:
                if " ".join(line.split()).split(' ')[0] == profile:
                    fieldvalue = " ".join(line.split()).split(' ')[indexdict[field]]
            cur.execute(f"INSERT INTO profile_fields(scheme_id, "
                        f"scheme_field, profile_id, value, "
                        f"curator, datestamp) "
                        f"VALUES((SELECT id FROM schemes WHERE name = '{schemedict[scheme]['schemename_bigsdb']}'),"
                        f"'{field}', '{profile}', '{fieldvalue}', "
                        f"1,(SELECT CURRENT_DATE))")
        # third table (profile members):
        # Loci are saved from dir to be able to know which columns to search for in profiles.tsv
        loci = next(os.walk(schemedict[scheme]['dirdb']))[1]
        for locus in loci:
            if not locus.startswith('.'): # to exclude hidden folders like .git
                for line in handle[1:-1]:
                    if " ".join(line.split()).split(' ')[0] == profile:
                        locusvalue = " ".join(line.split()).split(' ')[indexdict[locus]]
                        if locusvalue == '0': # this will create a ForeignKeyViolation error so we prevent this by inserting a null allele if not yet present
                            cur.execute(f"SELECT count(*) FROM sequences WHERE "
                                        f"locus = '{locus}' AND sequence = 'null allele'")
                            nullpresent = cur.fetchall()
                            if nullpresent[0][0] == 0:
                                cur.execute(f"INSERT INTO sequences(locus, allele_id, sequence, status, sender,curator, date_entered, datestamp) \
                                              VALUES('{locus}',0, 'null allele', '',0,0,(SELECT CURRENT_DATE),(SELECT CURRENT_DATE))")
                        # print(profile)
                        # print(" ".join(line.split()).split(' '))
                        # print(indexdict[locus])
                        # print(locusvalue)
                cur.execute(f"INSERT INTO profile_members(scheme_id, "
                            f"locus, profile_id, allele_id, "
                            f"curator, datestamp) "
                            f"VALUES((SELECT id FROM schemes WHERE name = '{schemedict[scheme]['schemename_bigsdb']}'),"
                            f"'{locus}', '{profile}', '{locusvalue}', "
                            f"1,(SELECT CURRENT_DATE))")
    con.close()

for scheme in schemedict:
    handle = open('/'.join([schemedict[scheme]['dirdb'] , profile_file]),'r').readlines()
    # multiple whitespaces need to be replaced by single whitespace
    header = " ".join(handle[0].split()).split(' ')
    print(header)
    x = 0
    indexdict = {}
    for item in header:
        indexdict[item] = x
        x += 1
    print(indexdict.items())

    #check whether fields[0] is max or not, if not then all value above max will be inserted in all three tables
    con = psycopg2.connect(database=f"{schemedict[scheme]['seqdefdb']}", user="apache", password="remote",
                           host="127.0.0.1", port="")
    cur = con.cursor()
    cur.execute(f"SELECT MAX(profile_id) FROM profiles WHERE "
                f"scheme_id = (SELECT id FROM schemes WHERE name = '{schemedict[scheme]['schemename_bigsdb']}')")
    max_primary_field = cur.fetchall()
    list_to_be_inserted =[]
    if max_primary_field[0][0] is None:
        # table is empty, so all need to be inserted
        for line in handle[1:-1]:
            list_to_be_inserted.append(" ".join(line.split()).split(' ')[0])
        insert_profiles(scheme, indexdict)
    elif max_primary_field[0][0] == " ".join(handle[-1].split()).split(' ')[0]:
        # table is up to date
        continue
    elif max_primary_field[0][0] < " ".join(handle[-1].split()).split(' ')[0]:
        # table needs to be updated
        for line in handle[1:-1]:
            if " ".join(line.split()).split(' ')[0] > max_primary_field[0][0]:
                list_to_be_inserted.append(" ".join(line.split()).split(' ')[0])
            else:
                continue
        insert_profiles(scheme, indexdict)

