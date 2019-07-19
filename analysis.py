from collections import defaultdict
import copy

import scipy.optimize
import numpy as np

def accounts_to_allocations(accounts, asset_config, filter=None):
    allocations = defaultdict(float)
    for account in accounts:
        for holding in account.holdings:
            if filter is not None and not filter(account, holding):
                continue

            asset_class = asset_config[holding.symbol]["class"]
            allocations[asset_class] += holding.value
        allocations['investable'] += account.investable

    return allocations

def class_vector(classes, asset_defns, accounts, filter=None):
    allocations = accounts_to_allocations(accounts, asset_defns, filter=filter)
    return [allocations[c] for c in classes]

def find_allowed_classes(assets, location):
    allowed = set()
    for asset in assets.values():
        if asset.get("location", location) == location:
            allowed.add(asset["class"])

    return allowed

def sum_to_classes(allocations, num_classes):
    per_class = [0] * num_classes
    for i, a in enumerate(allocations):
        per_class[i % num_classes] += a
    return per_class

def objective(allocations, targets):
    if len(allocations) % len(targets) != 0:
        raise Exception(
            "Allocation variable vector (%d) is not a multiple of the length of targets (%d)" %(
                len(allocations), len(targets)
            )
        )

    # Sum of the squares of the differences
    per_class = sum_to_classes(allocations, len(targets))
    return sum((t - a) ** 2 for t, a in zip(targets, per_class))

def location_objective(taxable_allocations, non_taxable_preference):
    return sum(taxable_allocations[i] * pref for i, pref in enumerate(non_taxable_preference))

def optimize_locations(allocations, classes, min_taxable_allocations, allowed_in_taxable):
    constraints = []
    num_classes = len(classes)

    taxable_allocations = allocations[:num_classes]

    # Account total doesn't change
    taxable_total = sum(taxable_allocations)
    constraints.append(scipy.optimize.LinearConstraint(
        [1] * num_classes,
        taxable_total, taxable_total
    ))

    class_totals = sum_to_classes(allocations, num_classes)

    non_taxable_preference = [0] * num_classes
    for i, c in enumerate(classes):
        arr = [0] * num_classes
        arr[i] = 1

        total_for_class = class_totals[i]

        # TODO: dedupe
        min_lim = min_taxable_allocations[i]
        if c in allowed_in_taxable:
            max_lim = max(min_lim, total_for_class)
        else:
            max_lim = min_lim

        constraints.append(scipy.optimize.LinearConstraint(
            arr, min_lim, max_lim
        ))

        if abs(total_for_class) < 1:
            continue

        if "bond" in c:
            # We much prefer diversified bonds in non-taxable accounts over municipal bonds
            # in taxable accounts.
            pref = 1000
        else:
            pref = 0
        non_taxable_preference[i] = pref / total_for_class

    soln = scipy.optimize.minimize(
        location_objective,
        taxable_allocations,
        args=(non_taxable_preference,),
        jac=lambda x, pref: pref,
        hess=lambda x, _: np.zeros((len(x), len(x))),
        method='trust-constr',
        constraints=constraints,
        options={"maxiter": 5000},
    )

    if abs(soln.optimality) > 1:
        raise Exception("Expected optimality <<1, got %f" % soln.optimality)

    new_non_taxable = [class_totals[i] - soln.x[i] for i in range(num_classes)]
    new_allocations = np.concatenate((soln.x, new_non_taxable))

    return new_allocations


def run_optimization(current_allocations, target_allocations_vector, constraints):
    return scipy.optimize.minimize(
        objective,
        current_allocations,
        args=(target_allocations_vector,),
        jac='3-point', # TODO: `gradient
        hess=scipy.optimize.BFGS(), # TODO: Pretty sure I can provide this
        method='trust-constr',
        constraints=constraints,
        options={"maxiter": 5000},
    )


