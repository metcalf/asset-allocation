parsers/fidelity.pyimport csv

import codecs
import re
import csv
import datetime

from models import Account, Holding

EXPECT_ACCTS_STRING = 'Positions: All Accounts'

BOND_CUSIP_RE = re.compile(r"[A-Z0-9]{6}([A-Z]{2}|[A-Z]\d|\d[A-Z])\d")
BOND_DESC_RE = re.compile(r"(\d{1,2}\.\d{5}%) (\d{2}/\d{2}/\d{4})")

def read(path):
    with codecs.open(path, encoding="utf-8-sig") as f:
        return f.read()

def parse(contents, config, allow_after):
    accounts = _build_accounts(config)

    lines = contents.split("\n")

    if lines[0] != EXPECT_ACCTS_STRING:
        raise Exception("Expected '%s', got: %s" % (EXPECT_ACCTS_STRING, lines[0]))

    _check_date(lines[1], allow_after)

    if len(lines[2]) > 0:
        raise Exception("Expected empty 3rd line, got: %s" % lines[2])

    reader = csv.DictReader(lines[3:])

    for row in reader:
        try:
            acct_name = row["Account Name"]
            acct = accounts[acct_name]

            symbol = row['Symbol']

            if symbol.endswith("**"):
                symbol = symbol.rstrip("**")
                # Money market core positions don't get price and quantity in this export
                # so we assume price is always $1 and derive quantity from value
                quantity = _parse_num(row['Current Value'])
                price = 1.0
                yield_rate = _parse_pct(row['Yield'])
                maturity_date = None
            else:
                quantity = _parse_num(row['Quantity'])

                if BOND_CUSIP_RE.match(symbol):
                    price = _parse_num(row['Current Value']) / quantity
                    desc = row['Description']
                    match = BOND_DESC_RE.search(desc)
                    yield_rate = _parse_pct(match[1])

                    print(match[2].split("/"))
                    (month, day, year) = match[2].split("/")
                    maturity_date = datetime.date(int(year), int(month), int(day))
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
