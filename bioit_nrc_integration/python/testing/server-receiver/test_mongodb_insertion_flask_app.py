# Run this app by executing:
# sudo su
# source 3.10PythonVenv/bin/activate ; python test_mongodb_insertion_flask_app.py
# enter passphrase found in keepass twice

# Example command to access this app from any VM as long as you have the cert.pem file:
# curl -XPOST --data  '{"id": "test", "id_pseudonymized": "test_pseudo", "species": "neisseria", "dtap": "dev"}' https://10.6.8.11:5000 --cacert /home/mikelchtermans/cert.pem

import json
import logging
import sys
from pathlib import Path

from flask import Flask, request

PYTHONPATH = Path(__file__).resolve().parent.parent.parent.parent.parent
sys.path.append(str(PYTHONPATH))

from bioit_mongodb_scripts.util.mongo_initialisation import MongoInitialisation
from bioit_mongodb_scripts.util.python_utility_functions import get_mongodb_config_data, send_email

app = Flask(__name__)

# Configure logging
logging.basicConfig(level=logging.DEBUG)


@app.route('/', methods=['POST'])
def handle_request():
    body = request.get_data()
    mapping_table_dict = json.loads(body.decode('utf-8'))
    # example: mapping_table = {'id': 'test',
    # 				            'id_pseudonymized': 'test_pseudo',
    # 				            'species': 'neisseria',
    # 				            'dtap': 'dev'}
    app.logger.debug(body.decode('utf-8'))
    mongo_config_data = get_mongodb_config_data()
    mongoinit = MongoInitialisation(species=mapping_table_dict['species'],
                                    mongo_config_data=mongo_config_data,
                                    alternate_dtap=mapping_table_dict['dtap'],
                                    alternate_connection_string=mongo_config_data.get('CONNECTION_STRING_LOCAL'))
    mapping_table_collection = mongoinit.initialise_mapping_table_collection()
    mapping_table_collection.insert_one({'_id': mapping_table_dict['id'],
                                         'id_pseudonymized': mapping_table_dict['id_pseudonymized']})

    return 'Request body written to mongo.'


if __name__ == '__main__':
    app.run(host='0.0.0.0',  # broadcasting on localhost and actual ip
            ssl_context=('/home/mikelchtermans/certificate.crt', '/home/mikelchtermans/private.key'),  # use self generated ssl certificate
            debug=True)  # write debug messages to console
