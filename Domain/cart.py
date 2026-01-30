
class Cart:
    def __init__(self):
        self.items = []

    def add(self, product_id, name, qty, price):
        subtotal = qty * price
        self.items.append((product_id, name, qty, price, subtotal))

    def total(self):
        return sum(item[4] for item in self.items)
    
    def clear(self):
        self.items.clear()