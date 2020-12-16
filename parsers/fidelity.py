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

    total_value = 0
    source_value = 0
    source_account_num = config["source_account"]

    for row in reader:
        try:
            acct_num = row["Account Name/Number"]
            try:
                acct_name = num_to_name[acct_num]
            except KeyError:
                raise KeyError("Unknown account number %s. Accounts are: %s" % (acct_num, num_to_name))
            acct = accounts[acct_name]

            symbol = row['Symbol']
            desc = row['Description']
            value = _parse_num(row['Current Value'])

            if desc == "BROKERAGELINK" or symbol == "CORE**": # UNFUNDED CORE POSITION
                continue

            total_value += value

            if acct_num == source_account_num:
                source_value += value
            elif symbol in INVESTABLE_SYMBOLS:
                acct.investable += value
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

    # Stripe's 401k plan has a weird rule where you have to leave at least 5% of the total
    # account value in the source account.
    min_source_value = total_value * config.get("min_source_allocation", 0.0)
    investable_source_value = source_value - min_source_value
    if investable_source_value < 0.0:
        raise ValueError("investable source value shouldn't be less than zero")
    elif investable_source_value > 0:
        acct_name = num_to_name[source_account_num]
        print("%s: $%0.2f available to transfer into Brokeragelink" % (acct_name, investable_source_value))
        accounts[acct_name].investable += investable_source_value

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
