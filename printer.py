from collections import defaultdict

import tabulate

import analysis

def find_buyable_symbols(assets, cls, location, brokers):
    symbols = []
    for symbol, asset in assets.items():
        try:
            asset_brokers = asset["brokers"]
        except KeyError:
            raise KeyError("missing key 'brokers' for %s" % symbol)
        if (
            asset.get("location", location) == location and 
            asset["class"] == cls and 
            len(brokers.intersection(asset_brokers)) > 0
        ):
            symbols.append((asset.get("preference", 1), symbol))

    return [s[1] for s in sorted(symbols)]

def held_symbols_by_class(accts, assets):
    holdings = defaultdict(set)
    for acct in accts:
        for holding in acct.holdings:
            cls = assets[holding.symbol]["class"]
            holdings[cls].add(holding.symbol)

    return holdings

def print_investables(accts):
    rows = []
    for a in accts:
        rows.append((a.name, "$%d" % a.investable))
    
    headers = [
        "account", "investable"
    ]
    print(tabulate.tabulate(rows, headers=headers))


def print_results(
    current_allocations, new_allocations, taxable_accts, non_taxable_accts, classes, assets, targets
):
    curr_total = sum(current_allocations)
    new_total = sum(new_allocations)
    num_classes = len(classes)

    rows = []
    taxable_brokers = set(a.broker for a in taxable_accts)
    non_taxable_brokers = set(a.broker for a in non_taxable_accts)
    current_taxable_symbols = held_symbols_by_class(taxable_accts, assets)
    current_non_taxable_symbols = held_symbols_by_class(non_taxable_accts, assets)
    current_class_totals = analysis.sum_to_classes(current_allocations, num_classes)
    new_class_totals = analysis.sum_to_classes(new_allocations, num_classes)

    for i, c in enumerate(classes):
        curr = int(round(current_class_totals[i]))
        new = int(round(new_class_totals[i]))
        target = targets.get(c, 0)
        if curr == 0 and new == 0 and target == 0:
            continue

        curr_taxable = current_allocations[i]
        new_taxable = new_allocations[i]
        buy_taxable = int(new_taxable - curr_taxable)

        curr_non_taxable = current_allocations[num_classes + i]
        new_non_taxable = new_allocations[num_classes + i]
        buy_non_taxable = int(new_non_taxable - curr_non_taxable)

        buy_taxable_str = "$%d " % buy_taxable
        if buy_taxable > 0:
            symbols = find_buyable_symbols(assets, c, "taxable", taxable_brokers)
            buy_taxable_str += ",".join(symbols)
        elif buy_taxable < 0:
            symbols = current_taxable_symbols[c]
            buy_taxable_str += ",".join(symbols)

        buy_non_taxable_str = "$%d " % buy_non_taxable
        if buy_non_taxable > 0:
            symbols = find_buyable_symbols(assets, c, "non-taxable", non_taxable_brokers)
            buy_non_taxable_str += ",".join(symbols)
        elif buy_non_taxable < 0:
            symbols = current_non_taxable_symbols[c]
            buy_non_taxable_str += ",".join(symbols)

        row = [
            c,
            "%0.1f%%" % (curr / curr_total * 100),
            "%0.1f%%" % (new / new_total * 100),
            "%0.1f%%" % (target * 100),
            "$%d" % curr_taxable,
            "$%d" % new_taxable,
            buy_taxable_str,
            "$%d" % curr_non_taxable,
            "$%d" % new_non_taxable,
            buy_non_taxable_str,
        ]
        rows.append(row)
    
    headers = [
        "class", "total\ncurrent", "\nnew", "\ntarget",
        "taxable\ncurrent", "\nnew", "\nbuy",
        "non-taxable\ncurrent", "\nnew", "\nbuy",
    ]
    print(tabulate.tabulate(rows, headers=headers))