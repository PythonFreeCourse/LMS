import enum
import random
import secrets
import string
import typing
from datetime import datetime

from flask_login import UserMixin
from peewee import (  # noqa: I201
    BooleanField,
    CharField,
    Check,
    DateTimeField,
    ForeignKeyField,
    IntegerField,
    ManyToManyField,
    TextField,
)
from playhouse.signals import Model, pre_save  # noqa: I201
from werkzeug.security import (  # noqa: I201
    check_password_hash,
    generate_password_hash,
)

from lms.lmsdb import database_config  # noqa: I100


database = database_config.get_db_instance()


class RoleOptions(enum.Enum):
    STUDENT = 'Student'
    STAFF = 'Staff'
    ADMINISTRATOR = 'Administrator'

    def __str__(self):
        return self.value


class BaseModel(Model):
    class Meta:
        database = database


class Role(BaseModel):
    name = CharField(unique=True, choices=(
        (RoleOptions.ADMINISTRATOR.value,
         RoleOptions.ADMINISTRATOR.value),
        (RoleOptions.STAFF.value, RoleOptions.STAFF.value),
        (RoleOptions.STUDENT.value, RoleOptions.STUDENT.value),
    ))

    def __str__(self):
        return self.name

    @classmethod
    def get_student_role(cls):
        return cls.get(Role.name == RoleOptions.STUDENT.value)

    @classmethod
    def get_staff_role(cls):
        return cls.get(Role.name == RoleOptions.STAFF.value)

    @classmethod
    def by_name(cls, name):
        if name.startswith('_'):
            raise ValueError('That could lead to a security issue.')
        role_name = getattr(RoleOptions, name.upper()).value
        return cls.get(name=role_name)

    @property
    def is_student(self):
        return self.name == RoleOptions.STUDENT.value

    @property
    def is_staff(self):
        return self.name == RoleOptions.STAFF.value

    @property
    def is_administrator(self):
        return self.name == RoleOptions.ADMINISTRATOR.value

    @property
    def is_manager(self):
        return self.is_staff or self.is_administrator


class User(UserMixin, BaseModel):
    username = CharField(unique=True)
    fullname = CharField()
    mail_address = CharField(unique=True)
    password = CharField()
    role = ForeignKeyField(Role, backref='users')

    def is_password_valid(self, password):
        return check_password_hash(self.password, password)

    @classmethod
    def get_system_user(cls) -> 'User':
        instance, _ = cls.get_or_create(**{
            cls.mail_address.name: 'linter-checks@python.guru',
            User.username.name: 'linter-checks@python.guru',
        }, defaults={
            User.fullname.name: 'Checker guru',
            User.role.name: Role.get_staff_role(),
            User.password.name: cls.random_password(),
        })
        return instance

    @classmethod
    def random_password(cls) -> str:
        return ''.join(random.choices(string.printable.strip()[:65], k=12))

    def __str__(self):
        return f'{self.username} - {self.fullname}'


@pre_save(sender=User)
def on_save_handler(model_class, instance, created):
    """Hashes password on creation/save"""

    # If password changed then it won't start with hash's method prefix
    is_password_changed = not instance.password.startswith('pbkdf2:sha256')
    if created or is_password_changed:
        instance.password = generate_password_hash(instance.password)


class Exercise(BaseModel):
    subject = CharField()
    date = DateTimeField()
    users = ManyToManyField(User, backref='exercises')
    is_archived = BooleanField()
    notebook_num = IntegerField(default=0)
    order = IntegerField(default=0)

    def __str__(self):
        return self.subject


