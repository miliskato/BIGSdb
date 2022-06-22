#issue: max(allele_id) != len(allele_id); some alleles are missing in db, need to take count and can not use len!
#But on the other side; allele sequences under Max should not be updated, so i can only start looking from max(db)

# todo maybe add reverse check aswell to see if sequences are not retired, but why would they retire?


import os
import psycopg2
from pathlib import Path
import shutil
import re
import smtplib
from email.message import EmailMessage
import socket


schemedict = {
              'listeria_mlst': {'seqdefdb': 'bigsdb_listeria_seqdef', 'dirdb': '/db/sequence_typing/listeria/mlst'},
              'listeria_cgmlst': {'seqdefdb': 'bigsdb_listeria_seqdef', 'dirdb': '/db/sequence_typing/listeria/cgmlst'},
              'listeria_serogroup': {'seqdefdb': 'bigsdb_listeria_seqdef', 'dirdb': '/db/sequence_typing/listeria/serogroup'},
              'listeria_metal_detergent_resistance': {'seqdefdb': 'bigsdb_listeria_seqdef', 'dirdb': '/db/sequence_typing/listeria/metal_detergent_resistance'},
              'listeria_typing_virulence': {'seqdefdb': 'bigsdb_listeria_seqdef', 'dirdb': '/db/sequence_typing/listeria/virulence'},
              'listeria_antibiotic_resistance': {'seqdefdb': 'bigsdb_listeria_seqdef', 'dirdb': '/db/sequence_typing/listeria/antibiotic_resistance'},
              'listeria_species_confirmation': {'seqdefdb': 'bigsdb_listeria_seqdef', 'dirdb': '/db/sequence_typing/listeria/species_confirmation'},
              'mycobacterium_mlst': {'seqdefdb': 'bigsdb_mycobacterium_seqdef', 'dirdb': '/db/sequence_typing/mycobacterium/mlst'},
              'mycobacterium_cgmlst': {'seqdefdb': 'bigsdb_mycobacterium_seqdef', 'dirdb': '/db/sequence_typing/mycobacterium/cgmlst'},
              'neisseria_mlst': {'dirdb': '/db/sequence_typing/neisseria/mlst', 'seqdefdb': 'bigsdb_neisseria_seqdef'},
              'neisseria_cgmlst': {'dirdb': '/db/sequence_typing/neisseria/cgmlst', 'seqdefdb': 'bigsdb_neisseria_seqdef'},
              'neisseria_rplf': {'dirdb': '/db/sequence_typing/neisseria/rplf', 'seqdefdb': 'bigsdb_neisseria_seqdef'},
              'neisseria_bast': {'dirdb': '/db/sequence_typing/neisseria/bast', 'seqdefdb': 'bigsdb_neisseria_seqdef'},
              'neisseria_pora': {'dirdb': '/db/sequence_typing/neisseria/pora', 'seqdefdb': 'bigsdb_neisseria_seqdef'},
              'neisseria_porb': {'dirdb': '/db/sequence_typing/neisseria/porb', 'seqdefdb': 'bigsdb_neisseria_seqdef'},
              'neisseria_feta': {'dirdb': '/db/sequence_typing/neisseria/feta', 'seqdefdb': 'bigsdb_neisseria_seqdef'},
              'neisseria_resistancegenes': {'dirdb': '/db/sequence_typing/neisseria/resistance_genes', 'seqdefdb': 'bigsdb_neisseria_seqdef'},
              'neisseria_vaccinetargets': {'dirdb': '/db/sequence_typing/neisseria/vaccine_targets', 'seqdefdb': 'bigsdb_neisseria_seqdef'},
              'neisseria_fhbpnucl': {'dirdb': '/db/sequence_typing/neisseria/fhbp', 'seqdefdb': 'bigsdb_neisseria_seqdef'},
              'neisseria_fhbppept': {'dirdb': '/db/sequence_typing/neisseria/fhbp', 'seqdefdb': 'bigsdb_neisseria_seqdef'},
              'stec_mlst_warwick': {'dirdb': '/db/sequence_typing/ecoli/mlst-warwick', 'seqdefdb': 'bigsdb_stec_seqdef'},
              'stec_mlst_pasteur': {'dirdb': '/db/sequence_typing/ecoli/mlst-pasteur', 'seqdefdb': 'bigsdb_stec_seqdef'},
              'stec_cgmlst': {'dirdb': '/db/sequence_typing/ecoli/cgmlst', 'seqdefdb': 'bigsdb_stec_seqdef'},
              'salmonella_mlst': {'seqdefdb': 'bigsdb_salmonella_seqdef', 'dirdb': '/db/sequence_typing/salmonella/mlst'},
              'salmonella_cgmlst': {'seqdefdb': 'bigsdb_salmonella_seqdef', 'dirdb': '/db/sequence_typing/salmonella/cgmlst'}
              }

emaildict = {"from": "bioit-dev1@wiv-isp.be",
    "to": "michael.kelchtermans@sciensano.be, benoit.bergkpinto@sciensano.be",
    "host": "smtp.wiv-isp.be"}

def insert_alleles():
    for scheme in schemedict:
        dirs = next(os.walk(schemedict[scheme]['dirdb']))[1]
        for dir in dirs:
            if not dir.startswith('.') and not (scheme == 'neisseria_fhbpnucl' and (dir != 'fHbp_allele' and dir != 'fHbp_DNAfrag_Pasteur')) and not (scheme == 'neisseria_fhbppept' and (dir == 'fHbp_allele' or dir == 'fHbp_DNAfrag_Pasteur')):
                #Part 1: Python component
                # Make dict of fasta file
                handle = open(Path(schemedict[scheme]['dirdb']) / dir / ''.join([dir.lower(), '.fasta']), 'r').readlines()
                fastadict = {}
                x = 0
                if (len(handle) > 2 and not handle[2].startswith(">")) or scheme == 'neisseria_feta': # one file had this fasta format where the sequence was on different lines
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
                    else:
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

def send_email(subject: str, content: str, config: dict) -> None:
    """
    Sends an email.
    :param subject: Mail subject
    :param content: Content of the message
    :return: None
    """
    message = EmailMessage()
    message['Subject'] = subject
    message['From'] = config['from']
    message['To'] = config['to']
    message.set_content(content)
    with smtplib.SMTP(config['host']) as s:
        s.send_message(message)

try:
    insert_alleles()
except Exception as exceptionmessage:
    send_email(
        f'(automated weekly) alleles db update in BIGSdb failed on host {socket.gethostname()}',
        f"{exceptionmessage}", emaildict)