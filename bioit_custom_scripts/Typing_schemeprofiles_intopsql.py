import os
import psycopg2
import smtplib
from email.message import EmailMessage
import socket
import traceback
import sys
import logging
import yaml
import argparse

from config import BIGSDB_CONFIG
# For this script I am assuming that profiles do not retire.
# It is important to keep in mind that ST do not necessarily follow each other up continuously, there can be gaps


profile_file = 'profiles.tsv'

def _parse_arguments(specieslist: list) -> argparse.Namespace:
    """
    Parses the command line arguments.
    :param specieslist: list of all the species choices
    :return: Parsed arguments
    """
    argument_parser = argparse.ArgumentParser()
    argument_parser.add_argument('--species', required=False, type=str,
                                 choices=specieslist, default=specieslist,
                                 nargs='+')  # this does allow for the same species multiple times but doesnt really matter
    return argument_parser.parse_args()

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


def __insert_profiles(scheme: str, schemedict: dict, indexdict: dict, profile_line_dict: dict, list_to_be_inserted: list, cur_seqdef: object) -> None:
    """
    Inserts profiles for a given scheme in a given species database (cur_seqdef)
    :param scheme:
    :param schemedict: dictionary containing scheme metadata
    :param indexdict: dictionary containing profile locus indexes, and profile fields indexes in the tsv profiles file
    :param profile_line_dict: dictionary of main numeric profile fields (often ST) and their corresponding lines in the tsv
    :param list_to_be_inserted: list of main numeric profile fields (often ST) to be inserted
    :param cur_seqdef: seqdef database cursor object for a certain species
    :return:
    """
    # since we only need one db per scheme, it can stay open during the entire definition
    for profile in list_to_be_inserted:
        # first table (profiles):
        cur_seqdef.execute(f"INSERT INTO profiles(scheme_id, "
                    f"profile_id, sender, curator, "
                    f"date_entered, datestamp) "
                    f"VALUES((SELECT id FROM schemes WHERE name = '{schemedict[scheme]['schemename_bigsdb']}'),"
                    f"'{profile}', 1, 1, "
                    f"(SELECT CURRENT_DATE),(SELECT CURRENT_DATE))")
        # second table (profile fields):
        for field in schemedict[scheme]['scheme_fields']:
            line = profile_line_dict[profile]
            line = line.replace('? ', '').replace('Neisseria ', 'Neisseria_')  # this is added because rflp profiles are malformatted
            fieldvalue = " ".join(line.split()).split(' ')[indexdict[field]]
            cur_seqdef.execute(f"INSERT INTO profile_fields(scheme_id, "
                        f"scheme_field, profile_id, value, "
                        f"curator, datestamp) "
                        f"VALUES((SELECT id FROM schemes WHERE name = '{schemedict[scheme]['schemename_bigsdb']}'),"
                        f"'{field}', '{profile}', '{fieldvalue.replace('_',' ')}', "
                        f"1,(SELECT CURRENT_DATE))")
        # third table (profile members):
        # Loci are saved from dir to be able to know which columns to search for in profiles.tsv
        loci = next(os.walk(schemedict[scheme]['dirdb']))[1]
        for locus in loci:
            if not locus.startswith('.'):  # to exclude hidden folders like .git
                if locus == "'rplF":
                    locus = 'rplF'
                line = profile_line_dict[profile]
                locusvalue = " ".join(line.split()).split(' ')[indexdict[locus]]
                if locusvalue == '0':  # this will create a ForeignKeyViolation error so we prevent this by inserting a null allele if not yet present
                    cur_seqdef.execute(f"SELECT count(*) FROM sequences WHERE "
                                f"locus = '{locus}' AND sequence = 'null allele'")
                    nullpresent = cur_seqdef.fetchall()
                    if nullpresent[0][0] == 0:
                        cur_seqdef.execute(f"INSERT INTO sequences(locus, allele_id, sequence, status, sender,curator, date_entered, datestamp) \
                                      VALUES('{locus}',0, 'null allele', '',0,0,(SELECT CURRENT_DATE),(SELECT CURRENT_DATE))")

                try:
                    cur_seqdef.execute(f"INSERT INTO profile_members(scheme_id, "
                                f"locus, profile_id, allele_id, "
                                f"curator, datestamp) "
                                f"VALUES((SELECT id FROM schemes WHERE name = '{schemedict[scheme]['schemename_bigsdb']}'),"
                                f"'{locus}', '{profile}', '{locusvalue}', "
                                f"1,(SELECT CURRENT_DATE))")
                except Exception as exceptionmessage:
                    _send_email(f"profile with field {field} and value {fieldvalue.replace('_',' ')} already exists as another field, find the profile that was misinserted (not all loci have allele_id), remove it, and all above and restart this script",
                                f"{exceptionmessage}\n{traceback.format_exc()}", emaildict)
                    continue


