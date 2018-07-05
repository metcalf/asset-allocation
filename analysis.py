import scipy.optimize
import numpy as np
from collections import defaultdict

def accounts_to_allocations(accounts, asset_config, exclude_losses=False):
    allocations = defaultdict(float)
    for account in accounts:
        for holding in account.holdings:
            if exclude_losses and holding.value < holding.basis:
                continue

            asset_class = asset_config[holding.symbol]["class"]
            allocations[asset_class] += holding.value
        allocations['investable'] += account.investable

    return allocations

def class_vector(classes, asset_defns, accounts, exclude_losses=False):
    allocations = accounts_to_allocations(accounts, asset_defns, exclude_losses=exclude_losses)
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

def objective(allocations, targets, penalties):
    if len(allocations) % len(targets) != 0:
        raise Exception(
            "Allocation variable vector (%d) is not a multiple of the length of targets (%d)" %(
                len(allocations), len(targets)
            )
        )

    # Sum of the squares of the differences
    per_class = sum_to_classes(allocations, len(targets))    
    diff = sum((t - a) ** 2 for t, a in zip(targets, per_class))

    for i, penalty in enumerate(penalties):
        diff += allocations[i] * penalty
    
    return diff

def optimize_allocations(taxable_accts, non_taxable_accts, classes, assets, targets):
    num_classes = len(classes)
    
    current_taxable_allocations = class_vector(classes, assets, taxable_accts)
    min_taxable_allocations = class_vector(classes, assets, taxable_accts, exclude_losses=True)
    current_non_taxable_allocations = class_vector(classes, assets, non_taxable_accts)

    taxable_investable = sum(a.investable for a in taxable_accts)
    non_taxable_investable = sum(a.investable for a in non_taxable_accts)

    taxable_total = sum(current_taxable_allocations) + taxable_investable
    non_taxable_total = sum(current_non_taxable_allocations) + non_taxable_investable
    total = taxable_total + non_taxable_total

    target_allocations_vector = [targets.get(c, 0) * total for c in classes]

    allowed_in_taxable = find_allowed_classes(assets, "taxable")
    allowed_in_non_taxable = find_allowed_classes(assets, "non-taxable")

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

        min_lim = 0
        if classes[i] in allowed_in_non_taxable:
            max_lim = max(min_lim, target_allocations_vector[i])
        else:
            max_lim = min_lim

        constraints.append(scipy.optimize.LinearConstraint(
            arr, min_lim, max_lim
        ))

    # Constrain over-investing in an asset class.
    # This can happen when we apply adjustments to the objective function to steer
    # allocations between taxable/non-taxable
    # TODO: It's not clear that these adjustments/penalties are a good ideas anyway
    # versus some other way of later reshuffling between asset classes (e.g. like a second
    # optimization pass)
    # Anyway, this totally breaks things
    # for i in range(num_classes):
    #     arr = [0] * (2 * num_classes)
    #     arr[i] = 1
    #     arr[num_classes + i] = 1

    #     max_lim = max(min_taxable_allocations[i], target_allocations_vector[i])
   
    #     constraints.append(scipy.optimize.LinearConstraint(
    #         arr, 0, max_lim
    #     ))

    penalties = [0] * (num_classes * 2)
    if non_taxable_total > 0:
        # Apply a small penalty to holding bonds in taxable accounts
        for i, c in enumerate(classes):
            if "bond" in c and target_allocations_vector[i] > 0:
                penalties[i] = 1.0 / target_allocations_vector[i]
        # Apply a small preference for emerging stock in non-taxable accounts to hold in Roth
        # and a smaller preference for developed international. This also helps sequence what
        # goes into which account to reduce churn
    
        penalties[num_classes + classes.index("Emerging international stock")] = - 2.0 / non_taxable_total
        penalties[num_classes + classes.index("Developed international stock")] = -1.0 / non_taxable_total

    current_allocations = current_taxable_allocations + current_non_taxable_allocations

    soln = scipy.optimize.minimize(
        objective,
        current_allocations,
        args=(target_allocations_vector, penalties),
        jac='3-point', # TODO: `gradient
        hess=scipy.optimize.BFGS(), # TODO: Pretty sure I can provide this
        method='trust-constr',
        constraints=constraints,
        options={"maxiter": 5000},
    )

    if abs(soln.optimality) > 1:
        raise Exception("Expected optimality <<1, got %f" % soln.optimality)

    if abs(sum(soln.x) - total) > 1:
        raise Exception("Solution didn't spend all the money!")

    return (current_allocations, soln.x)