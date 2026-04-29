import importlib
import pathlib
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import InitVar, dataclass, field
from os import environ
from typing import Callable

from advanced_alchemy.extensions.litestar.plugins.init.config import (
    SQLAlchemyAsyncConfig,
)
from advanced_alchemy.extensions.litestar.plugins.init.config.asyncio import (
    autocommit_before_send_handler,
)
from advanced_alchemy.extensions.litestar.plugins.init.plugin import (
    SQLAlchemyInitPlugin,
)
from litestar.config.app import AppConfig
from advanced_alchemy.base import UUIDBase
from sqlalchemy.engine import Connection
from sqlalchemy import inspect, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

_default_db_path = (
    pathlib.Path(__file__).resolve().parents[3] / "database" / "cq_manager.db"
)

_engine = create_async_engine(
    environ.get("CONNECTION_STRING") or f"sqlite+aiosqlite:///{_default_db_path}",
)

_async_session_factory: async_sessionmaker[AsyncSession] = async_sessionmaker(
    _engine, expire_on_commit=True
)


@dataclass(frozen=True)
class AsyncSqlPlugin:
    """Wraps `litestar's` `sqlalchemy` plugin."""

    dependency_key: InitVar[str] = "session"
    modules_pattern: str = "**/domain/**/models.py"
    config: SQLAlchemyAsyncConfig = field(init=False)
    plugin: SQLAlchemyInitPlugin = field(init=False)

    def _init_mappers_(self) -> None:
        """Preloads all `modules` found by a given `glob.pattern`.

        This is useful when working with many models and relationships in `sqlalchemy`.
        Relationships are prone to circular imports therefore PEP 563 styled imports for
        relational model should be used. But these imports do not actually set up the classes
        at import time which may break `sqlalchemy`s mappers once the first module is accessed#
        for real. This than results in `InvalidRequestError`s where the mappers can not find the
        annotated classes.

        A solution for this problem is to pre load all modules before they are accessed directly
        and this is what dis hook tries to automate.

        `sqlalchemy` does not yet provide something like this.
        """
        cwd = pathlib.Path.cwd()
        app = pathlib.Path(__file__).parent.parent
        module_paths = cwd.glob(self.modules_pattern)
        module_names = map(
            lambda x: ".".join(x.relative_to(app).parts).replace(".py", ""),
            module_paths,
        )
        _, *_ = map(lambda x: importlib.import_module(x), module_names)

    def __post_init__(self, dependency_key: str) -> None:
        config = SQLAlchemyAsyncConfig(
            session_dependency_key=dependency_key,
            engine_instance=_engine,
            session_maker=_async_session_factory,
            before_send_handler=autocommit_before_send_handler,
        )
        plugin = SQLAlchemyInitPlugin(config=config)
        object.__setattr__(self, "config", config)
        object.__setattr__(self, "plugin", plugin)
        self._init_mappers_()

    @property
    def on_app_init(self) -> Callable[[AppConfig], AppConfig]:
        """Forwards `litestar's` plugins `on_app_init`."""
        return self.plugin.on_app_init

    @staticmethod
    def _ensure_question_sparql_query_column(connection: Connection) -> None:
        columns = {column["name"] for column in inspect(connection).get_columns("question")}
        if "sparql_query" not in columns:
            connection.execute(text("ALTER TABLE question ADD COLUMN sparql_query VARCHAR"))

    @staticmethod
    def _ensure_consolidation_result_question_id_column(connection: Connection) -> None:
        columns = {
            column["name"]
            for column in inspect(connection).get_columns("consolidation")
        }
        if "result_question_id" not in columns:
            connection.execute(
                text("ALTER TABLE consolidation ADD COLUMN result_question_id CHAR(32)")
            )

    @staticmethod
    def _remove_consolidation_name_column(connection: Connection) -> None:
        columns = {
            column["name"] for column in inspect(connection).get_columns("consolidation")
        }
        if "name" not in columns:
            return

        connection.execute(text("PRAGMA foreign_keys=OFF"))
        connection.execute(text("DROP TABLE IF EXISTS consolidation_new"))
        connection.execute(
            text(
                """
                CREATE TABLE consolidation_new (
                    id BINARY(16) NOT NULL,
                    engineer_id BINARY(16) NOT NULL,
                    project_id BINARY(16) NOT NULL,
                    sa_orm_sentinel INTEGER,
                    created_at DATETIME NOT NULL,
                    updated_at DATETIME NOT NULL,
                    result_question_id BINARY(16),
                    CONSTRAINT pk_consolidation PRIMARY KEY (id),
                    CONSTRAINT fk_consolidation_engineer_id_user
                        FOREIGN KEY(engineer_id) REFERENCES user (id),
                    CONSTRAINT fk_consolidation_project_id_project
                        FOREIGN KEY(project_id) REFERENCES project (id),
                    CONSTRAINT fk_consolidation_result_question_id_question
                        FOREIGN KEY(result_question_id) REFERENCES question (id)
                )
                """
            )
        )
        connection.execute(
            text(
                """
                INSERT INTO consolidation_new (
                    id, engineer_id, project_id, sa_orm_sentinel,
                    created_at, updated_at, result_question_id
                )
                SELECT
                    id, engineer_id, project_id, sa_orm_sentinel,
                    created_at, updated_at, result_question_id
                FROM consolidation
                """
            )
        )
        connection.execute(text("DROP TABLE consolidation"))
        connection.execute(text("ALTER TABLE consolidation_new RENAME TO consolidation"))
        connection.execute(text("PRAGMA foreign_keys=ON"))

    async def on_startup(self) -> None:
        """Initializes the database."""
        async with self.config.get_engine().begin() as conn:
            # await conn.run_sync(UUIDBase.metadata.drop_all)
            await conn.run_sync(UUIDBase.metadata.create_all)
            await conn.run_sync(self._ensure_question_sparql_query_column)
            await conn.run_sync(self._ensure_consolidation_result_question_id_column)
            await conn.run_sync(self._remove_consolidation_name_column)


@asynccontextmanager
async def session() -> AsyncIterator[AsyncSession]:
    """Gets a database session using the same engine as `litestar`.

    Notes:
        * since this session is not yielded from a route handler commit,
          rollback and close need to be called explicitly

    :yield: An `AsyncSession`.
    """
    async with _async_session_factory() as session:
        yield session
