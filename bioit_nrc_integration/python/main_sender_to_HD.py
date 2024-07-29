# Script should be run hourly in order to limit the nr of mails

import logging
import sys
import traceback
import yaml
from pathlib import Path

PYTHONPATH = Path(__file__).resolve().parent.parent.parent
sys.path.append(str(PYTHONPATH))

from bioit_mongodb_scripts.util.mongo_initialisation import MongoInitialisation
from bioit_mongodb_scripts.util.python_utility_functions import get_mongodb_config_data, send_email
from bioit_nrc_integration.python.send_mapping_table_to_ODS import SendMappingTableToODS
from bioit_nrc_integration.python.send_genomic_to_DWH import SendGenomicToDWH

# Configure stdout logging
logging.basicConfig(level=logging.DEBUG, stream=sys.stdout)

mongo_config_data = get_mongodb_config_data()

with (Path(__file__).resolve().parent / 'config' / 'codes_send_genomic_to_DWH.yml').open('r') as handle:
    translation_codes_genomic = yaml.safe_load(handle)

fail_log_dict = {}
for species in mongo_config_data['species']:
    # Only process pathogens which have been defined in the genomic code translation config file
    if translation_codes_genomic.get(species):
        continue

    mongoinit_local = MongoInitialisation(species, mongo_config_data=mongo_config_data,
                                          alternate_connection_string=mongo_config_data['CONNECTION_STRING_LOCAL'])
    # Seeing as there is no validation for all samples in place yet, I'm going to assume here that the validation info can be found in the mapping table collection
    # todo
    mapping_table_collection = mongoinit_local.initialise_mapping_table_collection()
    mongoinit_azure = MongoInitialisation(species, mongo_config_data=mongo_config_data)
    isolates_collection, old_isolateresults_collection, isolates_badqc_collection, \
        isolates_resequencing_collection = mongoinit_azure.initialise_collections()

    # get documents that need to be sent
    list_of_unsent_validated_documents = mapping_table_collection.find({'validated': True, 'sent_to_ODS_and_DWH': {'$ne': True}})

    fail_log_dict[species] = {'fail_counter': 0,
                              'fail_logs': '',
                              'fail_ids': []}
    for document in list_of_unsent_validated_documents:
        try:
            if not document.get('sent_to_ODS'):
                SendMappingTableToODS(document)
                # todo uncomment mapping_table_collection.update_one({'_id': document['_id']},
                                                    # todo uncomment {"$set": {"sent_to_ODS": True}})

            if not document.get('sent_to_DWH'):
                # Get the genomic document and transform it into a non-pseudonymized one
                document_genomic = isolates_collection.find_one({'_id': document['pseudo_id']})
                document_genomic['_id'] = document['_id']
                document_genomic['pseudo_id'] = document['pseudo_id']

                SendGenomicToDWH(document, mongo_config_data, species)

                # technically overkill to add this field here because right after sent_to_ODS_and_DWH is updated,
                # but it is added for clarity and so that the order of sending can be changed easily too
                # todo uncomment mapping_table_collection.update_one({'_id': document['_id']},
                                                    # todo uncomment {"$set": {"sent_to_DWH": True}})

            # todo uncomment mapping_table_collection.update_one({'_id': document['_id']},
                                                # todo uncomment {"$set": {"sent_to_ODS_and_DWH": True}})
        except Exception as exceptionmessage:
            fail_log_dict[species]['fail_counter'] += 1
            fail_log_dict[species]['fail_ids'].append(document['_id'])
            fail_log_dict[species]['fail_logs'] += f" {exceptionmessage}\n{traceback.format_exc()}"
            if fail_log_dict[species]['fail_counter'] == 5:
                # if 5 or more samples fail for a single pathogen, something is seriously wrong,
                # break the current pathogen for loop and continue to the next pathogen
                break
if sum(fail_dict['fail_counter'] for species, fail_dict in fail_log_dict.items()) > 0:
    email_body = ''
    for species, fail_dict in fail_log_dict.items():
        email_body += f"{fail_dict['fail_counter']}{' or more' if fail_dict['fail_counter'] == 5 else ''} " \
                      f"failures for {species} with ids " \
                      f"{fail_dict['fail_ids']}{' and more' if fail_dict['fail_counter'] == 5 else ''}, " \
                      f"logs:\n {fail_dict['fail_logs']}\n"
    send_email(email_body)
