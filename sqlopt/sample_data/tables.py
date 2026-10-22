"""Small data sets used by the interactive demo and executor."""

USERS = [
    {"id": 1, "name": "Aarav", "age": 24, "city": "Delhi", "active": 1},
    {"id": 2, "name": "Diya", "age": 17, "city": "Mumbai", "active": 1},
    {"id": 3, "name": "Kabir", "age": 31, "city": "Bengaluru", "active": 0},
    {"id": 4, "name": "Ananya", "age": 28, "city": "Delhi", "active": 1},
    {"id": 5, "name": "Vivaan", "age": 19, "city": "Pune", "active": 1},
    {"id": 6, "name": "Isha", "age": 42, "city": "Mumbai", "active": 0},
    {"id": 7, "name": "Arjun", "age": 35, "city": "Chennai", "active": 1},
    {"id": 8, "name": "Meera", "age": 22, "city": "Bengaluru", "active": 1},
    {"id": 9, "name": "Rohan", "age": 16, "city": "Pune", "active": 0},
    {"id": 10, "name": "Sara", "age": 29, "city": "Delhi", "active": 1},
]

ORDERS = [
    {"id": 101, "user_id": 1, "status": "shipped", "amount": 1200},
    {"id": 102, "user_id": 2, "status": "pending", "amount": 650},
    {"id": 103, "user_id": 3, "status": "shipped", "amount": 2200},
    {"id": 104, "user_id": 1, "status": "cancelled", "amount": 350},
    {"id": 105, "user_id": 4, "status": "shipped", "amount": 980},
    {"id": 106, "user_id": 5, "status": "pending", "amount": 1500},
    {"id": 107, "user_id": 6, "status": "shipped", "amount": 430},
    {"id": 108, "user_id": 7, "status": "shipped", "amount": 3100},
    {"id": 109, "user_id": 8, "status": "pending", "amount": 760},
    {"id": 110, "user_id": 10, "status": "shipped", "amount": 540},
]

TABLES = {"users": USERS, "orders": ORDERS}
TABLE_ROW_COUNTS = {name: len(rows) for name, rows in TABLES.items()}
