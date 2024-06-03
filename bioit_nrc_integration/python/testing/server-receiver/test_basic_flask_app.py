# Run this app by executing:
# sudo su
# source 3.10PythonVenv/bin/activate ; python test_basic_flask_app.py
# enter passphrase found in keepass twice

# Example command to access this app from any VM as long as you have the cert.pem file:
# curl -XPOST --data "field01=value01&field02=value02" https://10.6.8.11:5000 --cacert /home/mikelchtermans/cert.pem

from flask import Flask, request
import logging

app = Flask(__name__)

# Configure logging
logging.basicConfig(level=logging.DEBUG)


@app.route('/', methods=['POST'])
def handle_request():
    app.logger.debug(request.environ)
    body = request.get_data()
    app.logger.debug(body.decode('utf-8'))
    with open('request_bodies.txt', 'a') as f:
        f.write(body.decode('utf-8'))
        f.write('\n\n')

    return 'Request body written to file.'


if __name__ == '__main__':
    app.run(host='0.0.0.0',  # broadcasting on localhost and actual ip
            ssl_context=('/home/mikelchtermans/certificate.crt', '/home/mikelchtermans/private.key'),  # use self generated ssl certificate
            debug=True)  # write debug messages to console