class Solution(BaseModel):
    exercise = ForeignKeyField(Exercise, backref='solutions')
    solver = ForeignKeyField(User, backref='solutions')
    checker = ForeignKeyField(User, null=True, backref='solutions')
    is_checked = BooleanField(default=False)
    grade = IntegerField(
        default=0, constraints=[Check('grade <= 100'), Check('grade >= 0')],
    )
    submission_timestamp = DateTimeField()
    json_data_str = TextField()

    @property
    def code(self):
        return self.json_data_str

    @property
    def comments(self):
        return Comment.select().join(Solution).filter(Comment.solution == self)

    @classmethod
    def solution_exists(
            cls,
            exercise: Exercise,
            solver: User,
            json_data_str: str,
    ):
        return cls.select().filter(
            cls.exercise == exercise,
            cls.solver == solver,
            cls.json_data_str == json_data_str,
        ).exists()

    @classmethod
    def create_solution(
        cls,
        exercise: Exercise,
        solver: User,
        json_data_str='',
    ):
        return cls.create(**{
            cls.exercise.name: exercise,
            cls.solver.name: solver,
            cls.submission_timestamp.name: datetime.now(),
            cls.json_data_str.name: json_data_str,
        })

    @classmethod
    def next_unchecked(cls):
        unchecked_exercises = cls.select().where(cls.is_checked == False)  # NOQA: E712, E501
        try:
            return unchecked_exercises.dicts().get()
        except cls.DoesNotExist:
            return {}

    @classmethod
    def next_unchecked_of(cls, exercise_id):
        try:
            return cls.select().where(
                (cls.is_checked == 0) & (exercise_id == cls.exercise),
            ).dicts().get()
        except cls.DoesNotExist:
            return {}


class CommentText(BaseModel):
    text = TextField(unique=True)
    flake8_key = TextField(null=True)

    @classmethod
    def create_comment(
            cls, text: str, flake_key: typing.Optional[str] = None,
    ) -> 'CommentText':
        instance, created = CommentText.get_or_create(**{
            CommentText.text.name: text,
        }, defaults={
            CommentText.flake8_key.name: flake_key,
        })
        return instance


class Comment(BaseModel):
    commenter = ForeignKeyField(User, backref='comments')
    timestamp = DateTimeField(default=datetime.now)
    line_number = IntegerField(constraints=[Check('line_number >= 1')])
    comment = ForeignKeyField(CommentText)
    solution = ForeignKeyField(Solution)
    is_auto = BooleanField(default=False)

    @classmethod
    def create_comment(
            cls,
            commenter: User,
            line_number: int,
            comment_text: CommentText,
            solution: Solution,
            is_auto: bool,
    ) -> 'Comment':
        return cls.get_or_create(
            commenter=commenter,
            line_number=line_number,
            comment=comment_text,
            solution=solution,
            is_auto=is_auto,
        )

    @classmethod
    def by_solution(cls, solution_id: int):
        return Comment.select(
            Comment, CommentText.text,
            CommentText.flake8_key, CommentText.id,
        ).join(CommentText).where(
            Comment.solution == solution_id,
        )

    @classmethod
    def get_solutions(cls, solution_id: int) -> typing.Sequence[dict]:
        return tuple(cls.by_solution(solution_id).dicts())


def generate_password():
    randomizer = secrets.SystemRandom()
    length = randomizer.randrange(9, 16)
    password = randomizer.choices(string.printable[:66], k=length)
    return ''.join(password)


def create_demo_users():
    print('First run! Here are some users to get start with:')  # noqa: T001
    fields = ['username', 'fullname', 'mail_address', 'role']
    student_role = Role.by_name('Student')
    admin_role = Role.by_name('Administrator')
    entities = [
        ['lmsadmin', 'Admin', 'lms@pythonic.guru', admin_role],
        ['user', 'Student', 'student@pythonic.guru', student_role],
    ]

    for entity in entities:
        user = dict(zip(fields, entity))
        password = generate_password()
        User.create(**user, password=password)
        print(f"User: {user['username']}, Password: {password}")  # noqa: T001


def create_basic_roles():
    for role in RoleOptions:
        Role.create(name=role.value)


ALL_MODELS = BaseModel.__subclasses__()
