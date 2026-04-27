import random
import string
from typing import Iterable, NamedTuple
from uuid import UUID

from pydantic import EmailStr
from sqlalchemy.exc import IntegrityError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from .authentication.exceptions import (
    InvalidPasswordFormatException,
    InvalidPasswordLengthException,
)
from .authentication.services import EncryptionService, PasswordHash
from .dtos import (
    UserChangePasswordDTO,
    UserGetDTO,
    UserLoginDTO,
    UserRegisterDTO,
    UserUpdateDTO,
)
from .exceptions import (
    DelegateHTTPException,
    EmailInUseException,
    NameInUseException,
    UnmatchedCredentialsException,
    UserInUseException,
)
from .models import User

InvitedUsers = NamedTuple(
    "InvitedUsers",
    [("existing", Iterable[User]), ("created", Iterable[tuple[User, str]])],
)


class UserService:
    @staticmethod
    def _encrypt_password(encryption: EncryptionService, password: str) -> PasswordHash:
        """Encrypts a given password.

        :param encryption: Encryption service to use for password encryption.
        :param password: Password to encrypt.
        :raises DelegateHTTPException: If the given password is malformed.
        :return: A hashed password.
        """
        try:
            return encryption.hash_password(password)
        except (
            InvalidPasswordFormatException,
            InvalidPasswordLengthException,
        ) as exception:
            raise DelegateHTTPException(exception)

    @staticmethod
    async def get_users(session: AsyncSession) -> list[UserGetDTO]:
        """Gets all `Users` from the database.

        :param session: An active database session.
        :return: A `list` of all `Users`.
        """
        if users := await session.scalars(select(User)):
            return [UserGetDTO.model_validate(user) for user in users.all()]
        return []

    @staticmethod
    async def get_user(session: AsyncSession, user_email: str) -> UserGetDTO | None:
        """Gets a specific `User` by his `id`.

        :param session: An active database session.
        :param user_email: The `Users` `email`.
        :return: The selected `User` if found.
        """
        if user := await session.scalar(select(User).where(User.email == user_email)):
            return UserGetDTO.model_validate(user)
        return None

    @staticmethod
    async def get_user_by_credentials(
        session: AsyncSession, encryption: EncryptionService, data: UserLoginDTO
    ) -> User | None:
        """Gets a `User` by his login credentials.

        :param session: An active database session.
        :param encryption: Encryption service to use for password decryption.
        :param data: The `User's` credentials.
        :return: A matching `User` if any.
        """
        if user := await session.scalar(select(User).where(User.email == data.email)):
            if user.password_hash == encryption.resolve_password(
                data.password, user.password_salt
            ):
                return user
        return None

    @staticmethod
    async def update_user(
        session: AsyncSession,
        encryption: EncryptionService,
        user_email: EmailStr,
        data: UserUpdateDTO,
    ) -> UserGetDTO | None:
        """Updates a specific `User` by his `id` and the given data.

        :param session: An active database session.
        :param encryption: Encryption service to use for password encryption.
        :param user_id: The `Users` `id`.
        :param data: Any updates that should be applied to the `User`.
        :return: The updated `User` if found.
        """
        if data.email and await session.scalar(
            select(User).where(User.email == data.email)
        ):
            raise EmailInUseException(data.email)

        if data.name and await session.scalar(
            select(User).where(User.name == data.name)
        ):
            raise NameInUseException(data.name)

        if user := await session.scalar(select(User).where(User.email == user_email)):
            user.name = data.name if data.name else user.name
            user.is_system_admin = (
                data.is_system_admin if data.is_system_admin else user.is_system_admin
            )
            user.is_verified = (
                data.is_verified if data.is_verified else user.is_verified
            )

            if data.password:
                password = UserService._encrypt_password(encryption, data.password)
                user.password_hash = password.hash
                user.password_salt = password.salt

            return UserGetDTO.model_validate(user)
        return None

    @staticmethod
    async def delete_user(session: AsyncSession, user_email: str) -> bool:
        """Deletes a specific `User` by his `id`.

        :param session: An active database session.
        :param user_id: The `Users` `id`.
        :return: `True` if a `User` was removed else `False`.
        """
        if user := await session.scalar(select(User).where(User.email == user_email)):
            try:
                await session.delete(user)
                await session.flush()
            except IntegrityError as error:
                raise UserInUseException(user_email) from error
        return True if user else False

    @staticmethod
    async def change_password(
        session: AsyncSession,
        encryption: EncryptionService,
        user_id: UUID,
        data: UserChangePasswordDTO,
    ) -> bool:
        """Changes the password of a specific `User` by his `id`.

        :param session: An active database session.
        :param encryption: Encryption service to use for password hashing and verification.
        :param user_id: The `Users` `id`.
        :param data: Current and new password.
        :raises UnmatchedCredentialsException: If the current password is invalid.
        :return: `True` if the password was updated else `False`.
        """
        if user := await session.scalar(select(User).where(User.id == user_id)):
            current_password_hash = encryption.resolve_password(
                data.current_password, user.password_salt
            )
            if user.password_hash != current_password_hash:
                raise UnmatchedCredentialsException()

            new_password = UserService._encrypt_password(encryption, data.new_password)
            user.password_hash = new_password.hash
            user.password_salt = new_password.salt
            return True
        return False

    @staticmethod
    async def add_user(
        session: AsyncSession,
        encryption: EncryptionService,
        data: UserRegisterDTO,
    ) -> UserGetDTO:
        """Add a new `User` to the database and returns him.

        Notes:
            * name and email validation will be handled by database constraints

        :param session: An active database session.
        :param encryption: Encryption service to use for password encryption.
        :param data: The parameters for the new `User`.
        :raises NameInUseException: If the given `name` is not unique.
        :raises EmailInUseException: If the given `email` is not unique.
        :return: The new `User` if created.
        """
        if await session.scalar(select(User).where(User.name == data.name)):
            raise NameInUseException(data.name)

        if await session.scalar(select(User).where(User.email == data.email)):
            raise EmailInUseException(data.email)

        password = UserService._encrypt_password(encryption, data.password)

        user = User(
            name=data.name,
            email=data.email,
            password_hash=password.hash,
            password_salt=password.salt,
            is_system_admin=False,
            is_verified=False,
        )
        session.add(user)
        return UserGetDTO.model_validate(user)

    @staticmethod
    async def verify_user(session: AsyncSession, user_email: str) -> UserGetDTO | None:
        """Directly verifies a specific `User` (alternative to `add_user`).

        :param session: An active database session.
        :param user_email: The `Users` `email address`.
        :return: The updated `User` if found.
        """
        if user := await session.scalar(select(User).where(User.email == user_email)):
            user.is_verified = True
            return UserGetDTO.model_validate(user)
        return None

    @staticmethod
    def create_temporary_user(
        encryption: EncryptionService, email: EmailStr
    ) -> tuple[User, str]:
        name = email
        sequence = [
            *random.sample(string.ascii_lowercase, 4),
            *random.sample(string.ascii_uppercase, 4),
            *random.sample(string.digits, 4),
        ]
        random.shuffle(sequence)
        password = "".join(sequence)
        password_hash = UserService._encrypt_password(encryption, password)
        return (
            User(
                email=email,
                name=name,
                password_hash=password_hash.hash,
                password_salt=password_hash.salt,
                is_system_admin=False,
                is_verified=True,
            ),
            password,
        )

    @staticmethod
    async def get_or_create_users(
        session: AsyncSession,
        encryption: EncryptionService,
        emails: Iterable[EmailStr],
    ) -> InvitedUsers:
        mails = set(emails)
        existing_users = await session.scalars(
            select(User).where(User.email.in_(mails))
        )
        existing_users = existing_users.all()

        mails -= set(map(lambda user: user.email, existing_users))
        invited_users = [
            *map(
                lambda mail: UserService.create_temporary_user(encryption, mail), mails
            )
        ]
        session.add_all([user for user, _ in invited_users])
        await session.commit()
        _ = [await session.refresh(user) for user, _ in invited_users]
        return InvitedUsers(existing_users, invited_users)
