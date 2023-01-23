# todo maybe add reverse check aswell to see if sequences are not retired, but why would they retire?

import argparse
import logging
import os
import socket
import sys
import traceback
from pathlib import Path
from typing import Dict, List

PYTHONPATH = Path(__file__).resolve().parent.parent
sys.path.append(str(PYTHONPATH))

from bioit_custom_scripts.components.databaseconnection import DatabaseConnection
from bioit_custom_scripts.components.python_utility_functions import get_bigsdb_config_data, send_email

def _parse_arguments(specieslist: List[str]) -> argparse.Namespace:
    """
    Parses the command line arguments.
    :param specieslist: list of all the species choices
    :return: Parsed arguments
    """
    argument_parser = argparse.ArgumentParser()
    argument_parser.add_argument('--species', required=False, type=str,
                                 choices=specieslist, default=specieslist,
                                 nargs='+')  # this does allow for the same species multiple times but doesnt really matter, theyre uniquely filtered using set()
    return argument_parser.parse_args()


def _insert_alleles() -> None:
    """
    Main function to insert all alleles for the given species
    :return: None
    """
    for species in set(args.species):
        (con_isolates, cur_isolates), (con_seqdef, cur_seqdef) = DatabaseConnection().connect_to_dbs_and_create_cursors(species)

        schemedict: Dict[Dict[str, str]] = bigsdb_config_data['species'][species]['typing_schemes']
        for scheme in schemedict:
            if schemedict[scheme].get('dirdb') and schemedict[scheme]['dirdb'] != '':
                dirs: List[str] = next(os.walk(schemedict[scheme]['dirdb']))[1]
                for directory in dirs:
                    if not directory.startswith('.') and not (scheme == 'neisseria_fhbpnucl' and (
                            directory != 'fHbp_allele' and directory != 'fHbp_DNAfrag_Pasteur')) and not (
                            scheme == 'neisseria_fhbppept' and (directory == 'fHbp_allele' or directory == 'fHbp_DNAfrag_Pasteur')):
                        # Part 1: Python component
                        # Make dict of fasta file
                        fastafilepath: Path = Path(schemedict[scheme]['dirdb']) / directory / ''.join([directory.lower(), '.fasta'])
                        is_multiline = False
                        with Path(fastafilepath).open('r') as in_file:
                            for line in in_file:
                                if not line.startswith(">") and '\n' in line:
                                    is_multiline = True
                                    break
                        if is_multiline:
                            fasta_dict: Dict[str, str] = {}
                            sequence: str = ''
                            sequence_id: str = ''
                            with Path(fastafilepath).open() as in_file:
                                for line in in_file:
                                    if line.startswith(">"):
                                        if sequence:
                                            fasta_dict[sequence_id] = sequence
                                            sequence = ''
                                        if directory == 'rplF' or directory == 'fHbp':
                                             sequence_id = line.strip().replace(f">'{directory}", "").strip("-_")
                                        elif directory == 'fHbp_allele':
                                            sequence_id = line.strip().replace(f">'fHbp", "").strip("-_")
                                        elif directory == 'FetA':
                                            sequence_id = line.strip().replace(f">{directory}_VR", "").strip("-_")
                                        elif directory == 'porB':
                                            sequence_id = line.strip().replace(f">NEIS2020_", "").strip("-_")
                                        elif directory == 'nhba':
                                            sequence_id = line.strip().replace(f">NEIS2109_", "").strip("-_")
                                        elif directory == 'nadA':
                                            sequence_id = line.strip().replace(f">NEIS1969_", "").strip("-_")
                                        else:
                                            sequence_id = line.strip().replace(f">{directory}", "").strip("-_")
                                        fasta_dict[sequence_id] = ''
                                    else:
                                        sequence += line.strip()
                                if sequence:
                                    fasta_dict[sequence_id] = sequence

                        # Part 2: PSQL component
                        sqlquery = """SELECT allele_id FROM sequences WHERE locus=%s;"""
                        cur_seqdef.execute(sqlquery, (directory,))
                        rows: List[List[str]] = cur_seqdef.fetchall()
                        list_alleleid: set = set(item[0] for item in rows)

                        # Part_3: Compare the two lists
                        ids_to_be_inserted: set = set()
                        if len(list_alleleid):  # not necessary but makes it slightly more elegant for new locus allele sequences
                            for sequence_id in fasta_dict:
                                if sequence_id not in list_alleleid:
                                    ids_to_be_inserted.add(sequence_id)
                                else:
                                    continue
                        else:
                            ids_to_be_inserted = set(list(fasta_dict))

                        # Part_4: insert missing allele sequences into psql db
                        for sequence_id in ids_to_be_inserted:
                            try:
                                """
                                Sometimes alleles retire for seemingly no reason, and are added immediately after as a new allele id,
                                The observed ids that went through this were not in any profile or any allele designation in the isolate db
                                """
                                sqlquery = """
                                           INSERT INTO sequences(locus, allele_id, sequence, status,sender,curator, date_entered, datestamp) \
                                           VALUES(%s, %s, %s, 'unchecked', 1, 1, (SELECT CURRENT_DATE), (SELECT CURRENT_DATE));"""
                                cur_seqdef.execute(sqlquery, (directory, fasta_dict[sequence_id]))
                            except Exception:
                                """
                                Profiles are located in the seqdef db and will automatically update when the sequence db is updated through a rule.
                                Allele designations in the isolate db on the other hand will not, moreover, allele designations in the allele db 
                                do not need to be referring to a real allele in the seqdef db.
                                """
                                sqlquery = """SELECT allele_id FROM sequences WHERE locus=%s AND sequence=%s;"""
                                cur_seqdef.execute(sqlquery, (directory, fasta_dict[sequence_id]))
                                old_id = cur_seqdef.fetchall()[0][0]  # If empty then it will be a simple empty list '[]' and taking the index twice will throw an error
                                sqlquery = """UPDATE sequences SET allele_id = %s WHERE locus=%s AND allele_id=%s;"""
                                cur_seqdef.execute(sqlquery, (sequence_id, directory, old_id))
                                sqlquery = """UPDATE allele_designations SET allele_id = %s WHERE locus=%s AND allele_id=%s;"""
                                cur_isolates.execute(sqlquery, (sequence_id, directory, old_id))
        DatabaseConnection().close_connections(con_isolates, con_seqdef)


if __name__ == '__main__':

    # Read the global config
    bigsdb_config_data = get_bigsdb_config_data()

    # Configure stdout logging
    logging.basicConfig(level=logging.DEBUG, stream=sys.stdout)

    # Parse arguments
    args = _parse_arguments(list(bigsdb_config_data['species']))

    try:
        _insert_alleles()
    except Exception as exceptionmessage:
        send_email(f"{exceptionmessage}\n{traceback.format_exc()}")
        raise Exception(f"{Path(__file__).name} fail on host {socket.gethostname()}")
