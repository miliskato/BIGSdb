import json
import sys
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, Union

PYTHONPATH = Path(__file__).resolve().parent.parent.parent
sys.path.append(str(PYTHONPATH))

from bioit_mongodb_scripts.util.mongo_initialisation import MongoInitialisation
from bioit_mongodb_scripts.util.python_utility_functions import get_mongodb_config_data, send_email


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
    if not type(mapping_table_dict) == dict:
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
    The TX_BUSINESS_KEY is a key by HD that is a concatenation of the HCO and the sample ID and is what they use to link
    all DCDs. We need to use this as well to link all DCDs because not all DCDs contain the sample id.
    :param mapping_table_dict: the mapping table dictionary
    :param start_response: the response Callable belonging to the incoming POST request
    :return: a success or failure response
    """
    try:
        mongo_config_data = get_mongodb_config_data()
        mongoinit = MongoInitialisation(species=mapping_table_dict['species'],
                                        mongo_config_data=mongo_config_data,
                                        alternate_dtap=mapping_table_dict['dtap'],
                                        alternate_connection_string=mongo_config_data.get('CONNECTION_STRING_LOCAL'))
        mapping_table_collection = mongoinit.initialise_mapping_table_collection()
        already_present = mapping_table_collection.find_one({'_id': mapping_table_dict['id']})
        if not already_present:
            mapping_table_collection.insert_one({'_id': mapping_table_dict['id'],
                                                 'pseudo_id': mapping_table_dict['pseudo_id'],
                                                 'TX_BUSINESS_KEY': mapping_table_dict['TX_BUSINESS_KEY']})
            # Set the response status and headers
            status = '200 OK'
            response_headers = [('Content-type', 'text/plain')]
            start_response(status, response_headers)

            # Return a response
            return [b"Message handled and inserted into MongoDB"]
        else:
            # Set custom status code
            status = '299 OK'
            response_headers = [('Content-type', 'text/plain')]
            start_response(status, response_headers)

            # Return the already present pseudo_id for the given id
            return [already_present['pseudo_id'].encode('utf-8')]
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
