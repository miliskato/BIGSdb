from typing import Any, Optional

from pymongo.collection import Collection


def insert_document_into_rejected_collection(isolates_rejected_coreqc_collection: Collection,
                                             document_to_be_inserted: dict[str, Any]) -> None:
    """
    Inserts a document into the given isolates_rejected_coreqc collection
    :param isolates_rejected_coreqc_collection:
    :param document_to_be_inserted:
    :return: None
    """
    technical_id = document_to_be_inserted['_id']
    previous_rejected_sample_version: Optional[dict[str, Any]] = isolates_rejected_coreqc_collection.find_one(
        {'_id': technical_id})
    if previous_rejected_sample_version:
        previous_rejected_sample_version['isolates_id'] = technical_id
        previous_rejected_sample_version.pop('_id')
        isolates_rejected_coreqc_collection.insert_one(previous_rejected_sample_version)
        isolates_rejected_coreqc_collection.delete_one({'_id': technical_id})

    isolates_rejected_coreqc_collection.insert_one(document_to_be_inserted)
