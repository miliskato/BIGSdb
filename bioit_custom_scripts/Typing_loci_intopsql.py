# todo maybe add reverse check aswell to see if sequences are not retired, but why would they retire?

# I will not create schemes, these have to be created by the users manually
# I will create loci in both both the seqdef and the isolate db and also put these loci
# into schemes and link the loci from isolate db to seqdef db

import os
import psycopg2

# capitalisation in schemename_bigsdb is important
schemedict = {'listeria_mlst': {'dirdb': '/db/sequence_typing/listeria/mlst', 'schemename_bigsdb': 'MLST', 'seqdefdb': 'bigsdb_listeria_seqdef', 'isolatedb': 'bigsdb_listeria_isolates'},
              'listeria_cgmlst': {'dirdb': '/db/sequence_typing/listeria/cgmlst', 'schemename_bigsdb': 'cgMLST', 'seqdefdb': 'bigsdb_listeria_seqdef', 'isolatedb': 'bigsdb_listeria_isolates'},
              'listeria_serogroup': {'dirdb': '/db/sequence_typing/listeria/serogroup', 'schemename_bigsdb': 'PCR serogroup', 'seqdefdb': 'bigsdb_listeria_seqdef', 'isolatedb': 'bigsdb_listeria_isolates'},
              'listeria_metal_detergent_resistance': {'dirdb': '/db/sequence_typing/listeria/metal_detergent_resistance', 'schemename_bigsdb': 'Metal and detergent resistance', 'seqdefdb': 'bigsdb_listeria_seqdef', 'isolatedb': 'bigsdb_listeria_isolates'},
              'listeria_typing_virulence': {'dirdb': '/db/sequence_typing/listeria/virulence', 'schemename_bigsdb': 'Virulence', 'seqdefdb': 'bigsdb_listeria_seqdef', 'isolatedb': 'bigsdb_listeria_isolates'},
              'listeria_antibiotic_resistance': {'dirdb': '/db/sequence_typing/listeria/antibiotic_resistance', 'schemename_bigsdb': 'Antibiotic resistance', 'seqdefdb': 'bigsdb_listeria_seqdef', 'isolatedb': 'bigsdb_listeria_isolates'},
              'listeria_species_confirmation': {'dirdb': '/db/sequence_typing/listeria/species_confirmation', 'schemename_bigsdb': 'Species confirmation', 'seqdefdb': 'bigsdb_listeria_seqdef', 'isolatedb': 'bigsdb_listeria_isolates'},
              'mycobacterium_mlst': {'dirdb': '/db/sequence_typing/mycobacterium/mlst', 'schemename_bigsdb': 'MLST', 'seqdefdb': 'bigsdb_mycobacterium_seqdef', 'isolatedb': 'bigsdb_mycobacterium_isolates'},
              'mycobacterium_cgmlst': {'dirdb': '/db/sequence_typing/mycobacterium/cgmlst', 'schemename_bigsdb': 'cgMLST', 'seqdefdb': 'bigsdb_mycobacterium_seqdef', 'isolatedb': 'bigsdb_mycobacterium_isolates'},
              'neisseria_mlst': {'dirdb': '/db/sequence_typing/neisseria/mlst', 'schemename_bigsdb': 'MLST', 'seqdefdb': 'bigsdb_neisseria_seqdef', 'isolatedb': 'bigsdb_neisseria_isolates'},
              'neisseria_cgmlst': {'dirdb': '/db/sequence_typing/neisseria/cgmlst', 'schemename_bigsdb': 'cgMLST', 'seqdefdb': 'bigsdb_neisseria_seqdef', 'isolatedb': 'bigsdb_neisseria_isolates'},
              'neisseria_rplf': {'dirdb': '/db/sequence_typing/neisseria/rplf', 'schemename_bigsdb': 'rplF', 'seqdefdb': 'bigsdb_neisseria_seqdef', 'isolatedb': 'bigsdb_neisseria_isolates'},
              'neisseria_bast': {'dirdb': '/db/sequence_typing/neisseria/bast', 'schemename_bigsdb': 'BAST', 'seqdefdb': 'bigsdb_neisseria_seqdef', 'isolatedb': 'bigsdb_neisseria_isolates'},
              'neisseria_pora': {'dirdb': '/db/sequence_typing/neisseria/pora', 'schemename_bigsdb': 'porA', 'seqdefdb': 'bigsdb_neisseria_seqdef', 'isolatedb': 'bigsdb_neisseria_isolates'},
              'neisseria_porb': {'dirdb': '/db/sequence_typing/neisseria/porb', 'schemename_bigsdb': 'porB', 'seqdefdb': 'bigsdb_neisseria_seqdef', 'isolatedb': 'bigsdb_neisseria_isolates'},
              'neisseria_feta': {'dirdb': '/db/sequence_typing/neisseria/feta', 'schemename_bigsdb': 'FetA', 'seqdefdb': 'bigsdb_neisseria_seqdef', 'isolatedb': 'bigsdb_neisseria_isolates'},
              'neisseria_resistancegenes': {'dirdb': '/db/sequence_typing/neisseria/resistance_genes', 'schemename_bigsdb': 'Antibiotic_resistance', 'seqdefdb': 'bigsdb_neisseria_seqdef', 'isolatedb': 'bigsdb_neisseria_isolates'},
              'neisseria_vaccinetargets': {'dirdb': '/db/sequence_typing/neisseria/vaccine_targets', 'schemename_bigsdb': 'Vaccine_targets', 'seqdefdb': 'bigsdb_neisseria_seqdef', 'isolatedb': 'bigsdb_neisseria_isolates'},
              'neisseria_fhbpnucl': {'dirdb': '/db/sequence_typing/neisseria/fhbp', 'schemename_bigsdb': 'fHbp_nucl', 'seqdefdb': 'bigsdb_neisseria_seqdef', 'isolatedb': 'bigsdb_neisseria_isolates'},
              'neisseria_fhbppept': {'dirdb': '/db/sequence_typing/neisseria/fhbp', 'schemename_bigsdb': 'fHbp_pept', 'seqdefdb': 'bigsdb_neisseria_seqdef', 'isolatedb': 'bigsdb_neisseria_isolates'}
              }


