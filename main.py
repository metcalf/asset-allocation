import datetime
import os.path
import argparse
from collections import defaultdict

import parsers
import printer

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('config_path')
    parser.add_argument('--max-age', default=7, type=int,
                        help='maximum age of input data files')
    args = parser.parse_args()

    input_data = parsers.read_config(args.config_path)

    allow_after = datetime.datetime.now() - datetime.timedelta(days=args.max_age)
    accounts = parsers.read_accounts(os.path.dirname(args.config_path), input_data["accounts"], allow_after)

    for account in accounts:
        if len(account.holdings) == 0:
            warn("Did not find holdings for %s" % account.name)

    accounts_by_name = dict((a.name, a) for a in accounts)
    accounts_by_owner = defaultdict(list)
    for account in accounts:
        accounts_by_owner[account.owner].append(account)

    for owner, accts in accounts_by_owner.items():
        print("\nFor %s" % owner)

def warn(text):
    print("\033[0;31mWARNING:\033[0m %s" % text)

if __name__== "__main__":
    main()
