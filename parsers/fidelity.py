import csv

import codecs
import re
import csv
import datetime
import math

from models import Account, Holding

BOND_CUSIP_RE = re.compile(r"[A-Z0-9]{6}([A-Z]{2}|[A-Z]\d|\d[A-Z])\d")
BOND_DESC_RE = re.compile(r"(\d{1,2}\.\d{5}%) (\d{2}/\d{2}/\d{4})")

def read(path):
    with codecs.open(path, encoding="utf-8-sig") as f:
        return f.read()

def parse(contents, config, allow_after):
    ignore_accounts = config.get("ignore_accounts", [])
    accounts = _build_accounts(config)

    sections = contents.split("\r\n\r\n")

    _check_date(sections.pop().strip(), allow_after)

    section = sections.pop()
    if not section.startswith('"Brokerage services are provided'):
        raise Exception(f"Expected useless section, got: {section}")

    section = sections.pop()
    if not section.startswith('"The data and information in this spreadsheet'):
        raise Exception(f"Expected useless section, got: {section}")

    section = sections.pop()
    reader = csv.DictReader(section.splitlines())

    for row in reader:
        try:
            acct_name = f"{row['Account Name']} ({row['Account Number']})"
            if acct_name in ignore_accounts:
                continue

            acct = accounts[acct_name]

            symbol = row['Symbol']

            if symbol.endswith("**"):
                symbol = symbol.rstrip("**")
                # Money market core positions don't get price and quantity in this export
                # so we assume price is always $1 and derive quantity from value
                quantity = _parse_num(row['Current Value'])
                price = 1.0
                if symbol == "CORE":
                    # NB: The CORE** position in the Fidelity Cash Management account does
                    # not report a yield but we just ignore it because it should be
                    # immaterial.
                    annual_income = 0
                else:
                    annual_income = _parse_pct(row['Yield']) * quantity
                maturity_date = None
            else:
                quantity = _parse_num(row['Quantity'])

                if BOND_CUSIP_RE.match(symbol):
                    price = _parse_num(row['Current Value']) / quantity
                    desc = row['Description']
                    match = BOND_DESC_RE.search(desc)
                    # Coupon * dollars at par
                    annual_income = _parse_pct(match[1]) * quantity

                    (month, day, year) = match[2].split("/")
                    maturity_date = datetime.date(int(year), int(month), int(day))
                else:
                    price = _parse_num(row['Last Price'])
                    annual_income = _parse_num(row['Est. Annual Income'])
                    if math.isnan(annual_income):
                        annual_income = _parse_pct(row['Yield']) * _parse_num(row['Current Value'])
                    maturity_date = None

            holding = Holding(
                account=acct,
                symbol=symbol,
                quantity=quantity,
                price=price,
                annual_income=annual_income,
                maturity_date=maturity_date
            )
            acct.holdings.append(holding)
        except ValueError as e:
            raise ValueError(f"{e} (in {row})")

    return accounts.values()

def _check_date(date_str, allow_after):
    date = datetime.datetime.strptime(date_str, '"Date downloaded %m/%d/%Y %H:%M %p ET"')
    if date < allow_after:
        raise Exception(f"Export is too old, got a row with date {date_str}")

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
