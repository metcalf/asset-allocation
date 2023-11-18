import datetime
import os.path
import argparse
from collections import defaultdict

import parsers
import tabulate

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('config_path')
    parser.add_argument('--max-age', default=7, type=int,
                        help='maximum age of input data files')
    args = parser.parse_args()

    input_data = parsers.read_config(args.config_path)

    allow_after = datetime.datetime.now() - datetime.timedelta(days=args.max_age)
    accounts = parsers.read_accounts(os.path.dirname(args.config_path), input_data["accounts"], allow_after)

    all_symbols = input_data["assets"].keys()
    for account in accounts:
        if len(account.holdings) == 0:
            warn(f"Did not find holdings for {account.name}")

        for holding in account.holdings:
            if not holding.is_bond and holding.symbol not in all_symbols:
                warn(f"Unknown '{holding.symbol}' in {account.name}")

    cash_symbols = [k for k, v in input_data["assets"].items() if v["class"] == "Cash"]

    accounts_by_name = dict((a.name, a) for a in accounts)
    accounts_by_owner = defaultdict(list)
    for account in accounts:
        accounts_by_owner[account.owner].append(account)

    joint_categories = find_allocations_by_category(accounts_by_owner['joint'], input_data['classes'], input_data["assets"])
    # Joint bonds are for cash management and not considered in allocation
    # Cash is handled separately as well
    del joint_categories['Bond']
    del joint_categories['Cash']

    print_header("JOINT DATA")
    print_data_output(
        accounts_by_owner['joint'],
        cash_symbols,
        joint_categories
    )

    print_header("JOINT ALLOCATIONS")

    def by_class_for_category(category):
        def by_class(holding):
            if holding.is_bond:
                return None
            asset_class = input_data["assets"][holding.symbol]['class']
            if input_data['classes'][asset_class]['category'] == category:
                return asset_class

        return by_class

    print_allocations_by_category(
        find_allocations_by(accounts, by_class_for_category("Bond Fund"))
    )
    print()
    print_allocations_by_category(
        find_allocations_by(accounts, by_class_for_category("Equity Fund"))
    )

    print_header("ANDREW ALLOCATIONS")
    print_allocations_by_category(
        find_allocations_by_category(
            accounts_by_owner['andrew'], input_data['classes'], input_data["assets"]
        )
    )

def print_header(text):
     print()
     print(f"====== {text} ======")

def print_data_output(accounts, cash_symbols, amounts_by_category):
    bonds = []
    for account in accounts:
        bonds += [h for h in account.holdings if h.is_bond]

    income = 0
    cash = 0
    taxable = 0
    nontaxable = 0

    for account in accounts:
        for holding in account.holdings:
            if holding.is_bond:
                continue

            if account.taxable:
                income += holding.annual_income
                if holding.symbol in cash_symbols:
                    cash += holding.value
                else:
                    taxable += holding.value
            else:
                nontaxable += holding.value

    if len(amounts_by_category.keys()) != 3:
        raise f"Expected 3 categories need to update spreadsheet rows first: {amounts_by_category.keys()}"

    print(f"Fidelity taxable annual income,{income:0.2f}")
    print(f"Fidelity taxable cash value,{cash:0.2f}")
    print(f"Fidelity taxable non-cash value,{taxable:0.2f}")
    print(f"Fidelity non-taxable value,{nontaxable:0.2f}")
    print(f"Fidelity equity fund value,{amounts_by_category['Equity Fund']:0.2f}")
    print(f"Fidelity bond fund value,{amounts_by_category['Bond Fund']:0.2f}")
    print(f"Fidelity reit value,{amounts_by_category['Real Estate']:0.2f}")
    print("")
    print("CUSIP,Par Value,Current Value,Annual Income,Maturity")
    bonds.sort(key=lambda bond: bond.maturity_date)
    for bond in bonds:
        print(f"{bond.symbol},{bond.quantity:0.2f},{bond.value:0.2f},{bond.annual_income:0.2f},{bond.maturity_date.strftime('%m/%d/%Y')}")

def find_allocations_by(accounts, by):
    categories = defaultdict(lambda: 0)
    for account in accounts:
        for holding in account.holdings:
            category = by(holding)

            if category is not None:
                categories[category] += holding.value

    return categories

def find_allocations_by_category(accounts, classes, assets):
    def by_category(holding):
        if holding.is_bond:
            return 'Bond'
        else:
            return classes[assets[holding.symbol]['class']]['category']

    return find_allocations_by(accounts, by_category)

def print_allocations_by_category(categories, name='category'):
    total = sum(v for v in categories.values())

    rows = []
    for category, amt in categories.items():
        rows.append([
            category,
            f"${amt:,.0f}",
            f"{(amt / total * 100):0.1f}%"
        ])

    headers = [name, 'amount', 'percent']

    print(tabulate.tabulate(rows, headers=headers))


def warn(text):
    print(f"\033[0;31mWARNING:\033[0m {text}")

if __name__== "__main__":
    main()
