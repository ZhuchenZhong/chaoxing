import enum


class UserRole(str, enum.Enum):
    USER = "user"
    ADMIN = "admin"


class ChaoxingAuthType(str, enum.Enum):
    PASSWORD = "password"
    COOKIES = "cookies"


class NotOpenAction(str, enum.Enum):
    RETRY = "retry"
    CONTINUE = "continue"
