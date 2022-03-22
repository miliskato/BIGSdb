#issue: max(allele_id) != len(allele_id); some alleles are missing in db, need to take count and can not use len!
#But on the other side; allele sequences under Max should not be updated, so i can only start looking from max(db)

# todo maybe add reverse check aswell to see if sequences are not retired, but why would they retire?


import os
import psycopg2
from pathlib import Path
import shutil
import re

# ###
# #Listeria
# ###
#
# schemedict = {'listeria_mlst': {'seqdefdb': 'bigsdb_listeria_seqdef', 'dirdb': '/db/sequence_typing/listeria/mlst'},
#               'listeria_cgmlst': {'seqdefdb': 'bigsdb_listeria_seqdef', 'dirdb': '/db/sequence_typing/listeria/cgmlst'},
#               'listeria_serogroup': {'seqdefdb': 'bigsdb_listeria_seqdef', 'dirdb': '/db/sequence_typing/listeria/serogroup'},
#               'listeria_metal_detergent_resistance': {'seqdefdb': 'bigsdb_listeria_seqdef', 'dirdb': '/db/sequence_typing/listeria/metal_detergent_resistance'},
#               'listeria_typing_virulence': {'seqdefdb': 'bigsdb_listeria_seqdef', 'dirdb': '/db/sequence_typing/listeria/virulence'},
#               'listeria_antibiotic_resistance': {'seqdefdb': 'bigsdb_listeria_seqdef', 'dirdb': '/db/sequence_typing/listeria/antibiotic_resistance'},
#               'listeria_species_confirmation': {'seqdefdb': 'bigsdb_listeria_seqdef', 'dirdb': '/db/sequence_typing/listeria/species_confirmation'}
#               }

###
#Mycobacterium
###

schemedict = {'mycobacterium_mlst': {'seqdefdb': 'bigsdb_mycobacterium_seqdef', 'dirdb': '/db/sequence_typing/mycobacterium/mlst'},
              'mycobacterium_cgmlst': {'seqdefdb': 'bigsdb_mycobacterium_seqdef', 'dirdb': '/db/sequence_typing/mycobacterium/cgmlst'}
              }

for scheme in schemedict:
    dirs = next(os.walk(schemedict[scheme]['dirdb']))[1]
    for dir in dirs:
        if not dir.startswith('.'):

            #Part 1: Python component
            # Make dict of fasta file
            handle = open(Path(schemedict[scheme]['dirdb']) / dir / ''.join([dir.lower(), '.fasta']), 'r').readlines()
            fastadict = {}
            x = 0
            if len(handle) > 2 and not handle[2].startswith(">"): # one file had this fasta format where the sequence was on different lines
                pathcopytempfile = Path('/tmp') / ''.join([dir.lower(), '.fasta'])
                shutil.copyfile((Path(schemedict[scheme]['dirdb']) / dir / ''.join([dir.lower(), '.fasta'])), pathcopytempfile)
                with open(pathcopytempfile, 'r') as file:
                    handle2 = file.read()
                with open(pathcopytempfile, 'w') as file:
                    file.write(re.sub('(?<=[A-Z])\n(?=[A-Z])', '', handle2))
                handle = open(pathcopytempfile, 'r').readlines()
                os.remove(pathcopytempfile)

            while x < len(handle):
                fastadict[handle[x].rstrip().replace(f">{dir}","").strip("-_")] = handle[x + 1].rstrip()
                x += 2
            #print(list(fastadict.keys())) # I want to compare fasta allele id list with sql allele id list

            #Part 2: PSQL component
            con = psycopg2.connect(database=f"{schemedict[scheme]['seqdefdb']}", user="apache", password="remote", host="127.0.0.1", port="")
            cur = con.cursor()
            cur.execute(f"SELECT allele_id FROM sequences WHERE locus='{dir}'")
            rows = cur.fetchall()
            con.close()
            list_alleleid = []
            for item in rows:
                list_alleleid.append(item[0])
            #print(list_alleleid)

            #Part_3: Compare the two lists
            ids_to_be_inserted = []
            if len(list_alleleid): #not necessary but makes it slightly more elegant for new locus allele sequences
                for id in list(fastadict.keys()):
                    if id not in list_alleleid:
                        ids_to_be_inserted.append(id)
                    else:
                        continue
            else:
                ids_to_be_inserted = list(fastadict.keys())
            print(ids_to_be_inserted)

            #Part_4: insert missing allele sequences into psql db
            con = psycopg2.connect(database=f"{schemedict[scheme]['seqdefdb']}", user="apache", password="remote", host="127.0.0.1", port="")
            cur = con.cursor()
            print(scheme, dir)
            for id in ids_to_be_inserted:
                cur.execute(f"INSERT INTO sequences(locus, allele_id, sequence, status,sender,curator, date_entered, datestamp) \
                              VALUES('{dir}','{id}','{fastadict[id]}','unchecked',1,1,(SELECT CURRENT_DATE),(SELECT CURRENT_DATE))")
                con.commit()
                print(f"id {id} inserted into locus {dir}")
            con.close()

