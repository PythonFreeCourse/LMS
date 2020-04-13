import typing

from lms import lmsnotifications
from lms.lmsdb import models
from lms.lmstests.public.identical_tests import tasks
from lms.tests import conftest

SOME_CODE = "print('Hello Word')"


class TestAutoSolutionSolver:
    def test_solve_solution_with_identical_code(self, comment: models.Comment):
        f_solution, s_solution = self._duplicate_solution_from_comment(
            comment=comment,
            first_solution_code=SOME_CODE,
            second_solution_code=SOME_CODE,
        )
        assert len(tuple(s_solution.comments)) == 0
        tasks.solve_solution_with_identical_code(s_solution.id)
        assert len(tuple(s_solution.comments)) == 1

        messages = lmsnotifications.get_messages_for_user(
            for_user=s_solution.solver)
        assert len(messages) == 1
        expected = self.get_notification_text(s_solution)
        assert expected == messages[0][models.Notification.MESSAGE_FIELD_NAME]

        messages = lmsnotifications.get_messages_for_user(
            for_user=f_solution.solver)
        assert len(messages) == 0

    @staticmethod
    def get_notification_text(solution: models.Solution) -> str:
        return f'תרגיל {solution.exercise.subject} נבדק. צפה בתוצאות!'

    def test_solve_solution_with_identical_code_not_identical_code(
            self,
            comment: models.Comment,
    ):
        _, another_solution = self._duplicate_solution_from_comment(
            comment=comment,
            first_solution_code=SOME_CODE * 2,
            second_solution_code=SOME_CODE,
        )

        assert len(tuple(another_solution.comments)) == 0
        tasks.solve_solution_with_identical_code(another_solution.id)
        assert len(tuple(another_solution.comments)) == 0
        assert another_solution.state == models.Solution.STATES.CREATED.name

    def test_check_if_other_solutions_can_be_solved(
            self,
            comment: models.Comment,
    ):
        first_solution, another_solution = (
            self._duplicate_solution_from_comment(
                comment=comment,
                first_solution_code=SOME_CODE,
                second_solution_code=SOME_CODE,
            ))

        assert len(tuple(another_solution.comments)) == 0
        tasks.check_if_other_solutions_can_be_solved(first_solution.id)
        assert len(tuple(another_solution.comments)) == 1

        messages = lmsnotifications.get_messages_for_user(
            for_user=another_solution.solver)
        assert len(messages) == 1
        expected = self.get_notification_text(another_solution)
        assert expected == messages[0][models.Notification.MESSAGE_FIELD_NAME]

    def test_check_if_other_solutions_can_be_solved_not_identical_code(
            self,
            comment: models.Comment,
    ):
        first_solution, another_solution = (
            self._duplicate_solution_from_comment(
                comment=comment,
                first_solution_code=SOME_CODE,
                second_solution_code=SOME_CODE * 2,
            ))

        assert len(tuple(another_solution.comments)) == 0
        tasks.check_if_other_solutions_can_be_solved(first_solution.id)
        assert len(tuple(another_solution.comments)) == 0

    @staticmethod
    def _duplicate_solution_from_comment(
            comment: models.Comment,
            first_solution_code: str,
            second_solution_code: str,
    ) -> typing.Tuple[models.Solution, models.Solution]:
        first_solution: models.Solution = comment.solution
        first_solution.set_state(models.Solution.STATES.DONE)
        first_solution = first_solution.refresh()
        first_solution.json_data_str = first_solution_code
        first_solution.save()
        student_user: models.User = conftest.create_student_user(index=1)
        second_solution = models.Solution.create_solution(
            exercise=first_solution.exercise,
            solver=student_user,
            json_data_str=second_solution_code,
        )
        return first_solution, second_solution
