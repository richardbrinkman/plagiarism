import argparse
import difflib
import magic
import os
import pandas
import re
import shutil
import subprocess
import tempfile
import zipfile
from ansilogger import AnsiLogger
from functools import lru_cache, partial
from multiprocessing import Pipe, Pool
from plagiarism import conditional_options


def pandoc_reader(filename):
    with subprocess.Popen(['pandoc',  '--output', '-', '--to',  'markdown', filename], stdout=subprocess.PIPE, stderr=subprocess.DEVNULL) as process:
        return process.stdout.read()


def pdf_reader(filename):
    with subprocess.Popen(['pdftotext', '-layout', filename, '-'], stdout=subprocess.PIPE, stderr=subprocess.DEVNULL) as process:
        return process.stdout.read()


def sqlite_reader(filename):
    with subprocess.Popen(['sqlite3', filename, '.dump'], stdout=subprocess.PIPE, stderr=subprocess.DEVNULL) as process:
        return process.stdout.read()


def text_reader(filename):
    with open(filename) as file:
        return file.read()


@lru_cache(maxsize=256)
def convert_file_to_string(filename):
    converters = {
        '^application/csv$': text_reader,
        '^application/pdf$': pdf_reader,
        '^application/vnd.oasis.opendocument.text$': pandoc_reader,
        '^application/vnd.openxmlformats-officedocument.wordprocessingml.document$': pandoc_reader,
        '^application/x-sqlite3$': sqlite_reader,
        '^text/.+$': text_reader
    }
    with magic.Magic(flags=magic.MAGIC_MIME_TYPE) as m:
        mime_type = m.id_filename(filename)
        for mime_regex, reader in converters.items():
            if re.match(mime_regex, mime_type):
                return reader(filename)
        raise RuntimeError(f'Cannot convert file {filename} with mime-type {mime_type} to text')


def shortify_name(filename):
    match = re.match(r'^.+_(?P<student_number>\d+)_(?:attempt|poging)_\d{4}(?:-\d\d){5}_(?P<filename>.+)$', filename)
    if match:
        return match['student_number'] + '_' + match['filename']
    else:
        return filename


def compare(directory, client_connection, pair):
    message = f'comparison between {shortify_name(pair[0])} and {shortify_name(pair[1])}'
    client_connection.send(('processing',  message))
    try:
        similarity = difflib.SequenceMatcher(
            lambda x: str(x) in ' \t\n',
            convert_file_to_string(os.path.join(directory, pair[0])),
            convert_file_to_string(os.path.join(directory, pair[1]))
        ).ratio()
        client_connection.send(('processed', message))
        return pair, similarity
    except RuntimeError:
        client_connection.send(('error', message))
        return pair, None


def student_tab(directory, metafiles):
    student_names = dict()
    for absolute_filename in (os.path.join(directory, file) for file in metafiles):
        with open(absolute_filename) as file:
            match = re.match(r'^(?:Name|Naam): (?P<name>.+) \((?P<student_number>\d+)\)$', file.readline().rstrip())
            if match:
                student_names[match['student_number']] = match['name']
    return pandas.DataFrame({
        'student_number': student_names.keys(),
        'name': student_names.values()
    }).set_index('student_number')


def detect_plagiarism_in_directory(directory, output_file, client_connection):
    files = os.listdir(directory)
    files.sort()
    regex = r'^.+_(?:attempt|poging)_\d{4}(?:-\d\d){5}\.txt'
    metafiles = [file for file in files if re.match(regex, file)]
    non_metafiles = [file for file in files if not re.match(regex, file)]
    df = pandas.DataFrame(index=non_metafiles, columns=non_metafiles, dtype='float32')
    with Pool() as pool:
        pairs = ((x, y) for x in non_metafiles for y in non_metafiles if x < y)
        for (x, y), similarity in pool.imap_unordered(partial(compare, directory, client_connection), pairs):
            df.loc[x, y] = similarity
            df.loc[y, x] = similarity
    students = student_tab(directory, metafiles)
    student_series = students['name']
    multi_index = pandas.MultiIndex.from_tuples(
        [(student_series[student_number], non_metafile)
         for non_metafile in non_metafiles
         for student_number in re.findall(r'^.+_(\d{6})_(?:attempt|poging)_.+$', non_metafile)
        ]
    )
    df.columns = multi_index
    df.index = multi_index
    writer = pandas.ExcelWriter(output_file, engine="xlsxwriter")
    students.to_excel(writer, sheet_name='students')
    df.to_excel(writer, sheet_name='similarity')
    rows, columns = df.shape
    worksheet = writer.sheets['similarity']
    worksheet.conditional_format(2, 1, rows + 2, columns + 1, conditional_options)
    writer.close()


def detect_plagiarism(input_file, output_file, client_connection):
    """Detect plagiarism in either a zip file or an unzipped directory.

    :param input_file A string pointing to either a zip file or an unzipped directory
    :param output_file The filename of the resulting Excel file
    """
    if zipfile.is_zipfile(input_file):
        directory = tempfile.mkdtemp(prefix="plagiarism-")
        try:
            with zipfile.ZipFile(input_file) as zip_file:
                zip_file.extractall(directory)
            detect_plagiarism_in_directory(directory, output_file, client_connection)
        finally:
            shutil.rmtree(directory)
    else:
        detect_plagiarism_in_directory(input_file, output_file, client_connection)


def get_argument_parser():
    argument_parser = argparse.ArgumentParser(description="""
        Plagiarism detection tool for Blackboard.

        Given a zip file exported by Blackboard,
        this tool generates an Excel file. The Excel file contains a matrix
        where the assignment of each student is compared each other student.

        The following file types are supported. Some require external tools to convert it to text.

        .pdf: pdftotext is required
        .odt, .docx: pandoc is required
        .db, .sqlite: sqlite3 is required
        .csv, .txt, .md or something with mime-type text/*
    """)
    argument_parser.add_argument("--input",
                                 help="Name of the ZIP file or the directory of the unzipped file",
                                 metavar="assignment.zip"
                                )
    argument_parser.add_argument("--output",
                                 default="plagiarism.xlsx",
                                 help="Name of the generated Excel file (defaults to plagiarism.xlsx)",
                                 metavar="plagiarism.xlsx"
                                )
    argument_parser.add_argument("--no-ansi",
                                 action="store_const",
                                 const=False,
                                 default=True,
                                 dest="use_ansi",
                                 help="Using this option will prevent ansi colors and line movements"
                                )
    return argument_parser


if __name__ == "__main__":
    argument_parser = get_argument_parser()
    arguments = argument_parser.parse_args()
    parent_connection, client_connection = Pipe()
    AnsiLogger(parent_connection, arguments.use_ansi).start()
    try:
        detect_plagiarism(arguments.input, arguments.output, client_connection)
    finally:
        client_connection.send(('completed', None))
