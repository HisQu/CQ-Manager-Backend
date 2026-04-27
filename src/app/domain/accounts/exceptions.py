from uuid import UUID

from litestar.exceptions import HTTPException, NotAuthorizedException
from litestar.status_codes import (
    HTTP_400_BAD_REQUEST,
    HTTP_401_UNAUTHORIZED,
    HTTP_404_NOT_FOUND,
    HTTP_409_CONFLICT,
)


class UserNotFoundException(HTTPException):
    """Raised if a specified `User` was not found."""

    def __init__(self, user_email: str) -> None:
        detail = f"No user with id '{user_email}' was found."
        super().__init__(detail=detail, status_code=HTTP_404_NOT_FOUND)


class NameInUseException(HTTPException):
    """Raised on register if the given `name` is already in use by another `User`."""

    def __init__(self, name: str) -> None:
        detail = f"A user with the name '{name}' already exists."
        super().__init__(detail=detail, status_code=HTTP_400_BAD_REQUEST)


class EmailInUseException(HTTPException):
    """Raised on register if the given `email` is already in use by another `User`."""

    def __init__(self, email: str) -> None:
        detail = f"A user with the email address '{email}' already exists."
        super().__init__(detail=detail, status_code=HTTP_400_BAD_REQUEST)


class UnmatchedCredentialsException(NotAuthorizedException):
    """Raised if a login attempt failed."""

    def __init__(self) -> None:
        detail = f"No user with a matching set of credentials was found."
        super().__init__(detail=detail, status_code=HTTP_401_UNAUTHORIZED)


class DelegateHTTPException(HTTPException):
    """Forwards a basic `Exception` into an `HTTPException`."""

    def __init__(
        self, exception: Exception, status_code: int = HTTP_400_BAD_REQUEST
    ) -> None:
        super().__init__(detail=exception.args[0], status_code=status_code)


class VerificationRequiredException(NotAuthorizedException):
    """Raised when an unverified `User` tries to access and endpoint that requires authentication."""

    def __init__(self) -> None:
        detail = "This route may only be accessed by verified users. Contact your system administrators to get your account verified."
        super().__init__(detail=detail, status_code=HTTP_401_UNAUTHORIZED)


class SystemAdministratorRequiredException(NotAuthorizedException):
    """Raised when a `User` without the `SystemAdministrator` role tries to access a locked endpoint."""

    def __init__(self) -> None:
        detail = "This route may only be accessed by a system administrator."
        super().__init__(detail=detail, status_code=HTTP_401_UNAUTHORIZED)


class UserInUseException(HTTPException):
    """Raised when a `User` cannot be deleted because it is referenced by other entities."""

    def __init__(self, user_email: str) -> None:
        detail = (
            f"The user '{user_email}' is still referenced by other records and cannot be deleted. "
            "Remove or reassign related records first."
        )
        super().__init__(detail=detail, status_code=HTTP_409_CONFLICT)
