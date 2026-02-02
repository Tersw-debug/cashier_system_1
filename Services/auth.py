from Database.Schema import Database


def login(username, password):
    
    conn = Database.get_connection()
    c = conn.cursor()
    c.execute("SELECT role FROM users WHERE username=? AND password=?", (username, password))
    result = c.fetchone()
    conn.close()

    if not result:
        return False, None
    role = result[0]
    print(role)
    return True, role