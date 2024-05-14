import json
import requests


integration_vm_ip = '10.6.8.11'

mapping_table = {'id': 'test2',
                 'id_pseudonymized': 'test_pseudo',
                 'species': 'yersinia',
                 'dtap': 'test2'}
params = {'username': 'mikelchtermans', 'password': 'test'}
headers = {'Content-Type': 'application/json'}
response = requests.get(f"https://{integration_vm_ip}", params=params, headers=headers, verify=False)

if response.status_code == 200:
    print("Request successful. Response code: 200")
    token = json.loads(response.text).get('token')
    response2 = requests.post(f"https://{integration_vm_ip}", params={'token': token}, data=(json.dumps(mapping_table)).encode(), headers=headers, verify=False)
    print(response2.status_code, response2.text)
