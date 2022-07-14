###
# Write an AVRO file
###

# todo: isolate names in Hera will be technical IDs and therefore unique,
#  but when reanalyzing we will need to reuse this technical id without making it a duplicate in the Avro db

from fastavro import parse_schema, writer, reader
import argparse
from pathlib import Path
import logging
import yaml
import os

import util.avroschema as avroschema
import util.avrowriting as avrowriting
from config import AVRO_CONFIG

# avroschema = avroschema.Avroschema()
# avroschema.create_schema("listeria")
#
# writing = avrowriting.Avrowriting()
# writing._avro_input_commontsvoutput({'qc_kraken_status': 'ok', 'qc_kraken_value': '10', 'qc_cgmlst_status' :'nok', 'qc_cgmlst_value': '12'}, 'qc_kraken')

def _parse_arguments() -> argparse.Namespace:
    """
    Parses the command line arguments.
    :return: Parsed arguments
    """
    parser = argparse.ArgumentParser()
    parser.add_argument("--tsvfilepath", required=True, type=Path)
    parser.add_argument("--species", required=True, type=Path)
    return parser.parse_args()


if __name__ == '__main__':
    # Parse arguments
    args = _parse_arguments()

    # Get fixed arguments
    with open(AVRO_CONFIG, encoding='utf-8') as handle:
        config_data = yaml.safe_load(handle)

    # Parse output
    outputtsvdict = {}
    handle = open(args.tsvfilepath, "r").readlines()
    for line in handle:
        outputtsvdict[line.split("\t")[0]] = line.split("\t")[1].strip("\n")
    print(outputtsvdict["sample"])

    avroschema = avroschema.Avroschema()
    avroschema_species = avroschema.create_schema(args.species)
    schema_parsed = parse_schema(avroschema_species)

    avrowriting = avrowriting.Avrowriting()
    records = avrowriting.parse_output(args.species, outputtsvdict)

    # todo need another check that schema_parsed is same as in opened file
    avro_filelocation = Path(config_data['avro_database_directory']) / "_".join([str(args.species), "samples.avro"])
    if os.path.exists(avro_filelocation):
        logging.info(f"file {avro_filelocation} exists")
        with open(avro_filelocation, "rb") as input:
            query = [record['isolate'] for record in reader(input)]
            if outputtsvdict["sample"] not in query:
                with open(avro_filelocation, "a+b") as handle:
                    writer(handle, schema_parsed, records)
            else:
                logging.warning(f"isolate already in avro file {avro_filelocation}, skipping..")
    else:
        logging.warning(f"file {avro_filelocation} does not exists, creating new file")
        with open(avro_filelocation, "wb") as handle:
            writer(handle, schema_parsed, records)
#
# # Reading Avro
# from fastavro import reader
# with open("listeria_samples.avro", "rb") as handle:
#     query = [record["pipeline_version"] for record in reader(handle)]
#     print(query)
#     # print(query[2]['isolate'])
# #
# # # converting to json
# # from fastavro import reader, json_writer
# #
# # with open("listeria_samples.json", "w") as json_file:
# #     with open("listeria_samples.avro", "rb") as avro_file:
# #         avro_reader = reader(avro_file)
# #         json_writer(json_file, avro_reader.writer_schema, avro_reader)