for scheme in schemedict:
    dirs = next(os.walk(schemedict[scheme]['dirdb']))[1]
    for dir in dirs:
        if not dir.startswith('.') and not (schemedict[scheme]['schemename_bigsdb'] == 'fHbp_nucl' and (dir != 'fHbp_allele' and dir != 'fHbp_DNAfrag_Pasteur')) and not (schemedict[scheme]['schemename_bigsdb'] == 'fHbp_pept' and (dir == 'fHbp_allele' or dir == 'fHbp_DNAfrag_Pasteur')):
            con = psycopg2.connect(database=f"{schemedict[scheme]['seqdefdb']}", user="apache", password="remote", host="127.0.0.1", port="")
            print("Database opened successfully")
            cur = con.cursor()
            cur.execute(f"SELECT COUNT(*) FROM loci WHERE id='{dir}'")
            present = cur.fetchall()
            if present[0][0] == 0:
                print(f"locus {dir} not present in loci")
                # add into seqdef loci
                cur.execute(f"INSERT INTO loci(id, data_type, allele_id_format, length_varies, coding_sequence, curator, date_entered, datestamp) \
                                  VALUES('{dir}','DNA','text', 't', 't', 1, (SELECT CURRENT_DATE), (SELECT CURRENT_DATE))")
                con.commit()
                # add into seqdef scheme members
                cur.execute(f"INSERT INTO scheme_members(scheme_id, locus, curator, datestamp) \
                                  VALUES((SELECT id FROM schemes WHERE name='{schemedict[scheme]['schemename_bigsdb']}'), '{dir}', 1, (SELECT CURRENT_DATE))")
                con.commit()
                # If it doesnt exist in seqdef loci, then normally not in isolate loci aswell
                con.close()
                con = psycopg2.connect(database=f"{schemedict[scheme]['isolatedb']}", user="apache", password="remote", host="127.0.0.1", port="")
                print("Database opened successfully")
                cur = con.cursor()
                dbaseurl=''.join(['/cgi-bin/bigsdb/bigsdb.pl?db=',f"{schemedict[scheme]['seqdefdb']}", '&page=alleleInfo&locus=',f"{dir}",'&allele_id=[?]'])
                cur.execute(f"INSERT INTO loci(id, data_type, allele_id_format, length_varies, coding_sequence, dbase_name, dbase_id, "
                            f"url, isolate_display, main_display, query_field, analysis, submission_template, "
                            f"curator, date_entered, datestamp) \
                                  VALUES('{dir}','DNA','text', 't', 't', '{schemedict[scheme]['seqdefdb']}', '{dir}', "
                            f"'{dbaseurl}', 'allele_only', 'f', 't', 't', 'f',"
                            f" 1, (SELECT CURRENT_DATE), (SELECT CURRENT_DATE))")
                con.commit()
                # add into isolate scheme members
                cur.execute(f"INSERT INTO scheme_members(scheme_id, locus, curator, datestamp) \
                                  VALUES((SELECT id FROM schemes WHERE name='{schemedict[scheme]['schemename_bigsdb']}'), '{dir}', 1, (SELECT CURRENT_DATE))")
                con.commit()
                con.close()
            elif present[0][0] == 1:
                cur.execute(f"SELECT count(*) FROM scheme_members WHERE locus='{dir}' and scheme_id=(SELECT id FROM schemes WHERE name='{schemedict[scheme]['schemename_bigsdb']}')")
                present2 = cur.fetchall()
                if present2[0][0] == 0:
                    print(f"locus {dir} not present in scheme members")
                    # add into seqdef scheme members
                    cur.execute(f"INSERT INTO scheme_members(scheme_id, locus, curator, datestamp) \
                                      VALUES((SELECT id FROM schemes WHERE name='{schemedict[scheme]['schemename_bigsdb']}'), '{dir}', 1, (SELECT CURRENT_DATE))")
                    con.commit()
                    con.close()
                    con = psycopg2.connect(database=f"{schemedict[scheme]['isolatedb']}", user="apache", password="remote", host="127.0.0.1",
                                           port="")
                    print("Database opened successfully")
                    cur = con.cursor()
                    cur.execute(f"INSERT INTO scheme_members(scheme_id, locus, curator, datestamp) \
                                      VALUES((SELECT id FROM schemes WHERE name='{schemedict[scheme]['schemename_bigsdb']}'), '{dir}', 1, (SELECT CURRENT_DATE))")
                    con.commit()
                    con.close()
                else:
                    continue
            else:
                continue
            con.close()

