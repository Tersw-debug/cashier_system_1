

class Product:

    def __init__(self, created_at,name, barcode,price,qty,min_qty):
        self.created_at = created_at
        self.name = name
        self.barcode = barcode
        self.price = price
        self.qty = qty
        self.min_qty = min_qty