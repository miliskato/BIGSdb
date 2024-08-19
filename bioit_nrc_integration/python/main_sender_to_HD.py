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
from bioit_nrc_integration.python.config import CODES_GENOMIC_DWH
from bioit_nrc_integration.python.send_mapping_table_to_ODS import SendMappingTableToODS
from bioit_nrc_integration.python.send_genomic_to_DWH import SendGenomicToDWH

# Configure stdout logging
logging.basicConfig(level=logging.DEBUG, stream=sys.stdout)


class MainSenderToHD:
    """
    Queries the validated documents from Bigsdb that have not been sent to ODS and DWH yet and
    dispatches them to their respective senders to be sent. Creates an aggregated error log so as to avoid mailspam.
    """
    def __init__(self, test_dummy: bool = False, alternate_dtap: str = None) -> None:
        """
        Initialises this class and executes the main function.
        :param test_dummy: Whether the test dummy should be processed or if the main function should run normally
        :param alternate_dtap: alternative dtap (should take test or prod from mongo config) in case we want to test dev or acc
        :return: None
        """
        self._test_dummy = test_dummy
        self._alternate_dtap = alternate_dtap

        # get mongodb config data
        self._mongo_config_data = get_mongodb_config_data()

        with CODES_GENOMIC_DWH.open('r') as handle:
            self._translation_codes_genomic = yaml.safe_load(handle)

        try:
            self.main_main_sender_to_hd()
        except Exception as exceptionmessage:
            send_email(f"{exceptionmessage}\n{traceback.format_exc()}")
            raise

    def main_main_sender_to_hd(self) -> None:
        """
        Main function, queries the validated documents from Bigsdb that have not been sent to ODS and DWH yet and
        dispatches them to their respective senders to be sent. Creates an aggregated error log so as to avoid mailspam.
        :return: None
        """
        fail_log_dict = {}
        for species in self._mongo_config_data['species']:
            # Only process pathogens which have been defined in the genomic code translation config file
            if not self._translation_codes_genomic.get(species):
                continue

            mongoinit_azure = MongoInitialisation(species, mongo_config_data=self._mongo_config_data,
                                                  alternate_dtap=self._alternate_dtap)
            isolates_collection, old_isolateresults_collection, isolates_badqc_collection, \
                isolates_resequencing_collection = mongoinit_azure.initialise_collections()

            mongoinit_local = MongoInitialisation(species, mongo_config_data=self._mongo_config_data,
                                                  alternate_connection_string=self._mongo_config_data['CONNECTION_STRING_LOCAL'],
                                                  alternate_dtap=self._alternate_dtap)
            # Seeing as there is no validation for all samples in place yet, I'm going to assume here that the validation info can be found in the mapping table collection
            # todo
            mapping_table_collection = mongoinit_local.initialise_mapping_table_collection()

            # get documents that need to be sent
            list_of_unsent_validated_documents = mapping_table_collection.find({'validated': True, 'sent_to_ODS_and_DWH': {'$ne': True}})
            if self._test_dummy:
                list_of_unsent_validated_documents = [mapping_dict for mapping_dict in list_of_unsent_validated_documents if mapping_dict['_id'].startswith('test_dummy')]

            fail_log_dict[species] = {'fail_counter': 0,
                                      'fail_logs': '',
                                      'fail_ids': []}
            for document in list_of_unsent_validated_documents:
                try:
                    if not document.get('sent_to_ODS'):
                        SendMappingTableToODS(document, species)
                        mapping_table_collection.update_one({'_id': document['_id']},
                                                            {"$set": {"sent_to_ODS": True}})

                    if not document.get('sent_to_DWH'):
                        # Get the genomic document and transform it into a non-pseudonymized one
                        document_genomic = isolates_collection.find_one({'_id': document['pseudo_id']})
                        document_genomic['_id'] = document['_id']
                        document_genomic['pseudo_id'] = document['pseudo_id']
                        document_genomic['TX_BUSINESS_KEY'] = document['TX_BUSINESS_KEY']

                        SendGenomicToDWH(document_genomic, self._mongo_config_data, species)

                        # technically overkill to add this field here because right after sent_to_ODS_and_DWH is updated,
                        # but it is added for clarity and so that the order of sending can be changed easily too
                        mapping_table_collection.update_one({'_id': document['_id']},
                                                            {"$set": {"sent_to_DWH": True}})

                    mapping_table_collection.update_one({'_id': document['_id']},
                                                        {"$set": {"sent_to_ODS_and_DWH": True}})
                except Exception as exceptionmessage:
                    fail_log_dict[species]['fail_counter'] += 1
                    if fail_log_dict[species]['fail_counter'] > 5:
                        # if 5 or more samples fail for a single pathogen, something is seriously wrong,
                        # break the current pathogen for loop and continue to the next pathogen
                        break
                    fail_log_dict[species]['fail_ids'].append(document['_id'])
                    fail_log_dict[species]['fail_logs'] += f" {exceptionmessage}\n{traceback.format_exc()}"
        if sum(fail_dict['fail_counter'] for species, fail_dict in fail_log_dict.items()) > 0:
            email_body = ''
            for species, fail_dict in fail_log_dict.items():
                email_body += f"{fail_dict['fail_counter']}{' and more' if fail_dict['fail_counter'] == 5 else ''} " \
                              f"failures for {species} with ids " \
                              f"{fail_dict['fail_ids']}{' and more' if fail_dict['fail_counter'] == 5 else ''}, " \
                              f"logs:\n {fail_dict['fail_logs']}\n"
            send_email(email_body)


if __name__ == '__main__':
    MainSenderToHD()
