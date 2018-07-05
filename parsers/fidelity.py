import csv

import re
import csv 
import datetime

from models import Account, Holding

INVESTABLE_SYMBOLS = ("FDRXX**",)

def parse(contents, config, allow_after):
    accounts = _build_accounts(config)
    num_to_name = {}
    for name, nums in config["account_mapping"].items():
        for num in nums:
            num_to_name[num] = name

    sections = contents.split("\n\n")

    _check_date(sections.pop(), allow_after)

    section = sections.pop()
    if not section.startswith('"Brokerage services are provided'):
        raise Exception("Expected useless section, got: %s" % section)
    
    section = sections.pop()
    if not section.startswith('"The data and information in this spreadsheet'):
        raise Exception("Expected useless section, got: %s" % section)

    section = sections.pop()
    reader = csv.DictReader(section.splitlines())

    for row in reader:
        acct_num = row["Account Name/Number"]
        acct_name = num_to_name[acct_num]
        acct = accounts[acct_name]

        symbol = row['Symbol']
        value = _parse_num(row['Current Value'])

        if symbol == "BLNK":
            continue
        elif acct_num in config["investable"] or symbol in INVESTABLE_SYMBOLS:
            acct.investable += value
        else:
            holding = Holding(
                account=acct,
                symbol=row['Symbol'],
                quantity=_parse_num(row['Quantity']),
                value=value,
                basis=_parse_num(row['Cost Basis Total'])
            )
            acct.holdings.append(holding)

    for account in accounts.values():
        if len(account.holdings) == 0:
            raise Exception("Did not find holdings for %s" % account.name)

    return accounts.values()

def _check_date(date_str, allow_after):
    date = datetime.datetime.strptime(date_str, '"Date downloaded %m/%d/%Y %H:%M %p",')
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
    if num_str == "n/a":
        return float('nan')
    else:   
        return float(num_str.lstrip('$'))