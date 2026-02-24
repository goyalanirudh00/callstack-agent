"""
Sample Application: User Registration System
=============================================
A simple multi-function app to demonstrate call stack dynamic testing.
This has normal functions (not recursive) with various call paths.
"""


# --- Validation layer ---

def validate_email(email: str) -> bool:
    if not isinstance(email, str):
        raise TypeError(f"Email must be a string, got {type(email).__name__}")
    if "@" not in email:
        raise ValueError(f"Invalid email: missing '@'")
    if "." not in email.split("@")[1]:
        raise ValueError(f"Invalid email: missing domain")
    return True


def validate_name(name: str) -> bool:
    if not isinstance(name, str):
        raise TypeError(f"Name must be a string, got {type(name).__name__}")
    if len(name.strip()) < 2:
        raise ValueError(f"Name too short: '{name}'")
    if len(name) > 100:
        raise ValueError(f"Name too long: {len(name)} chars")
    return True


def validate_age(age: int) -> bool:
    if not isinstance(age, int):
        raise TypeError(f"Age must be int, got {type(age).__name__}")
    if age < 0 or age > 150:
        raise ValueError(f"Invalid age: {age}")
    return True


# --- Data layer ---

_db = {}
_next_id = 1


def save_to_db(record: dict) -> dict:
    global _next_id
    record["id"] = _next_id
    _db[_next_id] = record
    _next_id += 1
    return record


def get_from_db(record_id: int) -> dict:
    if record_id not in _db:
        raise KeyError(f"Record {record_id} not found")
    return _db[record_id]


def delete_from_db(record_id: int) -> bool:
    if record_id not in _db:
        raise KeyError(f"Record {record_id} not found")
    del _db[record_id]
    return True


# --- Business logic layer ---

def create_user(name: str, email: str, age: int) -> dict:
    validate_name(name)
    validate_email(email)
    validate_age(age)
    user = {"name": name, "email": email, "age": age, "role": "user"}
    return save_to_db(user)


def create_admin(name: str, email: str, age: int) -> dict:
    validate_name(name)
    validate_email(email)
    validate_age(age)
    if age < 18:
        raise ValueError("Admins must be 18 or older")
    user = {"name": name, "email": email, "age": age, "role": "admin"}
    return save_to_db(user)


def update_user_email(user_id: int, new_email: str) -> dict:
    validate_email(new_email)
    user = get_from_db(user_id)
    user["email"] = new_email
    return user


# --- Entry points ---

def register(name: str, email: str, age: int) -> dict:
    user = create_user(name, email, age)
    send_notification(user, "welcome")
    return user


def admin_register(name: str, email: str, age: int, admin_key: str) -> dict:
    if admin_key != "secret-admin-key":
        raise PermissionError("Invalid admin key")
    user = create_admin(name, email, age)
    send_notification(user, "admin_welcome")
    return user


# --- Side effects ---

_notifications = []


def send_notification(user: dict, notification_type: str):
    msg = format_message(user, notification_type)
    _notifications.append(msg)


def format_message(user: dict, notification_type: str) -> str:
    if notification_type == "welcome":
        return f"Welcome {user['name']}! Your account has been created."
    elif notification_type == "admin_welcome":
        return f"Welcome Admin {user['name']}! You have admin privileges."
    else:
        return f"Notification for {user['name']}: {notification_type}"


def reset():
    global _db, _next_id, _notifications
    _db = {}
    _next_id = 1
    _notifications = []
