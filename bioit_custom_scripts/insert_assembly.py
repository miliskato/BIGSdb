import argparse
import logging
import shutil
import socket
import sys
import traceback
from pathlib import Path
from typing import Dict, List

from Bio import SeqIO

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
    argument_parser.add_argument('--fastafilepath', required=True, type=str)
    argument_parser.add_argument('--species', required=True, type=str, choices=specieslist)
    argument_parser.add_argument('--isolatename', required=True, type=str)
    return argument_parser.parse_args()


def insert_assembly(isolatename: str, species: str, fastafilepath: str) -> None:
    try:
        # Connect to db and create cursors
        (con_isolates, cur_isolates), (con_seqdef, cur_seqdef) = DatabaseConnection().connect_to_dbs_and_create_cursors(species)

        sqlquery = """SELECT COUNT(*) FROM isolates WHERE isolate=%s;"""
        cur_isolates.execute(sqlquery, (isolatename,))
        sample_presence = cur_isolates.fetchall()
        if sample_presence[0][0] == 0:
            send_email(f"please insert isolate/isolate results first",
                       f'{Path(__file__).name}: Error inserting assembly of {species} pipeline to bigsdb for sample {isolatename} on host {socket.gethostname()}.')
            sys.exit()

        sqlquery = """SELECT count(*) FROM sequence_bin WHERE isolate_id = (SELECT MAX(id) FROM isolates WHERE isolate=%s);"""
        cur_isolates.execute(sqlquery, (isolatename,))
        presentcontigs = cur_isolates.fetchall()
        if presentcontigs[0][0] == 0:
            is_multiline = False
            with Path(fastafilepath).open('r') as in_file:
                for line in in_file:
                    if not line.startswith(">") and '\n' in line:
                        is_multiline = True
                        break
            if is_multiline:
                fasta_dict: Dict[str, str] = {}
                sequence: str = ''
                id: str = ''
                with Path(fastafilepath).open() as in_file:
                    for line in in_file:
                        if line.startswith(">"):
                            if sequence:
                                fasta_dict[id] = sequence
                                sequence = ''
                            id = line.strip()
                            fasta_dict[id] = ''
                        else:
                            sequence += line.strip()
                    if sequence:
                        fasta_dict[id] = sequence

                # write output to the temporary file
                temp_file = Path('/tmp') / ''.join([isolatename.lower(), '.fasta'])
                with temp_file.open("w") as out_file:
                    for key, value in fasta_dict.items():
                        out_file.write(key + '\n' + value + '\n')

                # replace the original file with the new file
                shutil.move(temp_file, Path(fastafilepath))
            else:
                fasta_dict: Dict[str, str] = {}
                for record in SeqIO.parse(Path(fastafilepath), "fasta"):
                    # add the record to the dictionary with the ID as the key and the sequence as the value
                    fasta_dict[record.id] = str(record.seq)
                logging.info("The file is not a multiline file")

            # insert into database
            for sequencename, sequence in fasta_dict.items():
                sqlquery = """
                           INSERT INTO sequence_bin(id, 
                           isolate_id, 
                           remote_contig, sequence, original_designation, sender, 
                           curator, date_entered, datestamp) 
                           VALUES((SELECT CASE WHEN (SELECT MAX(id) FROM sequence_bin) IS NULL THEN 1 ELSE (SELECT(SELECT MAX(id) FROM sequence_bin)+1) END), 
                           (SELECT MAX(id) FROM isolates WHERE isolate=%s), 
                           'f', %s, %s, 1, 
                           1, (SELECT CURRENT_DATE),(SELECT CURRENT_DATE))"""
                cur_isolates.execute(sqlquery, (isolatename, sequence, sequencename.strip('>')))
            # # remove the file
            # os.remove(Path(fastafile))

        else:
            send_email(f"isolate {isolatename} already contains assembly records!",
                       f'{Path(__file__).name}: Error inserting assembly of {species} pipeline to bigsdb for sample {isolatename} on host {socket.gethostname()}.')
            sys.exit()

        DatabaseConnection().close_connections(con_isolates, con_seqdef)
    except Exception as exceptionmessage:
        send_email(f"{exceptionmessage}\n{traceback.format_exc()}",
                   f'{Path(__file__).name}: Error inserting assembly of {species} pipeline to bigsdb for sample {isolatename} on host {socket.gethostname()}.')
        sys.exit()


if __name__ == '__main__':
    # Configure stdout logging
    logging.basicConfig(level=logging.DEBUG, stream=sys.stdout)


    bigsdb_config_data = get_bigsdb_config_data()

    # Parse arguments
    args = _parse_arguments(list(bigsdb_config_data['species']))

    # run main
    insert_assembly(args.isolatename, args.species, args.fastafilepath)
