import codecs
import csv
import datetime
import requests
import re
from collections import defaultdict

from models import Account, Holding

YIELD_REX = re.compile(r'data-test="(?:TD|7_DAY)_YIELD-value">(\d+\.\d+)%</td>')

def read(path):
    with codecs.open(path, encoding="utf-8") as f:
        return f.read()

def parse(contents, config, allow_after):
    accounts = _build_accounts(config)
    reader = csv.DictReader(contents.splitlines(), dialect=csv.excel_tab)

    for row in reader:
        _check_date(row.get('COB Date') or row['Date'], allow_after)

        nickname = row['Account Nickname']
        acct = accounts[nickname]

        symbol = row['Symbol']
        quantity = _parse_num(row['Quantity'])
        price = _parse_num(row['Price ($)'])

        # NB: If we switch to margin account this is handled differently
        if symbol == "--":
            symbol = "MLSWEEP"
            annual_income = 0 # Barely pays any interest and should be a small allocation
        else:
            yld = _query_yield(symbol)
            print(f"Yield {symbol}={yld*100}%")
            annual_income = yld * _parse_num(row['Value ($)'])

        holding = Holding(
            account=acct,
            symbol=symbol,
            quantity=quantity,
            price=price,
            annual_income=annual_income,
            maturity_date=None
        )
        acct.holdings.append(holding)


    return accounts.values()

def _query_yield(symbol):
    url = f'https://finance.yahoo.com/quote/{symbol}/'
    resp = requests.get(url, headers={"User-Agent": "Mozilla/5.0"})
    resp.raise_for_status()

    match = YIELD_REX.search(resp.text)

    if match is None:
        raise f"Unable to find yield text at {url}"

    return float(match[1]) / 100

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
