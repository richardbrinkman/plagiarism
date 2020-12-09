import argparse
from functools import partial
from multiprocessing import Pipe, Pool

import numpy
import pandas
import xlsxwriter
from strsimpy.normalized_levenshtein import NormalizedLevenshtein

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

normalized_levenshtein = NormalizedLevenshtein()


def get_argument_parser():
    argument_parser = argparse.ArgumentParser(description="""
        Plagiarism detection tool for Surpass.

        Given an ItemsDeliveredRawReport.csv file produced by Surpass,
        this tool generates an Excel file. The Excel file contains as many
        tabs as there are questions. For each question, the answers for
        each pair of students are compared using the normalised Levenshtein
        similarity where 0 means completely different and 1 means exactly the
        same.
    """)
    argument_parser.add_argument("--input",
                                 default="ItemsDeliveredRawReport.csv",
                                 help="Name of the input CSV file (defaults to ItemsDeliveredRawReport.csv",
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


def similarity(string_series, string):
    return string_series.apply(partial(normalized_levenshtein.similarity, string), convert_dtype=False)


def read_csv(input_file):
    df = pandas.read_csv(input_file, index_col='Referentie')
    return df[df["Cijfer"] != "Ongeldig"]


def get_names(csv):
    return csv.iloc[:, csv.columns.str.startswith('Naam')].dropna().iloc[0, :]


def get_reactions(csv):
    return csv.iloc[:, csv.columns.str.startswith('Reactie')].replace(numpy.nan, "", regex=True)


def student_tab(csv):
    return csv[["Voornaam", "Achternaam"]]


def average_tab(csv, sheet_names):
    referenties = csv.index
    size = len(referenties)
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
    df = pandas.DataFrame(data=data, index=referenties, columns=referenties, dtype=str)
    return df


def jobs(csv):
    names = get_names(csv)
    reactions = get_reactions(csv)

    for column_name in reactions.columns:
        name = names[column_name.replace("Reactie", "Naam")]
        column = reactions.loc[:, column_name]
        yield column, name


def worker(job, client_connection):
    column, name = job
    client_connection.send(("processing", name))
    try:
        df = column.apply(partial(similarity, column), convert_dtype=False)
        client_connection.send(("processed", name))
    except TypeError:
        df = None
        client_connection.send(("error", name))
    return df, name


def detect_plagiarism(input_file, output_file, client_connection):
    csv = read_csv(input_file)
    writer = pandas.ExcelWriter(output_file, engine="xlsxwriter")
    student_tab(csv).to_excel(writer, sheet_name="students")
    sheet_names = []

    with Pool() as pool:
        for df, name in pool.imap(partial(worker, client_connection=client_connection), jobs(csv)):
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

    averages = average_tab(csv, sheet_names)
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
