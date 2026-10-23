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

PRODUCTS = [
    {"id": 201, "name": "Laptop", "category": "Electronics", "price": 55000, "stock": 12},
    {"id": 202, "name": "Smartphone", "category": "Electronics", "price": 28000, "stock": 25},
    {"id": 203, "name": "Headphones", "category": "Electronics", "price": 3500, "stock": 50},
    {"id": 204, "name": "Desk Chair", "category": "Furniture", "price": 8500, "stock": 8},
    {"id": 205, "name": "Coffee Table", "category": "Furniture", "price": 4200, "stock": 0},
    {"id": 206, "name": "Standing Desk", "category": "Furniture", "price": 18000, "stock": 5},
    {"id": 207, "name": "SQL Guide", "category": "Books", "price": 650, "stock": 100},
    {"id": 208, "name": "Compilers Book", "category": "Books", "price": 1200, "stock": 40},
    {"id": 209, "name": "Mechanical Keyboard", "category": "Electronics", "price": 4500, "stock": 15},
    {"id": 210, "name": "Monitor", "category": "Electronics", "price": 14000, "stock": 0},
]

DEPARTMENTS = [
    {"id": 10, "dept_name": "Engineering", "budget": 500000, "building": "Tower A"},
    {"id": 20, "dept_name": "Product", "budget": 250000, "building": "Tower A"},
    {"id": 30, "dept_name": "Marketing", "budget": 180000, "building": "Tower B"},
    {"id": 40, "dept_name": "Operations", "budget": 120000, "building": "Tower C"},
]

EMPLOYEES = [
    {"id": 1, "name": "Aditi", "dept_id": 10, "salary": 85000, "city": "Bengaluru"},
    {"id": 2, "name": "Karan", "dept_id": 10, "salary": 92000, "city": "Delhi"},
    {"id": 3, "name": "Priya", "dept_id": 20, "salary": 78000, "city": "Mumbai"},
    {"id": 4, "name": "Rahul", "dept_id": 30, "salary": 52000, "city": "Pune"},
    {"id": 5, "name": "Neha", "dept_id": 10, "salary": 64000, "city": "Bengaluru"},
    {"id": 6, "name": "Vikram", "dept_id": 20, "salary": 71000, "city": "Delhi"},
    {"id": 7, "name": "Simran", "dept_id": 40, "salary": 45000, "city": "Chennai"},
    {"id": 8, "name": "Manish", "dept_id": 30, "salary": 58000, "city": "Bengaluru"},
]

TABLES = {
    "users": USERS,
    "orders": ORDERS,
    "products": PRODUCTS,
    "departments": DEPARTMENTS,
    "employees": EMPLOYEES,
}
TABLE_ROW_COUNTS = {name: len(rows) for name, rows in TABLES.items()}
