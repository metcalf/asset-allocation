import re
import csv 
import datetime

from models import Account, Holding

INVESTABLE_SYMBOLS = ('IIAXX',)

def parse(contents, config, allow_after):
    accounts = _build_accounts(config)
    reader = csv.DictReader(contents.splitlines(), dialect=csv.excel_tab)
    
    for row in reader:
        _check_date(row['COB Date'], allow_after)

        nickname = row['Account Nickname']
        acct = accounts[nickname]

        symbol = row['Symbol']
        value = _parse_num(row['Value ($)'])

        if symbol in INVESTABLE_SYMBOLS:
            acct.investable += value
        else:
            holding = Holding(
                account=acct,
                symbol=row['Symbol'],
                quantity=_parse_num(row['Quantity']),
                value=value,
                basis=_parse_num(row['Cost Basis ($)'])
            )
            acct.holdings.append(holding)

    for account in accounts.values():
        if len(account.holdings) == 0:
            raise Exception("Did not find holdings for %s" % account.name)

    return accounts.values()

def _check_date(date_str, allow_after):
    date = datetime.datetime.strptime(date_str, '%m/%d/%Y')
    if date < allow_after:
        raise "Export is too old, got a row with date %s" % date_str

def _build_accounts(config):
    accounts = {}
    for name, sub in config['subaccounts'].items():
        acct = Account(
            name=name,
            owner=sub['owner'],
            broker='merrill',
            taxable=sub['taxable'],
            investable=sub.get('investable', 0)
        )
        accounts[name] = acct
    
    return accounts

def _parse_num(num_str):
    if num_str == "--":
        return float('nan')
    else:
        return float(num_str.replace(',', ''))