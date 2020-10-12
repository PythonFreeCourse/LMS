from flask import request
from flask_login import current_user

from lms.lmsdb.models import CommentText, Exercise, Note, User
from lms.models.errors import ForbiddenPermission, UnprocessableRequest


def delete():
    note_id = int(request.args.get('noteId'))
    note_ = Note.get_or_none(Note.id == note_id)
    if note_.creator.id != current_user.id and note_.is_private:
        raise ForbiddenPermission(
            "You aren't allowed to access this page.", 403,
        )
    if note_ is not None:
        note_.delete_instance()


def create(user: User) -> Note:
    note_text = request.args.get('note', '')
    note_exercise = request.args.get('exercise', '')
    privacy = request.args.get('privacy')
    if not note_text:
        raise UnprocessableRequest('Empty notes are not allowed.', 422)
    new_note_id = CommentText.create_comment(text=note_text).id

    return Note.create(
        creator=User.get_or_none(User.id == current_user.id),
        user=user,
        note=new_note_id,
        exercise=Exercise.get_or_none(Exercise.subject == note_exercise),
        privacy=Note.get_privacy_level(int(privacy)),
    )
