from .base import DatabaseError

class Database:
    def __init__(self, **config):
        from . import companies
        from . import invoices
        self.companies = companies.Companies(db=self, **config)
        self.invoices = invoices.Invoices(db=self, **config)
