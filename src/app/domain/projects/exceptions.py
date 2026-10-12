from litestar.exceptions import NotAuthorizedException
from litestar.status_codes import HTTP_401_UNAUTHORIZED


class ProjectManagerRequiredException(NotAuthorizedException):
    """Raised when a `User` without the `SystemAdministrator` or `ProjectManager` role tries to modify project settings."""

    def __init__(self) -> None:
        detail = "This route may only be accessed by a system administrator or project manager."
        super().__init__(detail=detail, status_code=HTTP_401_UNAUTHORIZED)


class ProjectEngineerRequiredException(NotAuthorizedException):
    """Raised when a `User` without the `SystemAdministrator` or `OntologyEngineer` role tries to modify project settings."""

    def __init__(self) -> None:
        detail = "This route may only be accessed by a system administrator or ontology engineer."
        super().__init__(detail=detail, status_code=HTTP_401_UNAUTHORIZED)


class ProjectCuratorRequiredException(NotAuthorizedException):
    """Raised when a `User` without the `SystemAdministrator`, `ProjectManager` or `OntologyEngineer` role tries to curate project content."""

    def __init__(self) -> None:
        detail = "This route may only be accessed by a system administrator, project manager or ontology engineer."
        super().__init__(detail=detail, status_code=HTTP_401_UNAUTHORIZED)


class ProjectParticipationRequiredException(NotAuthorizedException):
    """Raised when a `User` tries to modify content of a project he neither manages, engineers nor is a member of."""

    def __init__(self) -> None:
        detail = "This route may only be accessed by project members, managers or ontology engineers."
        super().__init__(detail=detail, status_code=HTTP_401_UNAUTHORIZED)


class ProjectMembershipRequiredException(NotAuthorizedException):
    """Raised when a `User` tries to access content of a project he does not belong to."""

    def __init__(self) -> None:
        detail = "This route may only be accessed by project members."
        super().__init__(detail=detail, status_code=HTTP_401_UNAUTHORIZED)
