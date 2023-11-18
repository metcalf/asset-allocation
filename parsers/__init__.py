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

    for symbol, defn in config["assets"].items():
        if defn["class"] not in valid_classes:
            raise Exception("Unknown class %s for %s" % (defn["class"], symbol))

        if defn.get("location", "taxable") not in ("taxable", "non-taxable"):
            raise Exception("Unknown location %s" % defn["location"])
