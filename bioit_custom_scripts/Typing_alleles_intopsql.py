# issue: max(allele_id) != len(allele_id); some alleles are missing in db, need to take count and can not use len!
# But on the other side; allele sequences under Max should not be updated, so i can only start looking from max(db)

# todo maybe add reverse check aswell to see if sequences are not retired, but why would they retire?


import os
import psycopg2
from pathlib import Path
import shutil
import re
import smtplib
from email.message import EmailMessage
import socket
import traceback
import sys
import logging
import yaml

from config import BIGSDB_CONFIG


schemedict = {
              'listeria_mlst': {'seqdefdb': 'bigsdb_listeria_seqdef', 'dirdb': '/db/sequence_typing/listeria/mlst', 'isolatedb': 'bigsdb_listeria_isolates'},
              'listeria_cgmlst': {'seqdefdb': 'bigsdb_listeria_seqdef', 'dirdb': '/db/sequence_typing/listeria/cgmlst', 'isolatedb': 'bigsdb_listeria_isolates'},
              'listeria_serogroup': {'seqdefdb': 'bigsdb_listeria_seqdef', 'dirdb': '/db/sequence_typing/listeria/serogroup', 'isolatedb': 'bigsdb_listeria_isolates'},
              'listeria_metal_detergent_resistance': {'seqdefdb': 'bigsdb_listeria_seqdef', 'dirdb': '/db/sequence_typing/listeria/metal_detergent_resistance', 'isolatedb': 'bigsdb_listeria_isolates'},
              'listeria_typing_virulence': {'seqdefdb': 'bigsdb_listeria_seqdef', 'dirdb': '/db/sequence_typing/listeria/virulence', 'isolatedb': 'bigsdb_listeria_isolates'},
              'listeria_antibiotic_resistance': {'seqdefdb': 'bigsdb_listeria_seqdef', 'dirdb': '/db/sequence_typing/listeria/antibiotic_resistance', 'isolatedb': 'bigsdb_listeria_isolates'},
              'listeria_species_confirmation': {'seqdefdb': 'bigsdb_listeria_seqdef', 'dirdb': '/db/sequence_typing/listeria/species_confirmation', 'isolatedb': 'bigsdb_listeria_isolates'},
              'mycobacterium_mlst': {'seqdefdb': 'bigsdb_mycobacterium_seqdef', 'dirdb': '/db/sequence_typing/mycobacterium/mlst', 'isolatedb': 'bigsdb_mycobacterium_isolates'},
              'mycobacterium_cgmlst': {'seqdefdb': 'bigsdb_mycobacterium_seqdef', 'dirdb': '/db/sequence_typing/mycobacterium/cgmlst', 'isolatedb': 'bigsdb_mycobacterium_isolates'},
              'neisseria_mlst': {'dirdb': '/db/sequence_typing/neisseria/mlst', 'seqdefdb': 'bigsdb_neisseria_seqdef', 'isolatedb': 'bigsdb_neisseria_isolates'},
              'neisseria_cgmlst': {'dirdb': '/db/sequence_typing/neisseria/cgmlst', 'seqdefdb': 'bigsdb_neisseria_seqdef', 'isolatedb': 'bigsdb_neisseria_isolates'},
              'neisseria_rplf': {'dirdb': '/db/sequence_typing/neisseria/rplf', 'seqdefdb': 'bigsdb_neisseria_seqdef', 'isolatedb': 'bigsdb_neisseria_isolates'},
              'neisseria_bast': {'dirdb': '/db/sequence_typing/neisseria/bast', 'seqdefdb': 'bigsdb_neisseria_seqdef', 'isolatedb': 'bigsdb_neisseria_isolates'},
              'neisseria_pora': {'dirdb': '/db/sequence_typing/neisseria/pora', 'seqdefdb': 'bigsdb_neisseria_seqdef', 'isolatedb': 'bigsdb_neisseria_isolates'},
              'neisseria_porb': {'dirdb': '/db/sequence_typing/neisseria/porb', 'seqdefdb': 'bigsdb_neisseria_seqdef', 'isolatedb': 'bigsdb_neisseria_isolates'},
              'neisseria_feta': {'dirdb': '/db/sequence_typing/neisseria/feta', 'seqdefdb': 'bigsdb_neisseria_seqdef', 'isolatedb': 'bigsdb_neisseria_isolates'},
              'neisseria_resistancegenes': {'dirdb': '/db/sequence_typing/neisseria/resistance_genes', 'seqdefdb': 'bigsdb_neisseria_seqdef', 'isolatedb': 'bigsdb_neisseria_isolates'},
              'neisseria_vaccinetargets': {'dirdb': '/db/sequence_typing/neisseria/vaccine_targets', 'seqdefdb': 'bigsdb_neisseria_seqdef', 'isolatedb': 'bigsdb_neisseria_isolates'},
              'neisseria_fhbpnucl': {'dirdb': '/db/sequence_typing/neisseria/fhbp', 'seqdefdb': 'bigsdb_neisseria_seqdef', 'isolatedb': 'bigsdb_neisseria_isolates'},
              'neisseria_fhbppept': {'dirdb': '/db/sequence_typing/neisseria/fhbp', 'seqdefdb': 'bigsdb_neisseria_seqdef', 'isolatedb': 'bigsdb_neisseria_isolates'},
              'stec_mlst_warwick': {'dirdb': '/db/sequence_typing/ecoli/mlst-warwick', 'seqdefdb': 'bigsdb_stec_seqdef', 'isolatedb': 'bigsdb_stec_isolates'},
              'stec_mlst_pasteur': {'dirdb': '/db/sequence_typing/ecoli/mlst-pasteur', 'seqdefdb': 'bigsdb_stec_seqdef', 'isolatedb': 'bigsdb_stec_isolates'},
              'stec_cgmlst': {'dirdb': '/db/sequence_typing/ecoli/cgmlst', 'seqdefdb': 'bigsdb_stec_seqdef', 'isolatedb': 'bigsdb_stec_isolates'},
              'salmonella_mlst': {'seqdefdb': 'bigsdb_salmonella_seqdef', 'dirdb': '/db/sequence_typing/salmonella/mlst', 'isolatedb': 'bigsdb_salmonella_isolates'},
              'salmonella_cgmlst': {'seqdefdb': 'bigsdb_salmonella_seqdef', 'dirdb': '/db/sequence_typing/salmonella/cgmlst', 'isolatedb': 'bigsdb_salmonella_isolates'}
              }

