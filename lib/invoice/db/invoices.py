#!/usr/bin/python3

import os, sys, re, time, datetime

import logging
log = logging.getLogger()

from invoice.db.base import *

class Invoices(List):
    """Company invoice.

    When editing data files, you can use the following
    directives:

    Item -- price, followed by ':', optional whitespace and item description
    Due -- Due date YYYY-MM-DD
    Note -- a note at the and of the invoice
    """
    data_template = """\
Item: 
"""
    _directory = "income"
    _regex = re.compile("^(?P<date>[0-9]{8})-(?P<number>[0-9]{3})-(?P<company_name>[a-z0-9-]+)$")
    _template = "{date}-{number:03}-{company_name}"

    def _item_class(self):
        return Invoice

    def _select(self, selector):
        if isinstance(selector, str):
            match = self._regex.match(selector)
            if match:
                selector = match.groupdict()
                selector["number"] = int(selector["number"])
            else:
                try:
                    selector = int(selector)
                except TypeError:
                    raise ItemNotFoundError("Item not found: {}".format(selector))
        return super(Invoices, self)._select(selector)

    def new(self, company_name):
        if company_name not in self._db.companies:
            raise ItemNotFoundError("Company '{}' not found.".format(company_name))
        try:
            number = max(item.number for item in self) + 1
        except ValueError:
            number = 1
        date = time.strftime("%Y%m%d")
        name = self._template.format(**vars())
        return super(Invoices, self).new(name)

class Invoice(Item):
    def _data_class(self):
        return InvoiceData

    def _postprocess(self):
        self._selector["number"] = int(self.number)

class InvoiceData(Data):
    _fields = ["due", "paid", "payment"]
    _multivalue_fields = ["item", "address", "note"]
    _date_regex = re.compile(r"^(\d{4})-?(\d{2})-?(\d{2})$")
    _item_regex = re.compile(r"^(-?\d+)[:;]\s*(.*)$")
    _number_template = "{year}{number:03}"

    def _parse_date(self, date):
        match = self._date_regex.match(self.date)
        if not match:
            raise ValueError("Bad date format: {}".format(date))
	log.debug("Date match: {0}".format(match.groups()))
        return datetime.date(*(int(f) for f in match.groups()))

    def _postprocess(self):
        log.debug(self._data)
        self._postprocess_number()
        self._postprocess_items()
        self._postprocess_dates()
        self.rename_key("note", "notes")

    def _postprocess_number(self):
        self._data["number"] = self._number_template.format(
            year = self.year,
            number = self.number)

    def _postprocess_items(self):
        items = []
        for item in self.item:
            match = self._item_regex.match(item)
            if not match:
                raise ValueError("Bad item format: {}".format(item))
            price, description = match.groups()
            items.append((description, int(price)))
        del self._data["item"]
        self._data["items"] = items
        self._data["sum"] = sum(item[1] for item in items)

    def _postprocess_dates(self):
        date = self._parse_date(self._item.date)
        if self.due:
            try:
                due = self._parse_date(self.due)
            except ValueError:
                try:
                    due = datetime.timedelta(int(re.sub("^+", "", self.due)))
                except ValueError:
                    raise ValueError("Bad due format: {}".format(self.due))
        else:
            due = datetime.timedelta(14)
	log.debug("Due: {0}".format(due))
        if isinstance(due, datetime.timedelta):
            due += date
        self._data["date"] = date
        self._data["due"] = due
