import datetime

from bioit_bigsdb_scripts.Typing_alleles_intopsql import TypingAllelesIntoPsql
from bioit_bigsdb_scripts.Typing_loci_intopsql import TypingLociIntoPsql
from bioit_bigsdb_scripts.Typing_schemeprofiles_intopsql import TypingSchemeProfilesIntoPsql
from bioit_bigsdb_scripts.components.psql import TblAlleleDesignations
from bioit_bigsdb_scripts.genedetection_intopsql import GeneDetectionIntoPsql
from bioit_mongodb_scripts.util.mongo_initialisation import MongoInitialisation
from bioit_mongodb_scripts.util.python_utility_functions import get_mongodb_config_data


class UpdateBIGSdbSeqDef:
    """
    Updates the scheme definitions stored in BIGSdb seqdef database if the reference db used to run the pipelines were updated.
    """

    def __init__(self, species: str):
        """
        intializes the connection to mongodb AZURE collections "update_metadata" and "new_allele_hashes"
        :param species: species name
        """
        self._mongo_config_data = get_mongodb_config_data()
        self._species = species
        mongoinit_azure = MongoInitialisation(self._species, mongo_config_data=self._mongo_config_data,
                                              selected_connection_string='CONNECTION_STRING_AZURE')
        self._update_metadata_collection = mongoinit_azure.initialise_update_collection()
        self._hashed_ad_collection = mongoinit_azure.initialise_hashing_collection()

    def update_bigsdb_psql_if_needed(self) -> None:
        """
        This function checks whether a new dbupdate occured in Azure and updates all info in Bigsdb accordingly.
        :return: None
        """
        last_schema_update_date_document = self._update_metadata_collection.find_one({'metadata': 'last_dbupdate_insertion_date'})
        last_dbupdate_date = self._update_metadata_collection.find_one({'metadata': 'last_dbupdate_date'})['last_update_date']
        if not last_schema_update_date_document or last_dbupdate_date > last_schema_update_date_document['last_update_date']:
            # Run the temporary id replacer
            self._replace_tempids()

            # Insert new typing loci, alleles, typing profiles & gene detection alleles into psql
            TypingLociIntoPsql([self._species], dont_send_email=True)
            TypingAllelesIntoPsql([self._species], dont_send_email=True)
            TypingSchemeProfilesIntoPsql([self._species], dont_send_email=True)
            GeneDetectionIntoPsql(self._species, do_not_recalculate=True, dont_send_email=True).insert_schemes()
            # update last insertion date
            self._update_metadata_collection.update_one({'metadata': 'last_dbupdate_insertion_date'},
                                                        {'$set': {'last_update_date': datetime.datetime.now(
                                                            datetime.timezone.utc)}}, upsert=True)

    def _replace_tempids(self) -> None:
        """
        Replaces the temporary ids of alleles in bigsdb by actual allele numbers found in Pubmlst/Enterobase and
        indicated as such by Azure: "resolved_AD".
        :return: None
        """
        documents_list = [document for document in self._hashed_ad_collection.find(
            {'scheme': {'$in': self._mongo_config_data['schemes_sequence_typing']},
             'resolved_AD': {'$ne': 0}, 'replaced_in_bigs_date': {'$exists': False}})]

        with TblAlleleDesignations(self._species) as isolates_ad_psql_tbl:
            for hash_document in documents_list:
                isolates_ad_psql_tbl.update_designations(
                    (hash_document['resolved_AD'], hash_document['locus'], hash_document['hashed_allele']))
        self._hashed_ad_collection.update_many(
            {'_id': {'$in': [hash_document['_id'] for hash_document in documents_list]}},
            {'$set': {'replaced_in_bigs_date': datetime.datetime.now()}})
