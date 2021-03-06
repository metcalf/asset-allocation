from collections import defaultdict
import copy

import scipy.optimize
import numpy as np

ALLOCATION_OPTIMALITY_THRESHOLD = 0.5
LOCATION_OPTIMALITY_THRESHOLD = 50

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

def class_vector(class_names, asset_defns, accounts, filter=None):
    allocations = accounts_to_allocations(accounts, asset_defns, filter=filter)
    return [allocations[c] for c in class_names]

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

def optimize_locations(allocations, class_names, classes, bounds, current_allocations):
    constraints = []
    num_classes = len(class_names)

    taxable_allocations = allocations[:num_classes]
    class_totals = sum_to_classes(allocations, num_classes)

    taxable_bounds = []
    for i, class_total in enumerate(class_totals):
        t_min, t_max = bounds[i]
        nt_min, nt_max = bounds[num_classes + i]

        taxable_bounds.append((
            max(t_min, class_total - nt_max),
            min(t_max, class_total - nt_min),
        ))

    # Account total doesn't change
    total = sum(allocations)
    taxable_total = sum(taxable_allocations)
    constraints = [scipy.optimize.LinearConstraint(
        [1] * num_classes,
        taxable_total, taxable_total
    )]

    non_taxable_preference = [0] * num_classes
    for i, c in enumerate(class_names):
        pref = classes[c].get("non_taxable_preference", None)
        if pref is None:
            continue

        total_for_class = class_totals[i]
        if abs(total_for_class) < 1:
            continue

        # TODO: This actual choice of value isn't super well thought out
        non_taxable_preference[i] = total * pref / total_for_class

    best_soln = run_location_optimization(taxable_allocations, non_taxable_preference, constraints, taxable_bounds)
    check_result(best_soln, LOCATION_OPTIMALITY_THRESHOLD)

    allocations = allocations_from_taxables(class_totals, best_soln.x)

    unattempted = set(range(len(allocations)))
    while len(unattempted) > 0:
        # Smallest absolute negative, then smallest postive
        # The idea is we want to first remove cases where we sell in one accout
        # just to buy in another and then remove as many more transactions as possible
        # which is probably easier for smaller values
        keyed = [(allocations[i] > 0, abs(allocations[i]), i) for i in unattempted]
        i = sorted(keyed)[0][-1]
        unattempted.remove(i)

        class_idx = i % num_classes

        # There's nothing in this class anyway
        if class_totals[class_idx] < 1:
            continue

        if i < num_classes:
            new_bound = current_allocations[i]
        else:
            new_bound = class_totals[class_idx] - current_allocations[i]

        # Check to make sure the new bound doesn't violate the old bounds
        old_bound = taxable_bounds[class_idx]
        if old_bound[0] > new_bound or old_bound[1] < new_bound:
            continue

        # We're already constrained to the current allocation
        if old_bound[0] == new_bound and old_bound[1] == new_bound:
            continue

        new_bounds = taxable_bounds.copy()
        new_bounds[class_idx] = (new_bound, new_bound)

        curr_soln = run_location_optimization(best_soln.x, non_taxable_preference, constraints, new_bounds)
        if (curr_soln.fun - best_soln.fun) < 0.01 and (curr_soln.constr_violation - best_soln.constr_violation) < 0.01:
            best_soln = curr_soln
            taxable_bounds = new_bounds
            allocations = allocations_from_taxables(class_totals, best_soln.x)
            print("+", end="", flush=True)
        else:
            print(".", end="", flush=True)
    print("")

    return allocations_from_taxables(class_totals, best_soln.x)

def check_result(soln, threshold):
    if abs(soln.optimality) > threshold:
        raise Exception("Expected optimality <<%f, got %f" % (threshold, soln.optimality))

    if soln.constr_violation > 0.1:
        raise Exception("Expected constr_violation <<0.1, got %f" % soln.constr_violation)


def run_optimization(current_allocations, target_allocations_vector, constraints, bounds):
    soln = scipy.optimize.minimize(
        objective,
        current_allocations,
        args=(target_allocations_vector,),
        jac='3-point', # TODO: `gradient
        hess=scipy.optimize.BFGS(), # TODO: Pretty sure I can provide this
        method='trust-constr',
        bounds=bounds,
        constraints=constraints,
        options={"maxiter": 5000},
    )

    return soln

def run_location_optimization(taxable_allocations, non_taxable_preference, constraints, bounds):
    soln = scipy.optimize.minimize(
        location_objective,
        taxable_allocations,
        args=(non_taxable_preference,),
        jac=lambda x, pref: pref,
        hess=lambda x, _: np.zeros((len(x), len(x))),
        method='trust-constr',
        constraints=constraints,
        bounds=bounds,
        options={"maxiter": 5000},
    )

    return soln

