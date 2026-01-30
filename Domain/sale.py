from datetime import datetime

class Sale:
    def __init__(self, cashier):
        self.date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self.cashier = cashier
         