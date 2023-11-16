import csv

import codecs
import re
import csv
import datetime

from models import Account, Holding

BOND_CUSIP_RE = re.compile(r"[A-Z0-9]{6}[A-Z]{2}\d")
BOND_DESC_RE = re.compile(r"(\d{2}\.\d{5}%) (\d{2}/\d{2}/\d{4})")

def read(path):
    with codecs.open(path, encoding="utf-8-sig") as f:
        return f.read()

def parse(contents, config, allow_after):
    accounts = _build_accounts(config)

    sections = contents.split("\r\n\r\n")

    _check_date(sections.pop().strip(), allow_after)

    section = sections.pop()
    if not section.startswith('"Brokerage services are provided'):
        raise Exception("Expected useless section, got: %s" % section)

    section = sections.pop()
    if not section.startswith('"The data and information in this spreadsheet'):
        raise Exception("Expected useless section, got: %s" % section)

    section = sections.pop()
    reader = csv.DictReader(section.splitlines())

    for row in reader:
        try:
            acct_name = row["Account Name"]
            acct = accounts[acct_name]

            symbol = row['Symbol']

            quantity = _parse_num(row['Quantity'])

            if BOND_CUSIP_RE.match(symbol):
                price = _parse_num(row['Current Value']) / quantity
                desc = row['Description']
                match = BOND_DESC_RE.search(desc)
                yield_rate = match[1]
                maturity_date = match[2]
            else:
                price = _parse_num(row['Last Price'])
                yield_rate = _parse_pct(row['Yield'])
                maturity_date = None

            holding = Holding(
                account=acct,
                symbol=row['Symbol'],
                quantity=quantity,
                price=price,
                yield_rate=yield_rate,
                maturity_date=maturity_date
                # We're currently importing the yield sheet that doesn't include cost basis
                # unit_cost=_parse_num(row.get['Cost Basis Per Share'])
            )
            acct.holdings.append(holding)
        except ValueError as e:
            raise ValueError("%s (in %s)" % (e, row))

    return accounts.values()

def _check_date(date_str, allow_after):
    date = datetime.datetime.strptime(date_str, '"Date downloaded %m/%d/%Y %H:%M %p ET"')
    if date < allow_after:
        raise Exception("Export is too old, got a row with date %s" % date_str)

def _build_accounts(config):
    accounts = {}
    for name, sub in config['subaccounts'].items():
        acct = Account(
            name=name,
            owner=sub['owner'],
            broker='fidelity',
            taxable=sub['taxable'],
        )
        accounts[name] = acct

    return accounts

def _parse_num(num_str):
    if num_str == "n/a" or num_str == "--":
        return float('nan')
    else:
        return float(num_str.lstrip('$').replace(',', ''))

def _parse_pct(pct_str):
    return float(pct_str.rstrip('%')) / 100
