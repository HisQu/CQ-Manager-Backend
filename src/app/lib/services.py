from uuid import UUID

from domain.accounts.models import User
from domain.consolidations.models import Consolidation
from domain.groups.models import Group
from domain.projects.models import Project
from domain.questions.models import Question, QuestionCatalogueReservation
from domain.ratings.models import Rating
from domain.topics.models import Topic
from domain.versions.models import Version
from domain.comments.models import Comment
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import DeclarativeBase

from .orm import session as session_maker
from domain.terms.models import Term
from domain.terms.models import Passage


class MockDataService:
    """Simple mock data service.

    Tries to insert mock data on application start up, ignores any errors.

    TODO: make this optional
    """

    mock_password = b"\xef\xb9\tG\xff\x997\x88\x82\x95\x13\x1c(\x98\x81\x0e\xe9\x1a\xb4\xf0\x97\x11\x1c\x88\xb7\xc7\xfc\xe6l\xfa!\x835/\x95\xf9$\x8e.\xc1\xe1[z\xb8\xa7|\x81\xdc-\x1bir\x80I\x08|\xa8\xa6=d\xef\xe6w\x17a\x9c\xf8\xb5\xa1\xa5\x9dEd\xd0Z\x03mb\xc7\t\x15j\x80\xfc\xbaK.\xe9\xe5\xca\xe7xu\xfb\xd8z\xd3\xb6\xed\x04\xbe\x08u\xab\xae[\xc9\x9b3\xd4h\xbed`l7H\xb1\xe77*,e\x91+?\x8c\x99"
    mock_salt = b"i\xf1\xc7g\xf9\xba\x16\xd4\x00V\xbe!\xcf\x1e3\xfb[\x98\x0e\x9a\x16A\x0e\xb9'B\x89\x06Y\x97Y\xec\x1b%\xd3\xef\xabR\x16\xd3M4\xc8\x18\xfb4\xaa\xf6\x93*\xf5\x0b\x9f\xcby\xbe\xd2\x9b\x17\x83g\x80\xfa\x80\xd2\x94\xa1\x05\xcb\x03\x11\x85\xe9\xfd\x94\xb6\xea\xe7N7\x1e\x10SC\xc8\xa3\xc9\x01\xbd\x8b\xa3\xd9\xc8o*\xd7\xbd\xb1\x91\x17\xba\xe7\x10b\xd2g\xcb7G\x15%\xden\xdd\x9d\xa7:\x14w\xa8\\\xe0v,\xdb\xcf\xc3L"
    mock_topic_id = UUID("5bf24c4c-90b4-482d-8fda-89d47fb4cdb2")
    mock_topic_project_id = UUID("7efa96ba-c7a9-4069-9728-dc7fa2c105fd")
    mock_topic_question_id = UUID("92bcacac-c5bf-4fe3-a12a-d52d5f3ac1f1")

    mock_versions = [
        Version(
            question_string="How is it?",
            id=UUID("9811106f-0556-4cb6-9d00-292e6c026952"),
            version_number=1,
            question_id=UUID("2de6c0c8-3565-4c5a-bc85-3b5971e0e452"),
            editor_id=UUID("a8693768-244b-4b87-9972-548034df1cc3"),
        )
    ]
    mock_questions = [
        Question(
            question="How is it really?",
            id=UUID("2de6c0c8-3565-4c5a-bc85-3b5971e0e452"),
            version_number=2,
            author_id=UUID("a8693768-244b-4b87-9972-548034df1cc3"),
            editor_id=UUID("a3fbf0c3-35cb-4774-8eba-10bdd1cbfb0c"),
            group_id=UUID("b0488a1e-3768-4d34-8c90-f24f1f9036a3"),
            annotations=[
                Passage(
                    content="really",
                    #author_id=UUID("a3fbf0c3-35cb-4774-8eba-10bdd1cbfb0c"),
                    term_id=UUID("ec1b45bc-a901-4f0e-934b-bf90cb61855a"),
                )
            ],
        ),
        Question(
            question="Hot take: what if the earth is actually a cube?",
            id=UUID("92bcacac-c5bf-4fe3-a12a-d52d5f3ac1f1"),
            version_number=1,
            author_id=UUID("e0ca0b85-2960-4f47-8a1c-1acda6d13b87"),
            editor_id=UUID("e0ca0b85-2960-4f47-8a1c-1acda6d13b87"),
            group_id=UUID("a825cd37-f637-4853-bc73-97a2b01f18e7"),
            topic_id=mock_topic_id,
            catalogue_index=1,
        ),
        Question(
            question="Maps are square right?",
            id=UUID("968b9a07-463d-4e0d-a2ea-ba39c06e830d"),
            version_number=1,
            author_id=UUID("a8693768-244b-4b87-9972-548034df1cc3"),
            editor_id=UUID("a8693768-244b-4b87-9972-548034df1cc3"),
            group_id=UUID("a825cd37-f637-4853-bc73-97a2b01f18e7"),
        ),
        Question(
            question="What shape is the earth according to current evidence?",
            id=UUID("4f8c5f0b-5966-49d6-8d0f-a9a2e7883114"),
            version_number=1,
            author_id=UUID("a3fbf0c3-35cb-4774-8eba-10bdd1cbfb0c"),
            editor_id=UUID("a3fbf0c3-35cb-4774-8eba-10bdd1cbfb0c"),
            group_id=UUID("a825cd37-f637-4853-bc73-97a2b01f18e7"),
        ),
        Question(
            question="Ist ein akademischer Grad in BFO als `role` oder als `quality` zu modellieren?",
            comment="Designentscheidung dokumentieren.",
            reference="S. 137.",
            anchor=(
                "S. 137 Abs. 2 - funktionale Bestimmung des Studiums: Graduierungen verschaffen Vorteile "
                "beim Pfründenerwerb; Studium dient der Berufs- und Pfründenkarriere."
            ),
            example_answer=(
                "Empfehlung: `role`; der Grad ist realisierbar, z. B. bei Pfründenbewerbungen. "
                "Alternative: `generically dependent continuant` (Diplom als Träger)."
            ),
            type="FCQ",
            id=UUID("3c43a53b-b260-4de6-8c56-773a8fbb89a9"),
            version_number=1,
            author_id=UUID("a8693768-244b-4b87-9972-548034df1cc3"),
            editor_id=UUID("a8693768-244b-4b87-9972-548034df1cc3"),
            group_id=UUID("0469f9f6-a1a5-4e1b-b829-48366171f7ed"),
        ),
        Question(
            question="Ist die Klasse Doktor des kanonischen Rechts rigide?",
            reference="S. 136 Anm. 10.",
            anchor=(
                "S. 136 Anm. 10 - Promotion Lysuras zum `decretorum doctor` zeitlich nach den "
                "Immatrikulationen 1417/1423/1424."
            ),
            example_answer=(
                "Anti-rigide bezogen auf den Lebenslauf der Person; vor der Promotion gilt sie nicht. "
                "Typischerweise einmal erworben dann beständig - daher als Rolle mit dauerhafter "
                "Realisierung modellieren."
            ),
            type="MpCQ",
            id=UUID("b83d8f91-f3e6-4c5f-81b7-bf3cb5b7db92"),
            version_number=1,
            author_id=UUID("a8693768-244b-4b87-9972-548034df1cc3"),
            editor_id=UUID("a8693768-244b-4b87-9972-548034df1cc3"),
            group_id=UUID("0469f9f6-a1a5-4e1b-b829-48366171f7ed"),
        ),
        Question(
            question="Welche kirchlichen und kurialen Ämter werden im Repertorium Germanicum genannt?",
            reference="S. 138, 139, 140, 144 Anm. 44.",
            anchor=(
                "S. 138 Abs. 4 - Rotaauditoren, Kanzleibedienstete. S. 139 Abs. 3 - päpstlicher "
                "Zeremonienmeister Burchardus. S. 140 Abs. 1 - Offizial, Generalvikar, päpstlich "
                "delegierter Richter; Audientiaprokurator. S. 144 Anm. 44 - Heinrich Kalteisen OP "
                "als `magister sacri palatii`."
            ),
            example_answer=(
                "Bischof, Propst, Dekan, Kanoniker, Pfarrer, Vikar, Offizial, Generalvikar, päpstlich "
                "delegierter Richter, Kaplan, Familiare, Kuriale, Rotaauditor, Audientiaprokurator, "
                "Zeremonienmeister, Ketzerinquisitor (`magister sacri palatii`)."
            ),
            type="SCQ",
            id=UUID("b49ae397-a0a4-4fc1-8c48-c01f347c4c73"),
            version_number=1,
            author_id=UUID("a8693768-244b-4b87-9972-548034df1cc3"),
            editor_id=UUID("a8693768-244b-4b87-9972-548034df1cc3"),
            group_id=UUID("0469f9f6-a1a5-4e1b-b829-48366171f7ed"),
        ),
        Question(
            question="An welchen Institutionen waren Geistliche als Kurialen tätig?",
            reference="S. 138, 139, 143.",
            anchor=(
                "S. 138 Abs. 4 - Kanzlei und Rota Romana als zentrale kuriale Behörden. "
                "S. 139 Abs. 3 - kuriale Tätigkeit als Karrieresprungbrett seit dem Schisma. "
                "S. 143 Abs. 1 - Audientiaprokuratur (Johannes von Durkheim)."
            ),
            example_answer="Päpstliche Kanzlei, Rota Romana, Pönitentiarie, Audientia.",
            type="SCQ",
            id=UUID("f270b6de-680d-40e4-942e-d5e38450c519"),
            version_number=1,
            author_id=UUID("a8693768-244b-4b87-9972-548034df1cc3"),
            editor_id=UUID("a8693768-244b-4b87-9972-548034df1cc3"),
            group_id=UUID("0469f9f6-a1a5-4e1b-b829-48366171f7ed"),
        ),
        Question(
            question="Welche Personen waren Mitglied der päpstlichen Kanzlei?",
            comment="Lv <= Lo: OWL 2 DL via `mitgliedVon` und Klasse `PäpstlicheKanzlei`.",
            reference="S. 138.",
            anchor=(
                "S. 138 Abs. 4 - namentliche Aufzählung als Bedienstete der päpstlichen Kanzlei "
                "bzw. der Rota Romana."
            ),
            example_answer="Nikolaus Hertnid, Heinrich Massheim, Antonius Molitoris, Peter Quentin, Thomas Rode.",
            type="VCQ",
            id=UUID("0c90541f-9a31-4576-a88e-57f1527fb05b"),
            version_number=1,
            author_id=UUID("a8693768-244b-4b87-9972-548034df1cc3"),
            editor_id=UUID("a8693768-244b-4b87-9972-548034df1cc3"),
            group_id=UUID("0469f9f6-a1a5-4e1b-b829-48366171f7ed"),
        ),
    ]

    mock_users = [
        User(
            id=UUID("0051e4f8-f64a-4d96-96a9-7e397205da52"),
            email="chiara@uni-jena.de",
            name="Chiara",
            password_hash=mock_password,
            password_salt=mock_salt,
            is_system_admin=False,
            is_verified=True,
        ),
        User(
            id=UUID("e0ca0b85-2960-4f47-8a1c-1acda6d13b87"),
            email="daniel@uni-jena.de",
            name="Daniel",
            password_hash=mock_password,
            password_salt=mock_salt,
            is_system_admin=False,
            is_verified=True,
        ),
        User(
            id=UUID("a3fbf0c3-35cb-4774-8eba-10bdd1cbfb0c"),
            email="malte@uni-jena.de",
            name="Malte",
            password_hash=mock_password,
            password_salt=mock_salt,
            is_system_admin=False,
            is_verified=True,
        ),
        User(
            id=UUID("a8693768-244b-4b87-9972-548034df1cc3"),
            email="admin@uni-jena.de",
            name="Admin",
            password_hash=mock_password,
            password_salt=mock_salt,
            is_system_admin=True,
            is_verified=True,
        ),
    ]

    mock_projects = [
        Project(
            id=UUID("7efa96ba-c7a9-4069-9728-dc7fa2c105fd"),
            name="Flat Earth Society",
            description="Let's see if the world is flat!",
            managers=mock_users[:2],
            engineers=mock_users[2:],
            groups=[
                Group(
                    id=UUID("a825cd37-f637-4853-bc73-97a2b01f18e7"),
                    name="It's flat!",
                    members=mock_users[:2],
                ),
                Group(
                    id=UUID("de555760-8e7b-4be5-92bb-58927517099a"),
                    name="No it's round!",
                    members=mock_users[2:],
                ),
            ],
            topics=[
                Topic(
                    id=mock_topic_id,
                    identifier="A",
                    name="Shape and evidence",
                ),
            ],
        ),
        Project(
            id=UUID("415de6a4-4d35-420a-bca2-0fde2731234d"),
            name="World's best Kebab",
            description="Let's find out what makes a great kebab!",
            managers=[mock_users[2]],
            groups=[
                Group(
                    id=UUID("b0488a1e-3768-4d34-8c90-f24f1f9036a3"),
                    name="Kebab found in Jena",
                    members=[*mock_users[:-1]],
                ),
                Group(
                    id=UUID("0469f9f6-a1a5-4e1b-b829-48366171f7ed"),
                    name="Ontology guide examples",
                    members=mock_users,
                ),
            ],
        ),
    ]

    mock_consolidations = [
        Consolidation(
            id=UUID("5daa6935-bd94-47fa-87d8-e0660ef00a79"),
            engineer_id=UUID("a8693768-244b-4b87-9972-548034df1cc3"),
            project_id=UUID("7efa96ba-c7a9-4069-9728-dc7fa2c105fd"),
            result_question_id=UUID("4f8c5f0b-5966-49d6-8d0f-a9a2e7883114"),
            questions=mock_questions[1:3],
        )
    ]

    mock_terms = [
        Term(
            id=UUID("ec1b45bc-a901-4f0e-934b-bf90cb61855a"),
            content="Reality",
            project_id=UUID("7efa96ba-c7a9-4069-9728-dc7fa2c105fd"),
        )
    ]

    mock_ratings = [
        Rating(
            rating=4,
            author_id=UUID("a8693768-244b-4b87-9972-548034df1cc3"),
            question_id=UUID("2de6c0c8-3565-4c5a-bc85-3b5971e0e452"),
        ),
        Rating(
            rating=3,
            author_id=UUID("a3fbf0c3-35cb-4774-8eba-10bdd1cbfb0c"),
            question_id=UUID("2de6c0c8-3565-4c5a-bc85-3b5971e0e452"),
        ),
    ]

    mock_comments = [
        Comment(
            comment="Das ist eine sehr gute Frage!",
            author_id=UUID("a3fbf0c3-35cb-4774-8eba-10bdd1cbfb0c"),
            question_id=UUID("92bcacac-c5bf-4fe3-a12a-d52d5f3ac1f1"),
        ),
        Comment(
            comment="Ja wirklich gut!",
            author_id=UUID("a3fbf0c3-35cb-4774-8eba-10bdd1cbfb0c"),
            question_id=UUID("92bcacac-c5bf-4fe3-a12a-d52d5f3ac1f1"),
        ),
        Comment(
            comment="Und auch ein sehr spannender Kommentar!",
            author_id=UUID("a3fbf0c3-35cb-4774-8eba-10bdd1cbfb0c"),
            question_id=UUID("92bcacac-c5bf-4fe3-a12a-d52d5f3ac1f1"),
        ),
    ]

    mock_data: list[DeclarativeBase] = [
        *mock_users,
        *mock_projects,
        *mock_terms,
        *mock_questions,
        *mock_ratings,
        *mock_consolidations,
        *mock_versions,
        *mock_comments,
    ]

    async def _add_mock_model(self, model: DeclarativeBase) -> None:
        async with session_maker() as session:
            try:
                session.add(model)
                await session.commit()
            except IntegrityError:
                ...

    async def _ensure_mock_topic_assignment(self) -> None:
        async with session_maker() as session:
            project_exists = await session.scalar(
                select(Project.id).where(Project.id == self.mock_topic_project_id)
            )
            question = await session.scalar(
                select(Question).where(Question.id == self.mock_topic_question_id)
            )
            if project_exists is None or question is None:
                return

            topic = await session.scalar(
                select(Topic).where(
                    (Topic.id == self.mock_topic_id)
                    | (
                        (Topic.project_id == self.mock_topic_project_id)
                        & (Topic.identifier == "A")
                    )
                )
            )
            if topic is None:
                topic = Topic(
                    id=self.mock_topic_id,
                    identifier="A",
                    name="Shape and evidence",
                    project_id=self.mock_topic_project_id,
                )
                session.add(topic)
                await session.flush()

            question_reservation = await session.scalar(
                select(QuestionCatalogueReservation).where(
                    QuestionCatalogueReservation.question_id == question.id
                )
            )
            if question_reservation:
                question.topic_id = question_reservation.topic_id
                question.catalogue_index = question_reservation.catalogue_index
                await session.commit()
                return

            used_catalogue_indices = set(
                (
                    await session.scalars(
                        select(QuestionCatalogueReservation.catalogue_index).where(
                            QuestionCatalogueReservation.topic_id == topic.id
                        )
                    )
                ).all()
            )
            used_catalogue_indices.update(
                (
                    await session.scalars(
                        select(Question.catalogue_index).where(
                            Question.topic_id == topic.id,
                            Question.id != question.id,
                        )
                    )
                ).all()
            )
            catalogue_index = (
                question.catalogue_index
                if question.topic_id == topic.id and question.catalogue_index
                else 1
            )
            while catalogue_index in used_catalogue_indices:
                catalogue_index += 1

            question.topic_id = topic.id
            question.catalogue_index = catalogue_index
            reservation = await session.scalar(
                select(QuestionCatalogueReservation).where(
                    QuestionCatalogueReservation.topic_id == topic.id,
                    QuestionCatalogueReservation.catalogue_index == catalogue_index,
                )
            )
            if reservation is None:
                session.add(
                    QuestionCatalogueReservation(
                        topic_id=topic.id,
                        catalogue_index=catalogue_index,
                        question_id=question.id,
                    )
                )
            else:
                reservation.question_id = question.id
            await session.commit()

    async def on_startup(self) -> None:
        async with session_maker() as session:
            seeded_admin_exists = await session.scalar(
                select(User.id).where(User.email == "admin@uni-jena.de")
            )
            if seeded_admin_exists:
                await self._ensure_mock_topic_assignment()
                return

        _ = [await self._add_mock_model(model) for model in self.mock_data]
        await self._ensure_mock_topic_assignment()
