import parsers
import json
import os.path
from collections import defaultdict

from . import merrill, fidelity

def read_config(path):
    with open(path) as f:
        cfg = json.load(f)
    _validate_config(cfg)
    return cfg

def read_accounts(path, accounts_config, allow_after):
    accounts = []
    for name, accounts_config in accounts_config.items():
        parser = globals()[accounts_config["format"]]
        contents = parser.read(os.path.join(path, name))
        accounts += parser.parse(contents, accounts_config, allow_after)

    return accounts

def _validate_config(config):
    valid_classes = set(config["classes"])

    # Check that allocations sum to 1 and contain valid classes
    for owner, classes in config["targets"].items():
        total = sum(classes.values())
        if abs(total - 1) > 0.0001:
            raise Exception("Asset targets for %s sum to %0.4f" % (owner, total))

        extra = set(classes.keys()) - valid_classes
        if len(extra) > 0:
            raise Exception("Found unknown classes in allocations for %s: %s" % (owner, extra))

    for symbol, defn in config["assets"].items():
        if defn["class"] not in valid_classes:
            raise Exception("Unknown class %s for %s" % (defn["class"], symbol))

        if defn.get("location", "taxable") not in ("taxable", "non-taxable"):
            raise Exception("Unknown location %s" % defn["location"])
