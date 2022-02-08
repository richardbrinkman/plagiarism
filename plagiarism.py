import argparse
import difflib
from abc import ABCMeta, abstractmethod
from functools import partial
from multiprocessing import Pipe, Pool

import magic
import numpy
import pandas
import xlsxwriter

from ansilogger import AnsiLogger

conditional_options = {
    'type': '3_color_scale',
    'min_value': 0.0,
    'mid_value': 0.5,
    'max_value': 1.0,
    'min_type': 'num',
    'mid_type': 'num',
    'max_type': 'num',
    'min_color': '#00FF00',
    'mid_color': '#FFFF00',
    'max_color': '#FF0000'
}


def get_argument_parser():
    argument_parser = argparse.ArgumentParser(description="""
        Plagiarism detection tool for Surpass and TestVision.

        Given an ItemsDeliveredRawReport.csv file produced by Surpass or
        the resultaten_antwoorden.xlsx from TestVision,
        this tool generates an Excel file. The Excel file contains as many
        tabs as there are questions. For each question, the answers for
        each pair of students are compared using the normalised Levenshtein
        similarity where 0 means completely different and 1 means exactly the
        same.
    """)
    argument_parser.add_argument("--input",
                                 default="ItemsDeliveredRawReport.csv",
                                 help="Name of the input CSV file or XLSX (defaults to ItemsDeliveredRawReport.csv",
                                 metavar="input_file_name.csv"
                                 )
    argument_parser.add_argument("--output",
                                 default="plagiarism.xlsx",
                                 help="Name of the generated Excel file (defaults to plagiarism.xlsx)",
                                 metavar="output_file_name.xlsx"
                                 )
    argument_parser.add_argument("--no-ansi",
                                 action="store_const",
                                 const=False,
                                 default=True,
                                 dest="use_ansi",
                                 help="Using this option will prevent ansi colors and line movements"
                                )
    return argument_parser


def diff_ratio(a, b):
    return difflib.SequenceMatcher(lambda x: str(x) in ' \t\n', a, b).ratio()


def similarity(string_series, string):
    return string_series.apply(partial(diff_ratio, string), convert_dtype=False)


class Source(metaclass=ABCMeta):
    @abstractmethod
    def get_names(self):
        pass

    @abstractmethod
    def student_tab(self):
        pass

    @abstractmethod
    def jobs(self):
        pass

    def average_tab(self, sheet_names):
        index = self.student_index()
        size = len(index)
        data = [
            [
                "=AVERAGE({})".format(",".join([
                    "'{}'!{}".format(
                        sheet_name,
                        xlsxwriter.worksheet.xl_rowcol_to_cell(row, column)
                    )
                    for sheet_name in sheet_names
                ]))
                for column in range(1, size + 1)
            ]
            for row in range(1, size + 1)
        ]
        df = pandas.DataFrame(data=data, index=index, columns=index, dtype=str)
        return df


class SurpassSource(Source):
    def __init__(self, input_file):
        df = pandas.read_csv(input_file, index_col='Referentie')
        self.df = df[df["Cijfer"] != "Ongeldig"]

    def get_names(self):
        return self.df.iloc[:, self.df.columns.str.startswith('Naam')].dropna().iloc[0, :]

    def get_answers(self):
        return self.df.iloc[:, self.df.columns.str.startswith('Reactie')].replace(numpy.nan, "", regex=True)

    def student_tab(self):
        return self.df[["Voornaam", "Achternaam"]]

    def jobs(self):
        names = self.get_names()
        reactions = self.get_answers()

        for column_name in reactions.columns:
            name = names[column_name.replace("Reactie", "Naam")]
            answers = reactions.loc[:, column_name]
            yield answers, name

    def student_index(self):
        return self.df.index


class TestvisionSource(Source):

    def __init__(self, input_file):
        with magic.Magic(flags=magic.MAGIC_MIME_TYPE) as m:
            mime_type = m.id_filename(input_file)
            if mime_type == 'application/csv':
                df = pandas.read_csv(input_file, index_col='KandidaatId')
            elif mime_type == 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet':
                df = pandas.read_excel(input_file, index_col='KandidaatId', sheet_name='Data')
        self.df = df[df["OngeldigePogingen"] == 0]

    def get_names(self):
        return self.df['VraagNaam'].unique()

    def student_tab(self):
        return self.df[['KandidaatWeergavenaam']].drop_duplicates()

    def jobs(self):
        for name in self.get_names():
            filtered = self.df[self.df['VraagNaam'] == name]
            if filtered['VraagVorm'].iloc[0] in ['Open', 'Invul', 'InvulNumeriek', 'MeervoudigInvul']:
                answers = filtered['antwoord']
            else:
                answers = filtered['keuzeantwoord']
            yield answers.replace(numpy.nan, ""), name

    def student_index(self):
        return self.df['KandidaatWeergavenaam'].unique()


def worker(job, client_connection):
    answers, name = job
    client_connection.send(("processing", name))
    try:
        df = answers.apply(partial(similarity, answers), convert_dtype=False)
        client_connection.send(("processed", name))
    except TypeError:
        df = None
        client_connection.send(("error", name))
    return df, name


def is_testvision_source(input_file):
    with magic.Magic(flags=magic.MAGIC_MIME_TYPE) as m:
        mime_type = m.id_filename(input_file)
        if mime_type == 'application/csv':
            with open(input_file) as file:
                first_line = file.readline()
            fields = first_line.split(',')
            return 'KandidaatId' in fields and 'antwoord' in fields and 'VraagNaam' in fields
        elif mime_type == 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet':
            return True


def source_factory(input_file):
    if is_testvision_source(input_file):
        return TestvisionSource(input_file)
    else:
        return SurpassSource(input_file)


def detect_plagiarism(input_file, output_file, client_connection):
    source = source_factory(input_file)
    writer = pandas.ExcelWriter(output_file, engine="xlsxwriter")
    source.student_tab().to_excel(writer, sheet_name="students")
    sheet_names = []

    with Pool() as pool:
        for df, name in pool.imap(partial(worker, client_connection=client_connection), source.jobs()):
            if df is not None:
                sheet_name = name.replace("[", "").replace("]", "").replace("*", "").replace(":", "").replace("?",
                                                                                                              "").replace(
                    "/", "").replace("\\", "")[-31:].lower()
                if sheet_name in sheet_names:
                    sheet_name = sheet_name[:29]
                    i = 0
                    while f"{sheet_name}{i:02d}" in sheet_names:
                        i += 1
                    sheet_name = f"{sheet_name}{i:02d}"
                sheet_names.append(sheet_name)
                df.to_excel(writer, sheet_name=sheet_name)
                rows, columns = df.shape
                worksheet = writer.sheets[sheet_name]
                worksheet.conditional_format(1, 1, rows + 1, columns + 1, conditional_options)
                client_connection.send(("finished", name))

    averages = source.average_tab(sheet_names)
    averages.to_excel(writer, sheet_name="average")
    rows, columns = averages.shape
    writer.sheets["average"].conditional_format(1, 1, rows + 1, columns + 1, conditional_options)
    writer.close()
    client_connection.send(("completed", None))


if __name__ == "__main__":
    argument_parser = get_argument_parser()
    arguments = argument_parser.parse_args()
    parent_connection, client_connection = Pipe()
    AnsiLogger(parent_connection, arguments.use_ansi).start()
    detect_plagiarism(arguments.input, arguments.output, client_connection)