def allocations_from_taxables(class_totals, taxable_allocations):
    new_non_taxable = [class_totals[i] - taxable_allocations[i] for i in range(len(class_totals))]
    allocations = np.concatenate((taxable_allocations, new_non_taxable))

    return [v if v > 0.001 else 0.0 for v in allocations]

def minimize_moves(best_soln, current_allocations, target_allocations_vector, num_classes, constraints, bounds):
    for i, v in enumerate(best_soln.x):
        if (v - current_allocations[i]) >= 0:
            continue
        if current_allocations[i] == 0 and (target_allocations_vector[i % num_classes]) == 0:
            continue

        new_bounds = bounds.copy()
        new_bounds[i] = (current_allocations[i], current_allocations[i])

        curr_soln = run_optimization(current_allocations, target_allocations_vector, constraints, new_bounds)
        if (curr_soln.fun - best_soln.fun) < 0.1:
            best_soln = curr_soln
            bounds = new_bounds
            print("+", end="", flush=True)
        else:
            print(".", end="", flush=True)
    print("")
    return best_soln


def optimize_allocations(taxable_accts, non_taxable_accts, classes, assets, targets, no_sell_holdings, allow_gains):
    class_names = list(classes)
    num_classes = len(class_names)

    current_taxable_allocations = class_vector(class_names, assets, taxable_accts)
    current_non_taxable_allocations = class_vector(class_names, assets, non_taxable_accts)

    # Negative value holdings represent unsettled sales so should always be in the sum
    # TODO: What we really want is to net the negative amounts of a given holding out against the positives
    # and then filter on what remains
    min_taxable_allocations = class_vector(
        class_names, assets, taxable_accts,
        filter=lambda acct, hldg: hldg.value < 0 or hldg.symbol in no_sell_holdings[acct.name] or (hldg.value > hldg.basis and not allow_gains)
    )
    min_non_taxable_allocations = class_vector(
        class_names, assets, non_taxable_accts,
        filter=lambda acct, hldg: hldg.value < 0 or hldg.symbol in no_sell_holdings[acct.name]
    )

    taxable_investable = sum(a.investable for a in taxable_accts)
    non_taxable_investable = sum(a.investable for a in non_taxable_accts)

    taxable_total = sum(current_taxable_allocations) + taxable_investable
    non_taxable_total = sum(current_non_taxable_allocations) + non_taxable_investable
    total = taxable_total + non_taxable_total

    target_allocations_vector = [targets.get(c, 0) * total for c in class_names]

    allowed_in_taxable = find_allowed_classes(assets, "taxable")
    allowed_in_non_taxable = find_allowed_classes(assets, "non-taxable")

    bounds = []

    # Taxable asset limits
    for i in range(num_classes):
        arr = [0] * (2 * num_classes)
        arr[i] = 1

        min_lim = min_taxable_allocations[i]
        if class_names[i] in allowed_in_taxable:
            max_lim = max(min_lim, target_allocations_vector[i])
        else:
            max_lim = min_lim

        bounds.append((min_lim, max_lim))

    # Non-taxable asset limits
    for i in range(num_classes):
        arr = [0] * (2 * num_classes)
        arr[num_classes + i] = 1

        min_lim = min_non_taxable_allocations[i]
        if class_names[i] in allowed_in_non_taxable:
            max_lim = max(min_lim, target_allocations_vector[i])
        else:
            max_lim = min_lim

        bounds.append((min_lim, max_lim))

    constraints = [
        # Taxable account total
        scipy.optimize.LinearConstraint(
            [1] * num_classes + [0] * num_classes,
            taxable_total, taxable_total
        ),

        # Non-taxable account total
        scipy.optimize.LinearConstraint(
            [0] * num_classes + [1] * num_classes,
            non_taxable_total, non_taxable_total
        ),
    ]


    current_allocations = current_taxable_allocations + current_non_taxable_allocations

    best_soln = run_optimization(current_allocations, target_allocations_vector, constraints, bounds)
    check_result(best_soln, ALLOCATION_OPTIMALITY_THRESHOLD)

    # Attempt to avoid cases where we sell an asset only to buy in another account
    # best_soln = minimize_moves(
    #     best_soln, current_allocations, target_allocations_vector, num_classes, constraints, bounds
    # )

    allocations = optimize_locations(best_soln.x, class_names, classes, bounds,  current_allocations)

    unspent = sum(allocations) - total
    if unspent > 1:
         raise Exception("Solution didn't spend $%0.2f!" % unspent)
    if unspent < -1:
         raise Exception("Solution overspent $%0.2f!" % unspent)

    return (current_allocations, allocations)
