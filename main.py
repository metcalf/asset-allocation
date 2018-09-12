import datetime
import os.path
import argparse
from collections import defaultdict

import parsers
import analysis
import printer

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('config_path')
    parser.add_argument('--investable', action='append', default=[],
                        help='investable amount for an account in the form NAME=AMT')
    parser.add_argument('--max-age', default=7, type=int,
                        help='maximum age of input data files')
    parser.add_argument('--no-sell', action='append', default=[],
                        help='do not sell assets from these accounts:holdings')
    parser.add_argument('--allow-gains', action='store_true',
                        help='allow selling assets that would incur capital gains')
    args = parser.parse_args()

    input_data = parsers.read_config(args.config_path)
    
    investable_overrides = {}
    for inv_str in args.investable:
        name, value = inv_str.split("=", 2)
        investable_overrides[name] = float(value)

    allow_after = datetime.datetime.now() - datetime.timedelta(days=args.max_age)
    accounts = parsers.read_accounts(os.path.dirname(args.config_path), input_data["accounts"], allow_after)

    for account in accounts:
        inv = investable_overrides.get(account.name, None)
        if inv is not None:
            if account.investable > 0:
                warn(
                    "Supplied an investable amount for account %s that already has %d investable" % (
                    account.name, account.investable
                ))
            account.investable = inv
        elif account.investable == 0:
            raise Exception("Did not find an investable amount for %s" % account.name)

        if len(account.holdings) == 0:
            warn("Did not find holdings for %s" % account.name)

    accounts_by_name = dict((a.name, a) for a in accounts)

    no_sell_holdings = defaultdict(set)
    
    for arg in args.no_sell:
        parts = arg.split(":", 2)
        acct = accounts_by_name[parts[0]]
        if len(parts) == 1:
            for holding in acct.holdings:
                no_sell_holdings[acct.name].add(holding.symbol)
        else:
            symbols = parts[1].split(",")
            for symbol in symbols:
                no_sell_holdings[acct.name].add(symbol)
    
    accounts_by_owner = defaultdict(list)
    for account in accounts:
        accounts_by_owner[account.owner].append(account)

    for owner, accts in accounts_by_owner.items():
        print("\nFor %s" % owner)
        run_for_owner(
            accts=accts, 
            classes=input_data["classes"], 
            assets=input_data["assets"], 
            targets=input_data["targets"][owner],
            no_sell_holdings=no_sell_holdings,
            allow_gains=args.allow_gains
        )
        print("\n")

def run_for_owner(accts, classes, assets, targets, no_sell_holdings, allow_gains):
    taxable_accts = [a for a in accts if a.taxable]
    non_taxable_accts = [a for a in accts if not a.taxable]

    current_allocations, new_allocations = analysis.optimize_allocations(
        taxable_accts=taxable_accts,
        non_taxable_accts=non_taxable_accts,
        classes=classes,
        assets=assets,
        targets=targets,
        no_sell_holdings=no_sell_holdings,
        allow_gains=allow_gains
    )
    
    printer.print_investables(accts)
    printer.print_results(
        current_allocations=current_allocations,
        new_allocations=new_allocations,
        taxable_accts=taxable_accts,
        non_taxable_accts=non_taxable_accts,
        classes=classes,
        assets=assets,
        targets=targets
    )

def warn(text):
    print("\033[0;31mWARNING:\033[0m %s" % text)

if __name__== "__main__":
    main()