# WSGI application that apache2 sends requests to

# Can be triggered using e.g.: curl -XPOST --data '{"id": "test", "id_pseudonymized": "test_pseudo", "species": "neisseria", "dtap": "dev"}' https://10.6.8.11:443 --cacert /home/mikelchtermans/cert.pem

import json
import sys
from pathlib import Path

PYTHONPATH = Path(__file__).resolve().parent.parent.parent.parent.parent
sys.path.append(str(PYTHONPATH))

from bioit_mongodb_scripts.util.mongo_initialisation import MongoInitialisation
from bioit_mongodb_scripts.util.python_utility_functions import get_mongodb_config_data, send_email

def application(environ, start_response):
    # Get the request method
    request_method = environ['REQUEST_METHOD']

    # Get the request body
    if request_method == 'POST':
        # Read the request body
        request_body = environ['wsgi.input'].read()
        mapping_table_dict = json.loads(request_body.decode('utf-8'))
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
    return [b"OK"]
