#!/usr/bin/python3

import os, sys, re, time, datetime

import logging
log = logging.getLogger()

from invoice.db.base import *

class Companies(List):
    """Company list.

    When editing data files, you can use the following directives:

    Name -- full company name
    Address -- company address, repeat to get multiple lines
    Number -- identification number
    Comment -- additional information that you want to see on the invoice
    """    
    _directory = "companies"
    _regex = re.compile("^(?P<name>[a-z0-9-]+)$")
    _template = "{name}"
    _data_template = """\
Name:
Address:
Address:
Number:
"""
    def _item_class(self):
        return Company

class Company(Item):
    def _data_class(self):
        return CompanyData

class CompanyData(Data):
    _fields = ["name", "number", "ic", "bank_account"]
    _multivalue_fields = ["address", "comment"]

    def _postprocess(self):
        self.rename_key("ic", "number")
        self.rename_key("comment", "comments")
