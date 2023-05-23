import http.client
import json
import pprint
import logging
from logserver.models import Authenticated_Machine


# Get API ---------------------------------------------------------------------
def get_isms():

    conn = http.client.HTTPConnection("apidp.xxx.com:8443")

    headers = {
        'accept': "application/json",
        'authorization': "ldap xxxxxxxxxxxxxxxxxxxxx"
    }

    conn.request(
        "GET", "/ISMS_OIDC2/hardwareinfo/search?OS_name=RHEL",
        headers=headers
    )

    res = conn.getresponse()
    data = json.loads(res.read().decode("utf-8"))

    pprint(data)

    for d in data:
        am = Authenticated_Machine.objects.filter(hostName__icontains = d['ServerName'])
        if am:
            am[0].asset_ID = d['asset_id']
            am[0].depository_name = d['depository_name']
            am[0].backup_name = d['backup_name']
            am[0].serverIP = d['ServerIP']
            am[0].save()

def isms_file():
    logging.info("(isms_file) Enter function.")
    """
    isms example
    {
        'asset_id': 'H0000626',
        'ServerName': 'xxxxx',
        'ServerIP': '172.16.221.91',
        'Core': '2*2C',
        'OS_id': 288,
        'OS': 'RHEL'
        'OS_Version_id': 303,
        'OS_Version': '4',
        'Memory': '4',
        'Disk_Capacity': 'N/A',
        'depository_name': 'xxx',
        'backup_name': 'xxx'
    }
    """
    isms_file = "/opt/sysmo/server/isms.json"
    with open(isms_file, 'r') as f:
        isms_js =  json.loads(f.read())
        logging.info("(isms_file) Loading ISMS.json file")
        for j in isms_js:
            am = Authenticated_Machine.objects.filter(hostName__icontains = j['ServerName'])
            if am:
                am[0].asset_ID = j['asset_id']
                am[0].depository_name = j['depository_name']
                am[0].backup_name = j['backup_name']
                am[0].serverIP = j['ServerIP']
                am[0].save()
