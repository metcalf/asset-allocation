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
        if inv:
            if account.investable > 0:
                raise Exception(
                    "Supplied an investable amount for account %s that already has %d investable" % (
                    account.name, account.investable
                ))
            else:
                account.investable = inv
        elif account.investable == 0:
            raise Exception("Did not find an investable amount for %s" % account.name)

    accounts_by_owner = defaultdict(list)
    for account in accounts:
        accounts_by_owner[account.owner].append(account)

    for owner, accts in accounts_by_owner.items():
        print("\nFor %s" % owner)
        run_for_owner(accts, input_data["classes"], input_data["assets"], input_data["targets"][owner])
        print("\n")

def run_for_owner(accts, classes, assets, targets):
    taxable_accts = [a for a in accts if a.taxable]
    non_taxable_accts = [a for a in accts if not a.taxable]

    current_allocations, new_allocations = analysis.optimize_allocations(
        taxable_accts=taxable_accts,
        non_taxable_accts=non_taxable_accts,
        classes=classes,
        assets=assets,
        targets=targets
    )
    
    printer.print_results(
        current_allocations=current_allocations,
        new_allocations=new_allocations,
        taxable_accts=taxable_accts,
        non_taxable_accts=non_taxable_accts,
        classes=classes,
        assets=assets,
        targets=targets
    )
    

if __name__== "__main__":
    main()