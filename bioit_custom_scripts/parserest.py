import requests
response = requests.get("https://rest.pubmlst.org/db/pubmlst_neisseria_seqdef/loci/rpos/27")
json_data = response.json()

if json_data['status'] != 404:
    print('yes we get something')
    print(json_data)
else:
    print('nothing here')
if json_data['linked_data']:

    print(json_data['linked_data'])

if 'a' in json_data['linked_data'].keys():
    print('yes')
else:
    print('no')

#https://rest.pubmlst.org/db/pubmlst_neisseria_seqdef/loci/rpoB/alleles/27