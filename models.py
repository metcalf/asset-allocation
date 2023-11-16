
class Account(object):
    def __init__(self, name, owner, broker, taxable, holdings=None):
        self._name = name
        self._owner = owner
        self._broker = broker
        self._taxable = taxable
        self.holdings = holdings or []

    @property
    def name(self):
        return self._name

    @property
    def owner(self):
        return self._owner

    @property
    def broker(self):
        return self._broker

    @property
    def taxable(self):
        return self._taxable

    def __repr__(self):
        return str(self)

    def __str__(self):
        value = sum(holding.value for holding in self.holdings)

        return "%s($%0.2f, owner=%s, taxable=%s, broker=%s, # holdings=%d)" % (
            self.name,
            value,
            self.owner,
            self.taxable,
            self.broker,
            len(self.holdings)
        )

class Holding(object):
    def __init__(self, account, symbol, quantity, price, unit_cost, yield_rate, maturity_date):
        self._account = account
        self._symbol = symbol
        self._quantity = quantity
        self._price = price
        self._unit_cost = unit_cost
        self._yield_rate = yield_rate
        self._maturity_date = maturity_date

    @property
    def account(self):
        return self._account

    @property
    def symbol(self):
        return self._symbol

    @property
    def quantity(self):
        return self._quantity

    @property
    def value(self):
        return self._price * self.quantity

    @property
    def basis(self):
        return self.unit_cost * self.quantity

    @property
    def unit_cost(self):
        return self._unit_cost

    @property
    def yield_rate(self):
        return self._yield_rate

    @property
    def maturity_date(self):
        return self._maturity_date

    @property
    def is_bond(self):
        return self._maturity_date is not None

    def __repr__(self):
        return str(self)

    def __str__(self):
        return "%s(value=$%0.2f, gain=$%0.2f, qty=%s, acct=%s)" % (
            self.symbol,
            self.value,
            self.value - self.basis,
            self.quantity,
            self.account.name,
        )
