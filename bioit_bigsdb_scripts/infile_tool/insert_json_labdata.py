import argparse
import logging
import sys
from pathlib import Path
from typing import List

import numpy as np
import pandas as pd
import re

from pandas.errors import ParserError

PYTHONPATH = Path(__file__).resolve().parent.parent
sys.path.append(str(PYTHONPATH))

from bioit_bigsdb_scripts.components.psql import TblIsolates
from bioit_bigsdb_scripts.components.python_utility_functions import get_bigsdb_config_data


def parse_arguments(specieslist: List[str]) -> argparse.Namespace:
    """
    Parses the command line arguments.
    :param specieslist: list of all the species choices
    :return: Parsed arguments
    """
    argument_parser = argparse.ArgumentParser()
    argument_parser.add_argument('--jsonfilepath', required=True, type=Path)
    argument_parser.add_argument('--species', required=True, type=str, choices=specieslist)
    return argument_parser.parse_args()

def safe_date_parse(value):
    try:
        return pd.to_datetime(value, format='%Y-%m-%d')
    except (ParserError, ValueError):
        try:
            return pd.to_datetime(value, format='%Y-%m-%d %H:%M:%S')
        except (ParserError, ValueError):
            try:
                return pd.to_datetime(value, format='%d/%m/%Y')
            except (ParserError, ValueError):
                try:
                    return pd.to_datetime(value, unit='ms')
                except (ParserError, ValueError):
                    return value


def insert_json_labdata(species: str, jsonfilepath: Path) -> None:
    """
    Inserts an assembly for a given sample in bigsdb
    :param species: commonly used bioit species name: either genus or specific like stec
    :param fastafilepath: path of the fasta file
    :return: None
    """

    df = pd.read_json(jsonfilepath)
    fields_to_parse = ['Isolation Date ','Patient BirthDate']

    for item in fields_to_parse:
        df[item] = df[item].apply(lambda x: safe_date_parse(x))

    config = get_bigsdb_config_data()
    db_metadata_mappings = config['lab_meta_data']

    metadata_map_species = db_metadata_mappings[species]

    # prepare query
    species_update_query = TblIsolates.build_update_nomin_metadata_query(metadata_map_species)

    tbl_isolates = TblIsolates(species)
    # update rows
    df = df.reset_index()
    fail = 0

    for index, row in df.iterrows():
        try:
            params = []
            for key in metadata_map_species:
                if pd.isnull(row[metadata_map_species[key]]) or row[metadata_map_species[key]] == ' ':
                    params.append(None)
                else:
                    params.append(row[metadata_map_species[key]])
            params.append(row['Sample ID'])
            tbl_isolates.update_nomin_metadata(species_update_query, params)
        except Exception as e:
            fail += 1
            print(str.format("Error on id {} (Skipping it): {}", row['id'], e))

    print(str.format("Updated {} items, {} failures", (df.shape[0]-fail), fail))

if __name__ == '__main__':
    # Configure stdout logging
    logging.basicConfig(level=logging.DEBUG, stream=sys.stdout)

    # Get Bigsdb config
    bigsdb_config_data = get_bigsdb_config_data()

    # Parse arguments
    args = parse_arguments(list(bigsdb_config_data['lab_meta_data']))

    # run main
    insert_json_labdata(args.species, args.jsonfilepath)