def _insert_all_profiles() -> None:
    """
    Main function to insert all profiles for the given species
    :return:
    """
    for species in list(set(args.species)):
        con_seqdef = psycopg2.connect(database=f"{config_data['species'][species]['seqdefdb']}", user="apache", password="remote",
                                      host="127.0.0.1", port="")
        con_seqdef.autocommit = True
        cur_seqdef = con_seqdef.cursor()

        schemedict = config_data['species'][species]['typing_schemes']
        for scheme in schemedict.keys():
            if schemedict[scheme].get('scheme_fields'):
                handle = open('/'.join([schemedict[scheme]['dirdb'], profile_file]), 'r').readlines()
                # multiple whitespaces need to be replaced by single whitespace
                header = " ".join(handle[0].split()).split(' ')
                print(header)
                x = 0
                indexdict = {}
                for item in header:
                    print(item)
                    if item == "'rplF":
                        item = 'rplF'
                    indexdict[item] = x
                    x += 1
                print(indexdict.items())
                profile_line_dict = {}
                for line in handle[1:]:
                    profile_line_dict[" ".join(line.split()).split(' ')[0]] = line

                # check whether fields[0] is max or not, if not then all value above max will be inserted in all three tables
                cur_seqdef.execute(f"SELECT MAX(profile_id) FROM profiles WHERE "
                            f"scheme_id = (SELECT id FROM schemes WHERE name = '{schemedict[scheme]['schemename_bigsdb']}') AND "
                            f"LENGTH(profile_id) = (SELECT MAX(LENGTH(profile_id)) FROM profiles WHERE scheme_id = (SELECT id FROM schemes WHERE name = '{schemedict[scheme]['schemename_bigsdb']}'))")
                max_primary_field = cur_seqdef.fetchall()
                list_to_be_inserted = []
                if max_primary_field[0][0] is None:
                    # table is empty, so all need to be inserted
                    for line in handle[1:]:
                        list_to_be_inserted.append(" ".join(line.split()).split(' ')[0])
                    __insert_profiles(scheme, schemedict, indexdict, profile_line_dict, list_to_be_inserted, cur_seqdef)
                elif max_primary_field[0][0] == " ".join(handle[-1].split()).split(' ')[0]:
                    # table is up to date
                    continue
                elif int(max_primary_field[0][0]) < int(" ".join(handle[-1].split()).split(' ')[0]):
                    # table needs to be updated
                    for line in handle[1:]:
                        if int(" ".join(line.split()).split(' ')[0]) > int(max_primary_field[0][0]):
                            list_to_be_inserted.append(" ".join(line.split()).split(' ')[0])
                        else:
                            continue
                    __insert_profiles(scheme, schemedict, indexdict, profile_line_dict, list_to_be_inserted, cur_seqdef)


def _send_email(subject: str, content: str, config: dict) -> None:
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


if __name__ == '__main__':

    # Read the global config
    with open(BIGSDB_CONFIG, encoding='utf-8') as handle:
        config_data = yaml.safe_load(handle)
    emaildict = config_data['mail']

    # Configure stdout logging
    logging.basicConfig(level=logging.DEBUG, stream=sys.stdout)

    # Parse arguments
    args = _parse_arguments(list(config_data['species'].keys()))

    try:
        _insert_all_profiles()
    except Exception as exceptionmessage:
        _send_email(
            f'(automated weekly) profiles db update in BIGSdb failed on host {socket.gethostname()}',
            f"{exceptionmessage}\n{traceback.format_exc()}", emaildict)
