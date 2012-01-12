#!/usr/bin/python3

import os, sys, re, time, datetime

import logging
log = logging.getLogger()

class DatabaseError(Exception):
    pass

class ItemNotFoundError(DatabaseError, LookupError):
    pass

class ItemNameCheckError(DatabaseError, ValueError):
    pass

class ItemExistsError(DatabaseError):
    pass

class List:
    """Base class for database lists.
    
    This class provides a real-time view to a file-based database. It can be
    used as an iterable with a little bit of magic (like indexing by a
    dictionary of matching attributes).
    """
    def __init__(self, year, data_path, db=None):
        self._year = year
        self._path = os.path.expanduser(data_path.format(
            year=year, directory=self._directory))
        self._db = db
        log.debug("{}: {}".format(self.__class__.__name__, self._path))

    def _item_class(self):
        """Returns class object used to instantiate items.
        
        Override in subclasses.
        """
        return Item

    def _item_name(self):
        return self._item_class().__name__.lower()

    def __iter__(self):
        for name in os.listdir(self._path):
            match = self._regex.match(name)
            if match:
                yield self._item_class()(self, year=self._year, **match.groupdict())

    def last(self):
        return max(iter(self), key=lambda item: item._name)

    def __contains__(self, selector):
        return bool(self._select(selector))

    def __getitem__(self, selector):
        items = self._select(selector)
        assert(len(items) < 2)
        if not items:
            raise ItemNotFoundError("{} '{}' not found.".format(self._item_class().__name__, selector))
        item = items[0]
        log.debug("Found matching item: {}".format(item))
        return item

    def select(self, selector=None):
        return sorted(self._select(selector))

    def _select(self, selector):
        """Return a list of items matching 'name', 'number' or other attributes."""
        if selector == None:
            selector = {}
        if isinstance(selector, str):
            selector = {"name": selector}
        if isinstance(selector, int):
            selector = {"number": number}
        log.debug("Selecting: {}".format(selector))
        assert isinstance(selector, dict)
        return [item for item in self if all(getattr(item, key) == selector[key] for key in selector)]
        
    def new(self, name):
        """Create a new item in this list.
        
        Keyword arguments:
        name -- filesystem name of the new item
        edit -- edit the item after creation
        
        Returns
        """
        log.info("Creating {}: {}".format(self._item_name(), name))
        if not self._regex.match(name):
            raise ItemNameCheckError("Name {} doesn't match {} regex.".format(name, self._item_name()))
        if name in self:
            raise ItemExistsError("Item {} of type {} already exists.".format(name, self._item_name()))
        self._new(os.path.join(self._path, name))
        return self[name]

    def _new(self, path):
        log.debug("Creating {} file: {}".format(self._item_name(), path))
        stream = os.fdopen(os.open(path, os.O_WRONLY|os.O_EXCL|os.O_CREAT, 0o644), "w")
        stream.write(self.data_template)
        stream.close()

class Item:
    """Base class for database list items."""
    def __init__(self, list_, **selector):
        self._list = list_
        self._selector = selector
        self._postprocess()
        self._name = self._list._template.format(**selector)
        self._path = os.path.join(list_._path, self._name)
        log.debug("{!r}".format(self))

    def _postprocess(self):
        """Postprocess the _selector attribute.
        
        Override in subclasses.
        """

    def __lt__(self, other):
        return self._name < other._name

    def __repr__(self):
        return "{}({!r}, **{})".format(self.__class__.__name__, self._name, self._selector)

    def __str__(self):
        return self._name

    def __getattr__(self, key):
        return self._selector[key]

    def delete(self):
        log.info("Deleting: {}".format(self))
        path = self._path
        newpath = path + "~"
        log.debug("Renaming file {} to {}.".format(path, newpath))
        assert os.path.exists(path)
        os.rename(path, newpath)

    def data(self):
        """Return item's data.
       
        Override in subclasses.
        """
        return self._data_class()(self)

    def _data_class(self):
        return Data

class Data:
    """Base class for database list item data objects."""
    _fields = []
    _multivalue_fields = []
    _line_regex = re.compile(r"^([A-Z][a-zA-Z-]*):\s+(.*?)\s+$")

    def __init__(self, item):
        self._item = item
        self._parse(open(self._item._path))
        self._postprocess()

    def __getattr__(self, key):
        return self._data[key]

    def _parse(self, stream):
        self._data = self._item._selector.copy()
        for f in self._fields:
            self._data[f] = None
        for f in self._multivalue_fields:
            self._data[f] = []
        for n, line in enumerate(stream):
            match = self._line_regex.match(line)
            if not match:
                log.warning("Ignoring {}:{}: {}".format(n, self._item._name, line))
                continue
            key, value = match.groups()
            key = key.lower().replace("-", "_")
            if key in self._fields:
                self._data[key] = value
            elif key in self._multivalue_fields:
                self._data[key].append(value)
            else:
                log.warning("Key ignored: {}".format(key))

    def _postprocess(self):
        """Postprocess item data.

        Override in subclasses.
        """
    def rename_key(self, oldkey, newkey):
        """Convenience function mainly intended for subclasses."""
        if not self.__dict__.get(newkey) and oldkey in self._data:
            self._data[newkey] = self._data[oldkey]
            del self._data[oldkey]

