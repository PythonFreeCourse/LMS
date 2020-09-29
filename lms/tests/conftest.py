import datetime
import os
import random
import string
from typing import Optional

from flask.testing import FlaskClient
from peewee import SqliteDatabase
import pytest

from lms.lmsdb.models import (
    ALL_MODELS, Comment, CommentText, Exercise, Notification, Role,
    RoleOptions, SharedSolution, Solution, User,
)
from lms.extractors.base import File
from lms.lmstests.public import celery_app as public_app
from lms.lmstests.sandbox import celery_app as sandbox_app
from lms.lmsweb import routes, webapp
from lms.models import notifications


@pytest.fixture(autouse=True, scope='session')
def db_in_memory():
    """Binds all models to in-memory SQLite and creates all tables`"""
    db = SqliteDatabase(':memory:')
    db.bind(ALL_MODELS)
    db.connect()
    db.create_tables(ALL_MODELS)

    yield db

    db.drop_tables(ALL_MODELS)
    db.close()


@pytest.fixture(autouse=True, scope='session')
def populate_roles():
    for role in RoleOptions:
        Role.create(name=role.value)


@pytest.fixture(autouse=True, scope='function')
def db(db_in_memory):
    """Rollback all operations between each test-case"""
    with db_in_memory.atomic():
        yield db_in_memory
        db_in_memory.rollback()


@pytest.fixture(autouse=True, scope='session')
def celery_eager():
    public_app.conf.update(task_always_eager=True)
    sandbox_app.conf.update(task_always_eager=True)


@pytest.fixture(autouse=True, scope='session')
def webapp_configurations():
    webapp.config['SHAREABLE_SOLUTIONS'] = True
    webapp.secret_key = ''.join(
        random.choices(string.ascii_letters + string.digits, k=64),
    )


def disable_shareable_solutions():
    webapp.config['SHAREABLE_SOLUTIONS'] = False


def get_logged_user(username: str) -> FlaskClient:
    client = webapp.test_client()
    client.post(
        '/login',
        data=dict(  # noqa: S106
            username=username,
            password='fake pass',
        ),
        follow_redirects=True,
    )
    return client


def logout_user(client: FlaskClient) -> None:
    client.post('/logout', follow_redirects=True)


def create_user(
        role_name: str = RoleOptions.STUDENT.value,
        index: int = 1,
) -> User:
    return User.create(  # NOQA: S106
        username=f'{role_name}-{index}',
        fullname=f'A{role_name}',
        mail_address=f'so-{role_name}-{index}@mail.com',
        password='fake pass',
        api_key='fake key',
        role=Role.by_name(role_name),
    )


def create_student_user(index: int = 0) -> User:
    return create_user(RoleOptions.STUDENT.value, index)


def create_staff_user(index: int = 0) -> User:
    return create_user(RoleOptions.STAFF.value, index)


@pytest.fixture()
def staff_password():
    return 'fake pass'


@pytest.fixture()
def staff_user(staff_password):
    return create_staff_user()


@pytest.fixture()
def student_user():
    return create_student_user()


@pytest.fixture()
def admin_user():
    admin_role = Role.get(Role.name == RoleOptions.ADMINISTRATOR.value)
    return User.create(  # NOQA: B106, S106
        username='Yam',
        fullname='Buya',
        mail_address='mymail@mail.com',
        password='fake pass',
        api_key='fake key',
        role=admin_role,
    )


def create_notification(
        student_user: User,
        solution: Solution,
        index: int = 0,
) -> Notification:
    return Notification.create(
        user=student_user,
        kind=notifications.NotificationKind.CHECKED.value,
        message=f'Test message {index}',
        related_id=solution.id,
        action_url=f'{routes.SOLUTIONS}/{solution.id}',
    )


def create_exercise(index: int = 0) -> Exercise:
    return Exercise.create(
        subject=f'python {index}',
        date=datetime.datetime.now(),
        is_archived=False,
    )


def create_shared_solution(solution: Solution) -> str:
    return SharedSolution.create_shared_solution(solution=solution)


@pytest.fixture()
def exercise() -> Exercise:
    return create_exercise()


def create_solution(
        exercise: Exercise,
        student_user: User,
        code: Optional[str] = None,
        files: Optional[File] = None,
        hash_: Optional[str] = None,
) -> Solution:
    if code is None:
        code = ''.join(random.choices(string.printable, k=100))

    if files is None:
        files = [File('exercise.py', code)]

    return Solution.create_solution(
        exercise=exercise,
        solver=student_user,
        files=files,
        hash_=hash_,
    )


@pytest.fixture()
def solution(exercise: Exercise, student_user: User) -> Solution:
    return create_solution(exercise, student_user)


@pytest.fixture()
def comment(staff_user, solution):
    return Comment.create_comment(
        commenter=staff_user,
        file=solution.solution_files.get(),
        comment_text=CommentText.create_comment(text='very good!'),
        line_number=1,
        is_auto=False,
    )[0]


@pytest.fixture()
def notification(student_user: User, solution: Solution) -> Notification:
    return create_notification(student_user, solution)


SAMPLES_DIR = os.path.join(os.path.dirname(__file__), 'samples')
