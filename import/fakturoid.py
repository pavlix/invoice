#!/usr/bin/python3

import os
import yaml
import requests

CONFIG = os.path.expanduser("~/.config/paperwork/fakturoid.yaml")

with open(CONFIG) as stream:
    config = yaml.load(stream)

url = "https://app.fakturoid.cz/api/v2/accounts/{slug}/invoices.json".format(**config)
auth = requests.auth.HTTPBasicAuth(config["username"], config["key"])

response = requests.get(url, auth=auth)

print(yaml.dump(response.json()))
