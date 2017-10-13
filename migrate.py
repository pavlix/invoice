#!/usr/bin/python3

import os
import sys
import glob
import yaml

data_dir = os.path.expanduser("~/.local/paperwork")

def read_from_0_1():
    data_path = os.path.join(data_dir, "{year}/data/{directory}")
    years = [int(os.path.basename(year)) for year in glob.glob(os.path.join(data_dir, "????"))]

    sys.path.append("lib")
    import invoice.db

    data = {}
    for year in years:
        try:
            db = invoice.db.Database(year=year, data_path=data_path)
            for item in db.invoices:
               data.setdefault(year, []).append(item.data()._data)
        except FileNotFoundError:
            pass

    return data
    
if __name__ == "__main__":
    print(yaml.safe_dump(read_from_0_1()))
