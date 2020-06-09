import argparse
from functools import partial
from multiprocessing import Pipe, Pool

import numpy
import pandas
from strsimpy.normalized_levenshtein import NormalizedLevenshtein

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
                                 help="Name of the generated Excel file (defaults to plagiarism.xlsx",
                                 metavar="output_file_name.xlsx"
                                )
    return argument_parser


def similarity(string_series, string):
    return string_series.apply(partial(normalized_levenshtein.similarity, string), convert_dtype=False)


def read_csv(input_file):
    csv = pandas.read_csv(input_file, index_col='Reference')
    names = csv.iloc[:, csv.columns.str.startswith('Naam')].dropna().iloc[0, :]
    reactions = csv.iloc[:, csv.columns.str.startswith('Reactie')].replace(numpy.nan, "", regex=True)
    return names, reactions


def jobs(input_file):
    names, reactions = read_csv(input_file)

    for column_name in reactions.columns:
        name = names[column_name.replace("Reactie", "Naam")]
        column = reactions.loc[:, column_name]
        yield column, name


def worker(job, client_connection):
    column, name = job
    print(f"{name} [processing]")
    client_connection.send(("processing", name))
    try:
        df = column.apply(partial(similarity, column), convert_dtype=False)
        print(f"{name} [processed]")
        client_connection.send(("processed", name))
    except TypeError:
        df = None
        print(f"{name} [error]")
        client_connection.send(("error", name))
    return df, name


def detect_plagiarism(input_file, output_file, client_connection):
    writer = pandas.ExcelWriter(output_file, engine="xlsxwriter")

    with Pool() as pool:
        for df, name in pool.imap(partial(worker, client_connection=client_connection), jobs(input_file)):
            if df is not None:
                sheet_name = name.replace("[", "").replace("]", "").replace("*", "").replace(":", "").replace("?", "").replace("/", "").replace("\\", "")[-31:]
                df.to_excel(writer, sheet_name=sheet_name)
                rows, columns = df.shape
                worksheet = writer.sheets[sheet_name]
                worksheet.conditional_format(1, 1, rows + 1, columns + 1, {
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
                })
                print(f"{name} [done]")
                client_connection.send(("done", name))

    writer.close()
    client_connection.send(("completed", None))


if __name__ == "__main__":
    argument_parser = get_argument_parser()
    arguments = argument_parser.parse_args()
    _, client_connection = Pipe()
    detect_plagiarism(arguments.input, arguments.output, client_connection)
