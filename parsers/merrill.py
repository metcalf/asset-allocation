import re
import csv 
import datetime
from collections import defaultdict

from models import Account, Holding

INVESTABLE_SYMBOLS = ('IIAXX',)

def parse(contents, config, allow_after):
    accounts = _build_accounts(config)
    reader = csv.DictReader(contents.splitlines(), dialect=csv.excel_tab)
    
    # Account, symbol, shares
    executed_sales = defaultdict(lambda: defaultdict(int))

    for row in reader:
        _check_date(row.get('COB Date') or row['Date'], allow_after)

        nickname = row['Account Nickname']
        acct = accounts[nickname]

        symbol = row['Symbol']
        value = _parse_num(row['Value ($)'])
        quantity = _parse_num(row['Quantity'])

        if symbol in INVESTABLE_SYMBOLS:
            acct.investable += value
        elif row['Short/Long'] == ' Executed Sell':
            assert quantity < 0, "Sell quantities should be negative"
            executed_sales[acct][symbol] += -quantity
        else:
            holding = Holding(
                account=acct,
                symbol=symbol,
                quantity=quantity,
                price=value / quantity,
                unit_cost=_parse_num(row['Unit Cost ($)'])
            )
            acct.holdings.append(holding)

    for acct, symbols in executed_sales.items():
        for symbol, to_sell in symbols.items():
            holdings = [h for h in acct.holdings if h.symbol == symbol]
            holdings.sort(key=lambda h: h.unit_cost)

            while to_sell > 0:
                holding = holdings.pop(0)
                sell = min(holding.quantity, to_sell)
                holding.quantity -= sell
                to_sell -= sell

    return accounts.values()

def _check_date(date_str, allow_after):
    date = datetime.datetime.strptime(date_str, '%m/%d/%Y')
    if date < allow_after:
        raise Exception("Export is too old, got a row with date %s" % date_str)

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
    if num_str.startswith('(') and num_str.endswith(')'):
        num_str = num_str[1:-1]
        sign = -1
    else:
        sign = 1

    if num_str == "--":
        amt = float('nan')
    else:
        amt = float(num_str.replace(',', ''))

    return amt * sign