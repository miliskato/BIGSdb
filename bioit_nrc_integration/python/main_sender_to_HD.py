# Script should be run hourly in order to limit the nr of mails

import argparse
import logging
import sys
import traceback
import yaml
from pathlib import Path

from pymongo.collection import Collection

PYTHONPATH = Path(__file__).resolve().parent.parent.parent
sys.path.append(str(PYTHONPATH))

from bioit_mongodb_scripts.model.json_model import MongoRecordDict
from bioit_mongodb_scripts.util.mongo_config_provider import MongoConfigProvider
from bioit_mongodb_scripts.util.mongo_initialisation import MongoInitialisation
from bioit_mongodb_scripts.util.python_utility_functions import send_email
from bioit_nrc_integration.python.config import CODES_GENOMIC_ODS
from bioit_nrc_integration.python.send_genomic_to_ODS import SendGenomicToODS

# Configure stdout logging
logging.basicConfig(level=logging.DEBUG, stream=sys.stdout)


def parse_arguments() -> argparse.Namespace:
    """
    Parses the command line arguments.
    :return: Parsed arguments
    """
    argument_parser = argparse.ArgumentParser()
    argument_parser.add_argument('--alternate_dtap', type=str, choices=['dev', 'acc'], default=None,
                                 help=argparse.SUPPRESS)
    return argument_parser.parse_args()


class MainSenderToHD:
    """
    Queries the validated documents from Bigsdb that have not been sent to the ODS yet and
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
        self._mongo_config_provider = MongoConfigProvider(alternate_dtap)

        with CODES_GENOMIC_ODS.open('r') as handle:
            self._translation_codes_genomic = yaml.safe_load(handle)

        self._fail_log_dict = {}
        try:
            self._main_main_sender_to_hd()
        except Exception as exceptionmessage:
            send_email(f"{exceptionmessage}\n{traceback.format_exc()}")
            raise

    def _main_main_sender_to_hd(self) -> None:
        """
        Main function, queries the validated documents from Bigsdb that have not been sent to  the ODS yet and
        dispatches them to their respective senders to be sent. Creates an aggregated error log to avoid mailspam.
        :return: None
        """
        for species in MongoConfigProvider.get_currently_supported_species():
            # Only process pathogens which have been defined in the genomic code translation config file
            if not self._translation_codes_genomic.get(species):
                continue

            mapping_table_collection, isolates_collection = self.__open_mapping_table_and_isolates_collection(species)

            # get documents that need to be sent
            list_of_unsent_validated_documents = isolates_collection.find({'$or': [
                                                                               {'sent_to_ODS': {'$ne': True}},
                                                                               {'changed_since_sent_to_ODS': {'$ne': False}}
                                                                            ]})
            if self._test_dummy:
                list_of_unsent_validated_documents = [genomic_document for genomic_document in list_of_unsent_validated_documents if
                                                      genomic_document['_id'].startswith('test_dummy')]

            self._fail_log_dict[species] = {'fail_counter': 0,
                                            'fail_logs': '',
                                            'fail_ids': []}
            
            for document in list_of_unsent_validated_documents:
                try:
                    self.__trigger_sending_to_ods(MongoRecordDict(document), species, mapping_table_collection, isolates_collection)
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
        mongoinit_azure = MongoInitialisation(species, self._mongo_config_provider.get_azure_connection_string(species), self._mongo_config_provider.dtap)
        isolates_collection, old_isolateresults_collection, isolates_warningqc_collection, isolates_resequencing_collection, isolates_goodqc_collection = mongoinit_azure.initialise_collections()

        mongoinit_local = MongoInitialisation(species, self._mongo_config_provider.get_local_connection_string(species), self._mongo_config_provider.dtap)
        mapping_table_collection = mongoinit_local.initialise_mapping_table_collection()
        return mapping_table_collection, isolates_collection

    def __trigger_sending_to_ods(self, document_genomic: MongoRecordDict, species: str,
                                 mapping_table_collection: Collection,
                                 isolates_collection: Collection) -> None:
        """
        Triggers the scripts to send the data to the ODS if they have not been sent yet
        :param document_genomic: genomic document
        :param species: commonly used bioit species name: either genus or specific like stec
        :param mapping_table_collection: local MongoDB collection storing the mapping table
        :param isolates_collection: remote MongoDB collection storing the genomic indicators
        :return: None
        """
        document_mapping_table = mapping_table_collection.find_one({'pseudo_id': document_genomic.get_id()})
        if not document_genomic.get('sent_to_ODS') or document_genomic.get('changed_since_sent_to_ODS'):
            # Get the genomic document and transform it into a non-pseudonymized one
            document_genomic['_id'] = document_mapping_table['_id']
            document_genomic['pseudo_id'] = document_mapping_table['pseudo_id']
            document_genomic['TX_BUSINESS_KEY'] = document_mapping_table['TX_BUSINESS_KEY']
            SendGenomicToODS(document_genomic, species, self._mongo_config_provider.upload_path)

            isolates_collection.update_one({'_id': document_genomic['pseudo_id']},
                                           {"$set": {"sent_to_ODS": True, "changed_since_sent_to_ODS": False}})

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
    args = parse_arguments()
    MainSenderToHD(alternate_dtap=args.alternate_dtap)
