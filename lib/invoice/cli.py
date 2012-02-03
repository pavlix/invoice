#!/usr/bin/python3

import os, sys, argparse, datetime, subprocess
import invoice.db

import logging
log = logging.getLogger()

class SanityCheckError(Exception):
    pass

class Application:
    my_company = "my-company"

    editor = os.environ.get("EDITOR") or "vim"
    viewer = os.environ.get("PAGER") or "less"
    tex_program = "pdflatex"
    pdf_program = "xdg-open"

    def __init__(self, template_path):
        self._parse_args()
        exec(open(os.path.expanduser(os.path.join(self.args.user_data, "config"))).read(),
            {"__builtins__": None}, self.__dict__)
        self.year = self.args.__dict__.pop("year")
        self.user_path = os.path.expanduser(self.args.__dict__.pop("user_data"))
        self.method = self.args.__dict__.pop("method")
        self.data_path = os.path.join(self.user_path, "{year}", "data", "{directory}")
        self.tmp_path = os.path.join(self.user_path, "tmp")
        self.output_path =  os.path.join(self.user_path, "{year}", "output")
        self.template_path = template_path
        self.db = invoice.db.Database(
            year = self.year,
            data_path = self.data_path)

    def _parse_args(self):
        parser = argparse.ArgumentParser(
            description = "Pavel Šimerda's invoice CLI application.",
            conflict_handler = "resolve")
        parser.add_argument("--year", "-y", action="store")
        parser.add_argument("--user-data", "-d", action="store")
        parser.add_argument("--debug", "-D", action="store_const", dest="log_level", const=logging.DEBUG)
        #parser.add_argument("--verbose", "-v", action="store_const", dest="log_level", const=logging.INFO)
        #parser.add_argument("--config", "-C", action="store")
        parser.set_defaults(
            year = datetime.date.today().year,
            user_data = "~/.invoice",
            log_level = logging.INFO)

        subparsers = parser.add_subparsers(title="subcommands",
            description="valid subcommands",
            help="additional help")

        for list_ in "invoices", "companies":
            for action in "list", "new", "edit", "show", "pdf", "delete":
                if action == "pdf" and list_ != "invoices":
                    continue
                suffix = ''
                if list_ == "companies":
                    suffix = "-companies" if action=="list" else "-company"
                method = getattr(self, "do_"+(action+suffix).replace("-", "_"))
                subparser = subparsers.add_parser(action+suffix, help=method.__doc__)
                if method == self.do_pdf:
                    subparser.add_argument("--generate", "-g", action="store_true")
                if action == "delete":
                    subparser.add_argument("--force", "-f", action="store_true")
                if action == "new":
                    subparser.add_argument("name" if suffix else "company_name")
                if action in ("show", "pdf", "edit", "delete"):
                    subparser.add_argument("selector", nargs="?")
                subparser.set_defaults(method=method)

        self.args = parser.parse_args()
        log.setLevel(self.args.__dict__.pop("log_level"))
        log.debug("Arguments: {}".format(self.args))

    def run(self):
        try:
            self.method(**vars(self.args))
        except (SanityCheckError) as error:
            print("Error: {} Use '--force' to suppress this check.".format(error), file=sys.stderr)
            if log.isEnabledFor(logging.DEBUG):
                raise
        except invoice.db.DatabaseError as error:
            print("Error: {}".format(error), file=sys.stderr)
            if log.isEnabledFor(logging.DEBUG):
                raise

    def do_list(self):
        """List invoices."""
        for item in sorted(self.db.invoices):
            print(item)

    def do_new(self, company_name):
        """Create and edit a new invoice."""
        item = self.db.invoices.new(company_name)
        self._edit(item._path)

    def do_edit(self, selector):
        """Edit invoice in external editor.

        The external editor is determined by EDITOR environment variable
        using 'vim' as the default. Item is edited in-place.
        """
        self._edit(self.db.invoices[selector]._path)

    def _edit(self, path):
        log.debug("Editing file: {}".format(path))
        assert os.path.exists(path)
        subprocess.call((self.editor, path))

    def do_show(self, selector):
        """View invoice in external viewer.

        The external viewer is determined by PAGER environment variable
        using 'less' as the default.
        """
        item = self.db.invoices[selector]
        self._show(item._path)

    def do_pdf(self, selector, generate):
        """Generate and view a PDF invoice.

        This requires Tempita 0.5.
        """
        import tempita
        invoice = self.db.invoices[selector]

        tmp_path = self.tmp_path.format(year=self.year)
        output_path = self.output_path.format(year=self.year)
        log.debug("tmp_path={}".format(tmp_path))

        tex_template = os.path.join(self.template_path, "invoice.tex")
        tex_file = os.path.join(tmp_path, "{}.tex".format(invoice._name))
        tmp_pdf_file = os.path.join(tmp_path, "{}.pdf".format(invoice._name))
        pdf_file = os.path.join(output_path, "{}.pdf".format(invoice._name))

        if generate:
            #if(not os.path.exists(pdf_file) or
            #        os.path.getmtime(invoice._path) > os.path.getmtime(pdf_file)):
            issuer = self.db.companies[self.my_company]
            customer = self.db.companies[invoice.company_name]

            invoice_data = invoice.data()
            issuer_data = issuer.data()
            customer_data = customer.data()

            log.debug("Invoice: {}".format(invoice_data._data))
            log.debug("Issuer: {}".format(issuer_data._data))
            log.debug("Customer: {}".format(customer_data._data))

            log.debug("Creating TeX invoice...")
            self._check_path(self.tmp_path)
            result = tempita.Template(open(tex_template).read()).substitute(
                invoice=invoice_data, issuer=issuer_data, customer=customer_data)
            open(tex_file, "w").write(str(result))
            assert(os.path.exists(tex_file))

            log.debug("Creating PDF invoice...")
            if subprocess.call((self.tex_program, "{}.tex".format(invoice._name)), cwd=tmp_path) != 0:
                raise GenerationError("PDF generation failed.")
            assert(os.path.exists(tmp_pdf_file))

            log.debug("Moving PDF file to the output directory...")
            self._check_path(output_path)
            os.rename(tmp_pdf_file, pdf_file)

        assert(os.path.exists(pdf_file))
        log.debug("Running PDF viewer...")
        subprocess.call((self.pdf_program, pdf_file))

    def _check_path(self, path):
        if not os.path.exists(path):
            raise LookupError("Directory doesn't exist: {}".format(path))

    def do_delete(self, selector, force):
        """List invoices."""
        if selector:
            invoice = self.db.invoices[selector]
        else:
            invoice = self.db.invoices.last()
        if not force:
            raise SanityCheckError("It is not recommended to delete invoices.")
        invoice.delete()

    def do_list_companies(self):
        """List companies."""
        for item in sorted(self.db.companies):
            print(item)

    def do_new_company(self, name):
        """Create and edit a new company."""
        item = self.db.companies.new(name)
        self._edit(item._path)

    def do_edit_company(self, selector):
        """Edit company in external editor.

        The external editor is determined by EDITOR environment variable
        using 'vim' as the default. Item is edited in-place.
        """
        item = self.db.companies[selector]
        self._edit(item._path)

    def do_show_company(self, selector):
        """View company in external viewer.

        The external viewer is determined by PAGER environment variable
        using 'less' as the default.
        """
        item = self.db.companies[selector]
        self._show(item._path)

    def _show(self, path):
        log.debug("Viewing file: {}".format(path))
        assert os.path.exists(path)
        subprocess.call((self.viewer, path))

    def do_delete_company(self, selector, force):
        """Delete a company."""
        company = self.db.companies[selector]
        if not force:
            invoices = self.db.invoices.select({"company_name": company._name})
            if invoices:
                for invoice in invoices:
                    log.info("Dependent invoice: {}".format(invoice))
                raise SanityCheckError("This company is used by some invoices. You should not delete it.")
        company.delete()
