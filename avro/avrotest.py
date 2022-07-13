###
# Write an AVRO file
###

from fastavro import parse_schema, writer, reader
import argparse
from pathlib import Path
import util.make_avroschema_functions as make_schema_functions
import util.parse_avroinput_functions as parse_output_functions
import logging

# schema creation functions
listeria_schema = {
    "name": "sample",
    "type": "record",
    "fields": [
        {"name": "isolate", "type": "string"},
        {"name": "pipeline_version", "type": "float", "default": 1.0},
        make_schema_functions.make_avroschema_typingscheme('listeria', 'mlst', 'mlst'),
        make_schema_functions.make_avroschema_typingscheme('listeria', 'cgmlst', 'cgmlst'),
        make_schema_functions.make_avroschema_typingscheme('listeria', 'pcr_serogroup', 'serogroup')
               ]
                   }


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

    # Parse output
    outputtsvdict = {}
    handle = open(args.tsvfilepath, "r").readlines()
    for line in handle:
        outputtsvdict[line.split("\t")[0]] = line.split("\t")[1].strip("\n")
    print(outputtsvdict["sample"])


    # Writing Avro
    # records needs to be a list for fastavro (even though only one sample at a time)
    listeria_records = [{"isolate": outputtsvdict["sample"],
                # "pipeline_version": float(outputtsvdict["pipeline_version"]),
                "mlst": parse_output_functions.avro_input_typingschema("listeria", "mlst", "mlst", outputtsvdict),
                "cgmlst": parse_output_functions.avro_input_typingschema("listeria", "cgmlst", "cgmlst", outputtsvdict),
                "pcr_serogroup": parse_output_functions.avro_input_typingschema("listeria", "pcr_serogroup", "serogroup", outputtsvdict)
                }
               ]
    schema_parsed = parse_schema(listeria_schema)
    try:
        # if file exists
        with open("listeria_samples.avro", "rb") as input:
            query = [record['isolate'] for record in reader(input)]
            with open("listeria_samples2.avro", "wb") as handle:
                writer(handle, schema_parsed, query)
            # print(query)
            # check whether sample result already in, else do nothing
            if outputtsvdict["sample"] not in query:
                with open("listeria_samples.avro", "a+b") as handle:
                    writer(handle, schema_parsed, listeria_records)
            else:
                logging.warning("isolate already in avro file, skipping..")
    except:
        logging.warning("file does not exists, creating new file")
        # with open("listeria_samples.avro", "wb") as handle:
        #     writer(handle, schema_parsed, listeria_records)

# Reading Avro
from fastavro import reader
with open("listeria_samples.avro", "rb") as handle:
    query = [record["pipeline_version"] for record in reader(handle)]
    print(query)
    # print(query[2]['isolate'])

# converting to json
from fastavro import reader, json_writer

with open("listeria_samples.json", "w") as json_file:
    with open("listeria_samples.avro", "rb") as avro_file:
        avro_reader = reader(avro_file)
        json_writer(json_file, avro_reader.writer_schema, avro_reader)
