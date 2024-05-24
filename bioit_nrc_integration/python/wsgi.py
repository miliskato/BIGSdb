from wsgiref.simple_server import make_server
import json
import sys
from pathlib import Path
from typing import Any, Callable, Dict, Iterable

CUSTOM_PORT='to_be_replaced_by_ansible'

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
    mapping_table_dict = json.loads(request_body.decode('utf-8'))
    try:
        mongo_config_data = get_mongodb_config_data()
        mongoinit = MongoInitialisation(species=mapping_table_dict['species'],
                                        mongo_config_data=mongo_config_data,
                                        alternate_dtap=mapping_table_dict['dtap'],
                                        alternate_connection_string=mongo_config_data.get('CONNECTION_STRING_LOCAL'))
        mapping_table_collection = mongoinit.initialise_mapping_table_collection()
        mapping_table_collection.insert_one({'_id': mapping_table_dict['id'],
                                             'id_pseudonymized': mapping_table_dict['id_pseudonymized']})
        # Set the response status and headers
        status = '200 OK'
        response_headers = [('Content-type', 'text/plain')]
        start_response(status, response_headers)

        # Return a response
        return [b"Message handled and inserted into MongoDB"]
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


if __name__ == '__main__':
    application = application()