def optimize_allocations(taxable_accts, non_taxable_accts, classes, assets, targets, no_sell_holdings, allow_gains):
    num_classes = len(classes)

    current_taxable_allocations = class_vector(classes, assets, taxable_accts)
    current_non_taxable_allocations = class_vector(classes, assets, non_taxable_accts)

    # Negative value holdings represent unsettled sales so should always be in the sum
    # TODO: What we really want is to net the negative amounts of a given holding out against the positives
    # and then filter on what remains
    min_taxable_allocations = class_vector(
        classes, assets, taxable_accts,
        filter=lambda acct, hldg: hldg.value < 0 or hldg.symbol in no_sell_holdings[acct.name] or (hldg.value > hldg.basis and not allow_gains)
    )
    min_non_taxable_allocations = class_vector(
        classes, assets, non_taxable_accts,
        filter=lambda acct, hldg: hldg.value < 0 or hldg.symbol in no_sell_holdings[acct.name]
    )

    taxable_investable = sum(a.investable for a in taxable_accts)
    non_taxable_investable = sum(a.investable for a in non_taxable_accts)

    taxable_total = sum(current_taxable_allocations) + taxable_investable
    non_taxable_total = sum(current_non_taxable_allocations) + non_taxable_investable
    total = taxable_total + non_taxable_total

    target_allocations_vector = [targets.get(c, 0) * total for c in classes]

    allowed_in_taxable = find_allowed_classes(assets, "taxable")
    allowed_in_non_taxable = find_allowed_classes(assets, "non-taxable")

    # US bonds are weird because municipal bonds are tax efficient but other bonds are not.
    # If we can satisfy our allocations without municipal bonds, then exclude them.
    total_only_in_taxable = 0
    for i, c in enumerate(classes):
        if c in allowed_in_non_taxable and c not in allowed_in_taxable:
            total_only_in_taxable += target_allocations_vector[i]
    if total_only_in_taxable + target_allocations_vector[classes.index("US bond")] <= non_taxable_total:
        allowed_in_taxable.remove("US bond")

    constraints = []

    # Taxable account total
    constraints.append(scipy.optimize.LinearConstraint(
        [1] * num_classes + [0] * num_classes,
        taxable_total, taxable_total
    ))
    # Non-taxable account total
    constraints.append(scipy.optimize.LinearConstraint(
        [0] * num_classes + [1] * num_classes,
        non_taxable_total, non_taxable_total
    ))

    # Taxable asset limits
    for i in range(num_classes):
        arr = [0] * (2 * num_classes)
        arr[i] = 1

        min_lim = min_taxable_allocations[i]
        if classes[i] in allowed_in_taxable:
            max_lim = max(min_lim, target_allocations_vector[i])
        else:
            max_lim = min_lim

        constraints.append(scipy.optimize.LinearConstraint(
            arr, min_lim, max_lim
        ))

    # Non-taxable asset limits
    for i in range(num_classes):
        arr = [0] * (2 * num_classes)
        arr[num_classes + i] = 1

        min_lim = min_non_taxable_allocations[i]
        if classes[i] in allowed_in_non_taxable:
            max_lim = max(min_lim, target_allocations_vector[i])
        else:
            max_lim = min_lim

        constraints.append(scipy.optimize.LinearConstraint(
            arr, min_lim, max_lim
        ))

    current_allocations = current_taxable_allocations + current_non_taxable_allocations

    best_soln = run_optimization(current_allocations, target_allocations_vector, constraints)

    # Attempt to avoid cases where we sell an asset only to buy in another account
    for i, v in enumerate(best_soln.x):
        if (v - current_allocations[i]) >= 0:
            continue
        if current_allocations[i] == 0 and (target_allocations_vector[i % num_classes]) == 0:
            continue

        arr = [0] * (2 * num_classes)
        arr[i] = 1
        new_constraints = constraints + [
            scipy.optimize.LinearConstraint(
                arr, current_allocations[i], current_allocations[i],
            ),

        ]
        curr_soln = run_optimization(current_allocations, target_allocations_vector, new_constraints)
        if (curr_soln.fun - best_soln.fun) < 0.1:
            best_soln = curr_soln
            constraints = new_constraints
            print("+", end="", flush=True)
        else:
            print(".", end="", flush=True)

    print("")

    if abs(best_soln.optimality) > 1:
        raise Exception("Expected optimality <<1, got %f" % best_soln.optimality)
    allocations = best_soln.x

    unspent = sum(allocations) - total
    if unspent > 1:
         raise Exception("Solution didn't spend $%0.2f!" % unspent)
    if unspent < -1:
         raise Exception("Solution overspent $%0.2f!" % unspent)

    return (current_allocations, allocations)
