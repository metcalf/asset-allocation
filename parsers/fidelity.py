import csv

import codecs
import re
import csv
import datetime

from models import Account, Holding

INVESTABLE_SYMBOLS = ("FDRXX**",)

def read(path):
    with codecs.open(path, encoding="utf-8-sig") as f:
        return f.read()

def parse(contents, config, allow_after):
    accounts = _build_accounts(config)
    num_to_name = {}
    for name, nums in config["account_mapping"].items():
        for num in nums:
            num_to_name[num] = name

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
            acct_num = row["Account Name/Number"]
            try:
                acct_name = num_to_name[acct_num]
            except KeyError:
                raise KeyError("Unknown account number %s. Accounts are: %s" % (acct_num, num_to_name))
            acct = accounts[acct_name]

            symbol = row['Symbol']

            if symbol == "BLNK" or symbol == "CORE**": # BrokerageLink and UNFUNDED CORE POSITION
                continue
            elif acct_num in config["investable"] or symbol in INVESTABLE_SYMBOLS:
                acct.investable += _parse_num(row['Current Value'])
            else:
                holding = Holding(
                    account=acct,
                    symbol=row['Symbol'],
                    quantity=_parse_num(row['Quantity']),
                    price=_parse_num(row['Last Price']),
                    unit_cost=_parse_num(row['Cost Basis Per Share'])
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
    for name in config['account_mapping'].keys():
        acct = Account(
            name=name,
            owner=config['owner'],
            broker='fidelity',
            taxable=False,
        )
        accounts[name] = acct

    return accounts

def _parse_num(num_str):
    if num_str == "n/a" or num_str == "--":
        return float('nan')
    else:
        return float(num_str.lstrip('$').replace(',', ''))
