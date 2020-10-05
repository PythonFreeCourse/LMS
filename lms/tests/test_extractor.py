from io import BufferedReader, BytesIO
from tempfile import SpooledTemporaryFile
from typing import Iterator, Tuple
from zipfile import ZipFile

from flask import json
from werkzeug.datastructures import FileStorage

import lms.extractors.base as extractor
import lms.extractors.ziparchive as zipfilearchive
from lms.lmsdb.models import User
from lms.tests import conftest
from lms.tests.conftest import SAMPLES_DIR


class TestExtractor:
    IPYNB_NAME = 'upload-1-2.ipynb'
    IGNORE_FILES_ZIP_NAME = 'Upload_123.zip'
    PY_NAMES = ('code1.py', 'code2.py')
    ZIP_FILES = ('Upload_1.zip', 'zipfiletest.zip')

    def setup(self):
        self.ipynb_file = self.ipynb_file()
        self.pyfiles_files = list(self.py_files())
        self.zipfile_file = next(self.zip_files((self.IGNORE_FILES_ZIP_NAME,)))
        self.ipynb_storage = FileStorage(self.ipynb_file)
        self.pyfiles_storage = [
            FileStorage(pyfile)
            for pyfile in self.pyfiles_files
        ]
        self.zipfile_storage = self.create_zipfile_storage(
            self.zipfile_file, self.IGNORE_FILES_ZIP_NAME,
        )
        self.zipfiles_extractor_files = list(self.zip_files(self.ZIP_FILES))
        self.zipfiles_extractors_bytes_io = list(self.get_bytes_io_zip_files())

    def teardown(self):
        self.ipynb_file.close()
        self.zipfile_file.close()
        for py_file in self.pyfiles_files:
            py_file.close()
        for zip_file in self.zipfiles_extractor_files:
            zip_file.close()
        for bytes_io, _ in self.zipfiles_extractors_bytes_io:
            bytes_io.close()

    def ipynb_file(self):
        return open(f'{SAMPLES_DIR}/{self.IPYNB_NAME}', encoding='utf-8')

    def py_files(self):
        for file_name in self.PY_NAMES:
            yield open(f'{SAMPLES_DIR}/{file_name}')

    @staticmethod
    def zip_files(filenames: Tuple[str, ...]) -> Iterator[BufferedReader]:
        for filename in filenames:
            yield open(f'{SAMPLES_DIR}/{filename}', 'br')

    @staticmethod
    def create_zipfile_storage(
        opened_file: BufferedReader, filename: str,
    ) -> FileStorage:
        spooled = SpooledTemporaryFile()
        spooled.write(opened_file.read())
        zip_file_storage = FileStorage(spooled)
        zip_file_storage.filename = filename
        opened_file.seek(0)
        return zip_file_storage

    def get_zip_filenames(self):
        the_zip = ZipFile(f'{SAMPLES_DIR}/{self.IGNORE_FILES_ZIP_NAME}')
        return the_zip.namelist()

    def test_notebook(self):
        results = list(extractor.Extractor(self.ipynb_storage))
        assert len(results) == 5
        assert results[0][0] == 3141
        assert results[1][0] == 2
        assert results[2][1][0].path.endswith('.py')
        assert results[3][1][0].path.endswith('.html')
        assert results[4][1][0].path.endswith('.py')
        solution = extractor.Extractor(self.pyfiles_storage[1]).file_content
        solution = solution.replace('# Upload 3141', '')
        assert results[0][1][0].code == solution.strip()

    def test_py(self):
        for file in self.pyfiles_storage:
            solutions = list(extractor.Extractor(file))
            assert len(solutions) == 1
            assert solutions[0][0] == 3141

    def test_zip_ignore_files(self):
        result = zipfilearchive.Ziparchive(to_extract=self.zipfile_storage)
        exercises = list(result.get_exercises())[0][1]
        exercises_paths = [exercise.path for exercise in exercises]
        assert len(exercises) == 8
        original_zip_filenames = self.get_zip_filenames()

        assert all(
            '__pycache__/foo.py' not in exercise_path
            for exercise_path in exercises_paths
        )

        assert any(
            '__pycache__/foo.py' in filename
            for filename in original_zip_filenames
        )

    def get_bytes_io_zip_files(self) -> Iterator[Tuple[BytesIO, str]]:
        for file, name in zip(self.zipfiles_extractor_files, self.ZIP_FILES):
            yield BytesIO(file.read()), name

    def test_zip(self, student_user: User):
        conftest.create_exercise()
        conftest.create_exercise()
        conftest.create_exercise()
        conftest.create_exercise(is_archived=True)

        client = conftest.get_logged_user(username=student_user.username)

        # Uploading a multiple zip solutions file
        upload_response = client.post('/upload', data=dict(
            file=self.zipfiles_extractors_bytes_io[1],
        ))
        json_response_upload = json.loads(
            upload_response.get_data(as_text=True),
        )
        assert len(json_response_upload['exercise_misses']) == 1
        assert len(json_response_upload['exercise_matches']) == 2
        assert upload_response.status_code == 200

        # Uploading a zip file with a same solution exists in the previous zip
        second_upload_response = client.post('/upload', data=dict(
            file=self.zipfiles_extractors_bytes_io[0],
        ))
        assert second_upload_response.status_code == 400
