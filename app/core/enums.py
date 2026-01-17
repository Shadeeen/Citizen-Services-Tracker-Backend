from enum import Enum

class UserRole(str, Enum):
    admin = "admin"
    staff = "staff"
    citizen = "citizen"


class UserStatus(str, Enum):
    active = "active"
    disabled = "disabled"