with open(BIGSDB_CONFIG, encoding='utf-8') as handle:
    config_data = yaml.safe_load(handle)
emaildict = config_data['mail']

logging.basicConfig(level=logging.DEBUG, stream=sys.stdout)


def insert_alleles():
    for scheme in schemedict:
        con = psycopg2.connect(database=f"{schemedict[scheme]['seqdefdb']}", user="apache", password="remote",
                               host="127.0.0.1", port="")
        con.autocommit = True
        cur = con.cursor()
        dirs = next(os.walk(schemedict[scheme]['dirdb']))[1]
        for dir in dirs:
            if not dir.startswith('.') and not (scheme == 'neisseria_fhbpnucl' and (dir != 'fHbp_allele' and dir != 'fHbp_DNAfrag_Pasteur')) and not (scheme == 'neisseria_fhbppept' and (dir == 'fHbp_allele' or dir == 'fHbp_DNAfrag_Pasteur')):
                # Part 1: Python component
                # Make dict of fasta file
                handle = open(Path(schemedict[scheme]['dirdb']) / dir / ''.join([dir.lower(), '.fasta']), 'r').readlines()
                fastadict = {}
                x = 0
                if (len(handle) > 2 and not handle[2].startswith(">")) or scheme == 'neisseria_feta':  # one file had this fasta format where the sequence was on different lines
                    pathcopytempfile = Path('/tmp') / ''.join([dir.lower(), '.fasta'])
                    shutil.copyfile((Path(schemedict[scheme]['dirdb']) / dir / ''.join([dir.lower(), '.fasta'])), pathcopytempfile)
                    with open(pathcopytempfile, 'r') as file:
                        handle2 = file.read()
                    with open(pathcopytempfile, 'w') as file:
                        file.write(re.sub('(?<=[A-Z])\n(?=[A-Z])', '', handle2))
                    handle = open(pathcopytempfile, 'r').readlines()
                    os.remove(pathcopytempfile)

                while x < len(handle):
                    if dir == 'rplF' or dir == 'fHbp':
                        fastadict[handle[x].rstrip().replace(f">'{dir}", "").strip("-_")] = handle[x + 1].rstrip()
                        x += 2
                    elif dir == 'fHbp_allele':
                        fastadict[handle[x].rstrip().replace(f">'fHbp", "").strip("-_")] = handle[x + 1].rstrip()
                        x += 2
                    elif dir == 'FetA':
                        fastadict[handle[x].rstrip().replace(f">{dir}_VR", "").strip("-_")] = handle[x + 1].rstrip()
                        x += 2
                    elif dir == 'porB':
                        fastadict[handle[x].rstrip().replace(f">NEIS2020_", "").strip("-_")] = handle[x + 1].rstrip()
                        x += 2
                    elif dir == 'nhba':
                        fastadict[handle[x].rstrip().replace(f">NEIS2109_", "").strip("-_")] = handle[x + 1].rstrip()
                        x += 2
                    elif dir == 'nadA':
                        fastadict[handle[x].rstrip().replace(f">NEIS1969_", "").strip("-_")] = handle[x + 1].rstrip()
                        x += 2
                    else:
                        fastadict[handle[x].rstrip().replace(f">{dir}", "").strip("-_")] = handle[x + 1].rstrip()
                        x += 2

                # Part 2: PSQL component
                cur.execute(f"SELECT allele_id FROM sequences WHERE locus='{dir}'")
                rows = cur.fetchall()
                list_alleleid = []
                for item in rows:
                    list_alleleid.append(item[0])

                # Part_3: Compare the two lists
                ids_to_be_inserted = []
                if len(list_alleleid):  # not necessary but makes it slightly more elegant for new locus allele sequences
                    for id in list(fastadict.keys()):
                        if id not in list_alleleid:
                            ids_to_be_inserted.append(id)
                        else:
                            continue
                else:
                    ids_to_be_inserted = list(fastadict.keys())
                print(ids_to_be_inserted)

                # Part_4: insert missing allele sequences into psql db
                print(scheme, dir)
                for id in ids_to_be_inserted:
                    try:
                        """
                        Sometimes alleles retire for seemingly no reason, and are added immediately after as a new allele id,
                        The observed ids that went through this were not in any profile or any allele designation in the isolate db
                        """
                        cur.execute(f"INSERT INTO sequences(locus, allele_id, sequence, status,sender,curator, date_entered, datestamp) \
                                      VALUES('{dir}','{id}','{fastadict[id]}','unchecked',1,1,(SELECT CURRENT_DATE),(SELECT CURRENT_DATE))")
                        print(f"id {id} inserted into locus {dir}")
                    except Exception:
                        """
                        Profiles are located in the seqdef db and will automatically update when the sequence db is updated through a rule.
                        Allele designations in the isolate db on the other hand will not, moreover, allele designations in the allele db 
                        do not need to be referring to a real allele in the seqdef db.
                        """
                        cur.execute(f"SELECT allele_id FROM sequences WHERE locus = '{dir}' AND sequence = '{fastadict[id]}'")
                        old_id = cur.fetchall()[0][0]  # If empty then it will be a simple empty list '[]' and taking the index twice will throw an error
                        cur.execute(f"UPDATE sequences SET allele_id = '{id}' WHERE locus = '{dir}' AND \
                                      allele_id = '{old_id}'")
                        con2 = psycopg2.connect(database=f"{schemedict[scheme]['isolatedb']}", user="apache",
                                                password="remote",
                                                host="127.0.0.1", port="")
                        con2.autocommit = True
                        cur2 = con2.cursor()
                        cur2.execute(f"UPDATE allele_designations SET allele_id ='{id}' WHERE allele_id ='{old_id}' AND locus = '{dir}'")
                        cur2.close()
        con.close()


def send_email(subject: str, content: str, config: dict) -> None:
    """
    Sends an email.
    :param subject: Mail subject
    :param content: Content of the message
    :param config: Config containing the maildict
    :return: None
    """
    message = EmailMessage()
    message['Subject'] = subject
    message['From'] = config['from']
    message['To'] = config['to']
    message.set_content(content)
    with smtplib.SMTP(config['host']) as s:
        s.send_message(message)
    logging.info(content)


try:
    insert_alleles()
except Exception as exceptionmessage:
    send_email(
        f'(automated weekly) alleles db update in BIGSdb failed on host {socket.gethostname()}',
        f"{exceptionmessage}\n{traceback.format_exc()}", emaildict)
