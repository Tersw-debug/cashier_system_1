
def go_login(root):
    from UI.login_page import show_login
    show_login(root)

def go_admin(root):
    from UI.ui_admin import open_admin
    open_admin(root)

def go_cashier(root, username):
    from UI.ui_cashier import open_cashier
    open_cashier(root, username)