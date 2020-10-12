import logging
from typing import Optional, Tuple

from flask_babel import gettext as _  # type: ignore
import junitparser

from lms.lmsdb import models
from lms.lmstests.public.unittests import executers
from lms.lmsweb import routes
from lms.models import notifications


class UnitTestChecker:
    def __init__(
            self,
            logger: logging.Logger,
            solution_id: str,
            executor_name: str,
    ):
        self._logger = logger
        self._solution_id = solution_id
        self._executor_name = executor_name
        self._solution: Optional[models.Solution] = None
        self._exercise_auto_test: Optional[models.ExerciseTest] = None

    def initialize(self):
        self._solution = models.Solution.get_by_id(self._solution_id)
        self._exercise_auto_test = models.ExerciseTest.get_by_exercise(
            exercise=self._solution.exercise,
        )

    def run_check(self) -> None:
        self._logger.info('start run_check on solution %s', self._solution_id)
        if self._exercise_auto_test is None:
            self._logger.info('No UT for solution %s', self._solution_id)
            return
        junit_results = self._run_tests_on_solution()
        self._populate_junit_results(junit_results)
        self._logger.info('end run_check solution %s', self._solution_id)

    def _run_tests_on_solution(self):
        self._logger.info('start UT on solution %s', self._solution_id)
        python_code = self._generate_python_code()
        python_file = 'test_checks.py'
        test_output_path = 'output.xml'

        junit_results = None
        try:
            with executers.get_executor(self._executor_name) as executor:
                executor.write_file(python_file, python_code)
                executor.run_on_executor(
                    args=(
                        'pytest',
                        executor.get_file_path(python_file),
                        '--junitxml',
                        executor.get_file_path(test_output_path)),
                )
                junit_results = executor.get_file(file_path=test_output_path)
        except Exception:
            self._logger.exception('Failed to run tests on solution %s',
                                   self._solution_id)
        self._logger.info('end UT on solution %s', self._solution_id)
        return junit_results

    def _generate_python_code(self) -> str:
        # FIX: Multiple files
        assert self._solution is not None
        user_code = '\n'.join(
            file.code for file in self._solution.solution_files
        )
        assert self._exercise_auto_test is not None
        test_code = self._exercise_auto_test.code
        return f'{test_code}\n\n{user_code}'

    def _populate_junit_results(self, raw_results: str) -> None:
        assert self._solution is not None  # noqa: S101
        suites = ()
        if raw_results:
            suites = junitparser.TestSuite.fromstring(raw_results).testsuites()

        tests_ran = False
        number_of_failures = 0
        for test_suite in suites:
            failures, ran = self._handle_test_suite(test_suite)
            number_of_failures += failures
            if ran and not tests_ran:
                tests_ran = ran

        if not tests_ran:
            self._handle_failed_to_execute_tests(raw_results)
            return

        if not number_of_failures:
            return

        fail_message = _(
            'הבודק האוטומטי נכשל ב־ %(number)d דוגמאות בתרגיל "%(subject)s".',
            number=number_of_failures,
            subject=self._solution.exercise.subject,
        )
        notifications.send(
            kind=notifications.NotificationKind.UNITTEST_ERROR,
            user=self._solution.solver,
            related_id=self._solution.id,
            message=fail_message,
            action_url=f'{routes.SOLUTIONS}/{self._solution_id}',
        )

    def _handle_failed_to_execute_tests(self, raw_results: str) -> None:
        self._logger.info('junit invalid results (%s) on solution %s',
                          raw_results, self._solution_id)
        fail_user_message = _(
            'הבודק האוטומטי לא הצליח להריץ את הקוד שלך.',
        )
        models.SolutionExerciseTestExecution.create_execution_result(
            solution=self._solution,
            test_name=models.ExerciseTestName.FATAL_TEST_NAME,
            user_message=fail_user_message,
            staff_message=_('אחי, בדקת את הקוד שלך?'),
        )
        notifications.send(
            kind=notifications.NotificationKind.UNITTEST_ERROR,
            user=self._solution.solver,
            related_id=self._solution.id,
            message=fail_user_message,
            action_url=f'{routes.SOLUTIONS}/{self._solution_id}',
        )

    def _handle_test_suite(
            self,
            test_suite: junitparser.TestSuite,
    ) -> Tuple[int, bool]:
        number_of_failures = 0
        tests_ran = False
        for case in test_suite:
            tests_ran = True
            result: junitparser.Element = case.result
            if result is None:
                self._logger.info(
                    'Case %s passed for solution %s.',
                    case.name, self._solution,
                )
                continue
            # invalid case
            message = ' '.join([
                elem[1].replace('\n', '')
                for elem in result._elem.items()
            ])
            self._logger.info('Create comment on test %s solution %s.',
                              case.name, self._solution_id)
            number_of_failures += 1
            models.SolutionExerciseTestExecution.create_execution_result(
                solution=self._solution,
                test_name=case.name,
                user_message=message,
                staff_message=result._elem.text,
            )
        return number_of_failures, tests_ran
