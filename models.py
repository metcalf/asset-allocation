
class Account(object):
    def __init__(self, name, owner, broker, taxable, investable=0, holdings=None):
        self._name = name
        self._owner = owner
        self._broker = broker
        self._taxable = taxable
        self.investable = investable
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
        value = self.investable + sum(holding.value for holding in self.holdings)
        
        return "%s($%0.2f, owner=%s, taxable=%s, broker=%s, investable=$%0.2f, # holdings=%d)" % (
            self.name,
            value,
            self.owner,
            self.taxable,
            self.broker,
            self.investable,
            len(self.holdings)
        )

class Holding(object):
    def __init__(self, account, symbol, quantity, price, unit_cost):
        self.quantity = quantity

        self._account = account
        self._symbol = symbol
        self._price = price
        self._unit_cost = unit_cost

    @property
    def account(self):
        return self._account

    @property
    def symbol(self):
        return self._symbol

    @property
    def value(self):
        return self._price * self.quantity

    @property
    def basis(self):
        return self.unit_cost * self.quantity

    @property
    def unit_cost(self):
        return self._unit_cost

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