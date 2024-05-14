# WSGI application that apache2 sends requests to

# Can be triggered using e.g.: curl -XPOST --data '{"id": "test", "id_pseudonymized": "test_pseudo", "species": "neisseria", "dtap": "dev"}' https://10.6.8.11:443 --cacert /home/mikelchtermans/cert.pem

import json
import jwt
import sys
from datetime import datetime, timedelta
from pathlib import Path
import socket
from typing import Any, Callable, Dict, Iterable, Optional

PYTHONPATH = Path(__file__).resolve().parent.parent.parent.parent.parent
sys.path.append(str(PYTHONPATH))

from bioit_mongodb_scripts.util.mongo_initialisation import MongoInitialisation
from bioit_mongodb_scripts.util.python_utility_functions import get_mongodb_config_data, send_email
# todo use send email?

# Secret key to sign the JWTs (keep this secure)
SECRET_KEY = 'to_be_replaced_by_ansible'

# Dictionary to store user passwords (in a real-world scenario, passwords should be securely hashed)
SECRET_PASSWORD = 'to_be_replaced_by_ansible'


def authenticate(username, password) -> Optional[str]:
    """
    Authenticates the user and generates a token if authentication is succesfull.
    :param username: username
    :param password: password
    :return: token or None
    """
    # Check if the provided username exists and the password matches
    if username == 'bioit' and password == SECRET_PASSWORD:
        # Return the generated token
        # Set token expiration time (e.g., 1 hour from now)
        expiration_time = datetime.utcnow() + timedelta(hours=1)

        # Define payload with user ID and expiration time
        payload = {
            'user_id': username,
            'exp': expiration_time
        }

        # Generate JWT token
        token = jwt.encode(payload, SECRET_KEY, algorithm='HS256')
        return token
    else:
        return None


def return_token(environ: Dict[str, Any], start_response: Callable) -> Iterable[bytes]:
    """
    Returns a token if authentication credentials are good.
    :param environ: see application function.
    :param start_response: see application function.
    :return: Sends a message to the client.
    """
    # Extract username and password from the request
    username = None
    password = None
    status = '200 OK'
    response_headers = [('Content-type', 'text/plain')]
    start_response(status, response_headers)
    try:
        # For GET requests, extract username and password from query string
        query_string = environ.get('QUERY_STRING', '')
        for param in query_string.split('&'):
            key, value = param.split('=', 1)
            if key == 'username':
                username = value
            elif key == 'password':
                password = value
    except Exception as e:
        username = None
        password = None

    token = None
    if username and password:
        token = authenticate(username, password)
    if token:
        status = '200 OK'
        response_headers = [('Content-type', 'application/json')]
        start_response(status, response_headers)
        tokendict = {'token': token}
        return [json.dumps(tokendict).encode()]
    else:
        status = '401 Unauthorized'
        response_headers = [('Content-type', 'text/plain')]
        start_response(status, response_headers)
        send_email(f"Unauthorized request to NRC-integration VM {socket.gethostname()}")  # todo check if i can add remote address from where it failed once nginx solution is in place
        return [b"Authentication required."]


def verify_token(token: str) -> Optional[str]:
    """
    Verify the legitimacy of the token.
    :param token: token
    :return: decoded token or None
    """
    try:
        # Verify the token and decode its payload
        decoded_token = jwt.decode(token, SECRET_KEY, algorithms=['HS256'])
        # You can perform additional validation or checks here if needed
        return decoded_token
    except jwt.ExpiredSignatureError:
        # Token has expired
        return None
    except jwt.InvalidTokenError:
        # Invalid token
        return None


def handle_message(environ: Dict[str, Any], start_response: Callable) -> Iterable[bytes]:
    """
    Handles the post message; if token is valid, inserts contents in MongoDB.
    :param environ: see application function.
    :param start_response: see application function.
    :return: Sends a message to the client.
    """
    token = None
    query_string = environ.get('QUERY_STRING', '')
    for param in query_string.split('&'):
        key, value = param.split('=', 1)
        if key == 'token':
            token = value
    decoded_token = verify_token(token)
    if decoded_token:
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
    else:
        status = '401 Unauthorized'
        response_headers = [('Content-type', 'text/plain')]
        start_response(status, response_headers)
        send_email(f"Token absent or invalid") # todo check if i can add remote address from where it failed once nginx solution is in place
        return [b"Token absent or invalid"]


def application(environ: Dict[str, Any], start_response: Callable) -> Iterable[bytes]:
    """
    WSGI application entry point.
    :param environ: A dictionary containing CGI-like environment variables.
    :param start_response: A callback function used to start the response.
    :return: Sends a message to the client.
    """
    # Get the request method
    request_method = environ['REQUEST_METHOD']

    if request_method == 'GET':
        return return_token(environ, start_response)

    # Get the request body
    elif request_method == 'POST':
        return handle_message(environ, start_response)
