# Script should be run hourly in order to limit the nr of mails

import logging
import sys
import traceback
import yaml
from pathlib import Path
from typing import Any, Dict

from pymongo.collection import Collection

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
    dispatches them to their respective senders to be sent. Creates an aggregated error log to avoid mailspam.
    """
    def __init__(self, test_dummy: bool = False, alternate_dtap: str = None) -> None:
        """
        Initialises this class and executes the main function.
        :param test_dummy: Whether the test dummy should be processed or if the main function should run normally
        :param alternate_dtap: alternative dtap (should take test or prod from mongo config) in case we
        want to test dev or acc
        :return: None
        """
        self._test_dummy = test_dummy
        self._alternate_dtap = alternate_dtap

        # get mongodb config data
        self._mongo_config_data = get_mongodb_config_data()

        with CODES_GENOMIC_DWH.open('r') as handle:
            self._translation_codes_genomic = yaml.safe_load(handle)

        self._fail_log_dict = {}
        try:
            self._main_main_sender_to_hd()
        except Exception as exceptionmessage:
            send_email(f"{exceptionmessage}\n{traceback.format_exc()}")
            raise

    def _main_main_sender_to_hd(self) -> None:
        """
        Main function, queries the validated documents from Bigsdb that have not been sent to ODS and DWH yet and
        dispatches them to their respective senders to be sent. Creates an aggregated error log to avoid mailspam.
        :return: None
        """
        for species in self._mongo_config_data['species']:
            # Only process pathogens which have been defined in the genomic code translation config file
            if not self._translation_codes_genomic.get(species):
                continue

            mapping_table_collection, isolates_collection = self.__open_mapping_table_and_isolates_collection(species)

            # get documents that need to be sent
            list_of_unsent_validated_documents = isolates_collection.find({'validation.outcome': 'good',
                                                                           '$or': [
                                                                               {'sent_to_ODS_and_DWH': {'$ne': True}},
                                                                               {'changed_since_sent_to_DWH': {'$ne': False}}
                                                                            ]})
            if self._test_dummy:
                list_of_unsent_validated_documents = [genomic_document for genomic_document in list_of_unsent_validated_documents if
                                                      genomic_document['_id'].startswith('test_dummy')]

            self._fail_log_dict[species] = {'fail_counter': 0,
                                            'fail_logs': '',
                                            'fail_ids': []}
            
            for document in list_of_unsent_validated_documents:
                try:
                    self.__trigger_sending_to_ods_and_dwh(document, species, mapping_table_collection,
                                                          isolates_collection)
                except Exception as exceptionmessage:
                    self._fail_log_dict[species]['fail_counter'] += 1
                    self._fail_log_dict[species]['fail_ids'].append(document['_id'])
                    self._fail_log_dict[species]['fail_logs'] += f" {exceptionmessage}\n{traceback.format_exc()}"
                    if self._fail_log_dict[species]['fail_counter'] > 5:
                        # if 5 or more samples fail for a single pathogen, something is seriously wrong,
                        # break the current pathogen for loop and continue to the next pathogen
                        break
        self.__send_email_if_failures()

    def __open_mapping_table_and_isolates_collection(self, species: str) -> (Collection, Collection):
        """
        Opens the mapping table and isolates collections.
        :param species: commonly used bioit species name: either genus or specific like stec
        :return: mapping table collection + isolates collection
        """
        mongoinit_azure = MongoInitialisation(species, mongo_config_data=self._mongo_config_data,
                                              selected_connection_string='CONNECTION_STRING_AZURE',
                                              alternate_dtap=self._alternate_dtap)
        isolates_collection, old_isolateresults_collection, isolates_badqc_collection, \
            isolates_resequencing_collection = mongoinit_azure.initialise_collections()

        mongoinit_local = MongoInitialisation(species, mongo_config_data=self._mongo_config_data,
                                              selected_connection_string='CONNECTION_STRING_LOCAL',
                                              alternate_dtap=self._alternate_dtap)
        # Seeing as there is no validation for all samples in place yet, I'm going to assume here that the validation info can be found in the isolates collection
        # todo
        mapping_table_collection = mongoinit_local.initialise_mapping_table_collection()
        return mapping_table_collection, isolates_collection

    def __trigger_sending_to_ods_and_dwh(self, document_genomic: Dict[str, Any], species: str,
                                         mapping_table_collection: Collection,
                                         isolates_collection: Collection) -> None:
        """
        Triggers the scripts to send the data to the ODS and DWH if they have not been sent yet
        :param document_genomic: genomic document
        :param species: commonly used bioit species name: either genus or specific like stec
        :param mapping_table_collection: local MongoDB collection storing the mapping table
        :param isolates_collection: remote MongoDB collection storing the genomic indicators
        :return: None
        """
        document_mapping_table = mapping_table_collection.find_one({'pseudo_id': document_genomic['_id']})
        if not document_genomic.get('sent_to_ODS'):
            SendMappingTableToODS(document_mapping_table, species, alternate_dtap=self._alternate_dtap)
            isolates_collection.update_one({'_id': document_genomic['_id']},
                                           {"$set": {"sent_to_ODS": True}})
        
        if not document_genomic.get('sent_to_DWH') or document_genomic.get('changed_since_sent_to_DWH'):
            # Get the genomic document and transform it into a non-pseudonymized one
            document_genomic['_id'] = document_mapping_table['_id']
            document_genomic['pseudo_id'] = document_mapping_table['pseudo_id']
            document_genomic['TX_BUSINESS_KEY'] = document_mapping_table['TX_BUSINESS_KEY']
        
            SendGenomicToDWH(document_genomic, self._mongo_config_data, species, alternate_dtap=self._alternate_dtap)
        
            # technically overkill to add this field here because right after sent_to_ODS_and_DWH is updated,
            # but it is added for clarity and so that the order of sending can be changed easily too
            isolates_collection.update_one({'_id': document_genomic['_id']},
                                           {"$set": {"sent_to_DWH": True, "changed_since_sent_to_DWH": False}})
        
        isolates_collection.update_one({'_id': document_genomic['_id']},
                                       {"$set": {"sent_to_ODS_and_DWH": True}})

    def __send_email_if_failures(self) -> None:
        """
        Sends an email if there are any failures.
        All failures are aggregated in the self._fail_log_dict to avoid mailspam
        :return: None
        """
        if sum(fail_dict['fail_counter'] for species, fail_dict in self._fail_log_dict.items()) > 0:
            email_body = ''
            for species, fail_dict in self._fail_log_dict.items():
                email_body += f"{fail_dict['fail_counter']}{' and more' if fail_dict['fail_counter'] == 5 else ''} " \
                              f"failures for {species} with ids " \
                              f"{fail_dict['fail_ids']}{' and more' if fail_dict['fail_counter'] == 5 else ''}, " \
                              f"logs:\n {fail_dict['fail_logs']}\n"
            send_email(email_body)


if __name__ == '__main__':
    MainSenderToHD()
