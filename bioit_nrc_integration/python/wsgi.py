import json
import sys
import uuid
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, Union

PYTHONPATH = Path(__file__).resolve().parent.parent.parent
sys.path.append(str(PYTHONPATH))

from bioit_mongodb_scripts.util.mongo_config_provider import MongoConfigProvider
from bioit_mongodb_scripts.util.mongo_initialisation import MongoInitialisation
from bioit_mongodb_scripts.util.python_utility_functions import send_email


def handle_message(environ: Dict[str, Any], start_response: Callable) -> Iterable[bytes]:
    """
    Handles the post message and inserts message contents in MongoDB.
    :param environ: see application function.
    :param start_response: see application function.
    :return: Sends a message to the client.
    """
    # Read the request body
    request_body = environ['wsgi.input'].read()

    # parse request body
    mapping_table_dict = load_request_body_as_json(request_body, start_response)
    # if the parsing failed, the mapping table dict is a bytes iterable and not a dict.
    # The bytes iterable needs to be returned.
    if not isinstance(mapping_table_dict, dict):
        return mapping_table_dict

    # Insert mapping table into mongodb
    return insert_into_mongodb(mapping_table_dict, start_response)


def load_request_body_as_json(request_body: bytes, start_response: Callable) -> Union[Dict[str, str], Iterable[bytes]]:
    """
    Tries to load the request body as json, returns a failure response if it fails.
    :param request_body: the body of the incoming POST request
    :param start_response: the response Callable belonging to the incoming POST request
    :return: the body as a dictionary or a failure reponse
    """
    try:
        return json.loads(request_body.decode('utf-8'))
    except Exception as exceptionmessage:
        # Set the response status and headers
        status = '400 Bad Request'
        response_headers = [('Content-type', 'text/plain')]
        start_response(status, response_headers)

        # Return a response, because you can not use an f string in a b string, need to use encode
        response_message = f"Invalid JSON: {exceptionmessage}"
        send_email(response_message)
        return [response_message.encode('utf-8')]


def insert_into_mongodb(mapping_table_dict: Dict[str, str], start_response: Callable) -> Iterable[bytes]:
    """
    Tries to insert the mapping table into MongoDB, returns a failure response if it fails.
    The TX_BUSINESS_KEY is a key by HD that is a concatenation of the codeid of the HCO (not RIZIV nr) and the sample ID.
    Seeing as it uses the codeid of the HCO and not the actual RIZIV nr, it is of no further use to us, but
    we need to send this to HD through our outgoing DCD(s)/SFTP flow(s).
    The count serves to keep track how many times the pseudonymization for this _id was done, and to name the fq/fa
    files in Azure differently so that they do not interfere with each other during the archival step.
    :param mapping_table_dict: the mapping table dictionary
    :param start_response: the response Callable belonging to the incoming POST request
    :return: a success or failure response
    """
    try:
        mongo_config_provider = MongoConfigProvider(alternate_dtap=mapping_table_dict['dtap'])
        species = mapping_table_dict['species']
        mongoinit = MongoInitialisation(species, mongo_config_provider.get_local_connection_string(species), mongo_config_provider.dtap)
        mapping_table_collection = mongoinit.initialise_mapping_table_collection()
        already_present = mapping_table_collection.find_one({'_id': mapping_table_dict['id']})
        count = 1
        if not already_present:
            pseudo_id = str(uuid.uuid4())
            mapping_table_collection.insert_one({'_id': mapping_table_dict['id'],
                                                 'pseudo_id': pseudo_id,
                                                 'TX_BUSINESS_KEY': mapping_table_dict['TX_BUSINESS_KEY'],
                                                 'count': count})
            pseudo_id = already_present['pseudo_id']
            count = already_present.get('count', count) + 1
        else:
            pseudo_id = already_present['pseudo_id']
            count = already_present.get('count', count) + (1 if not mapping_table_dict.get('decrease_count') else -1)
            mapping_table_collection.update_one({'_id': mapping_table_dict['id']},
                                                {'$set': {'count': count}})

        # Set the response status and headers
        status = '200 OK'
        response_headers = [('Content-type', 'text/plain')]
        start_response(status, response_headers)

        # Return the unique pseudo_id for the id
        return [f"{pseudo_id}_{count}".encode('utf-8')]
    except Exception as exceptionmessage:
        # Set the response status and headers
        status = '400 Bad Request'
        response_headers = [('Content-type', 'text/plain')]
        start_response(status, response_headers)

        # Return a response, because you can not use an f string in a b string, need to use encode
        response_message = f"MongoDB insertion failed {exceptionmessage}"
        send_email(response_message)
        return [response_message.encode('utf-8')]


def application(environ: Dict[str, Any], start_response: Callable) -> Iterable[bytes]:
    """
    WSGI application entry point.
    :param environ: A dictionary containing CGI-like environment variables.
    :param start_response: A callback function used to start the response.
    :return: Sends a message to the client.
    """
    # Get the request body
    if environ['REQUEST_METHOD'] == 'POST':
        return handle_message(environ, start_response)
    raise NotImplementedError()
