from strsimpy.normalized_levenshtein import NormalizedLevenshtein
from functools import partial
import numpy
import pandas

normalized_levenshtein = NormalizedLevenshtein()


def similarity(string_series, string):
    return string_series.apply(partial(normalized_levenshtein.similarity, string), convert_dtype=False)


csv = pandas.read_csv('ItemsDeliveredRawReport.csv', index_col='Reference')
names = csv.iloc[:, csv.columns.str.startswith('Naam')].dropna().iloc[0, :]
reactions = csv.iloc[:, csv.columns.str.startswith('Reactie')].replace(numpy.nan, "", regex=True)
print(reactions.head())

writer = pandas.ExcelWriter("plagiarism.xlsx", engine="xlsxwriter")

for column_name in reactions.columns:
    name = names[column_name.replace("Reactie", "Naam")]
    print("#", name)
    column = reactions.loc[:, column_name]
    try:
        df = column.apply(partial(similarity, column), convert_dtype=False)
        print(df)
        sheet_name = name.replace("[", "").replace("]", "").replace("*", "").replace(":", "").replace("?", "").replace("/", "").replace("\\", "")[:31]
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
            'max_type': 'max',
            'min_color': '#00FF00',
            'mid_color': '#FFFF00',
            'max_color': '#FF0000'
        })
    except:
        pass
    print()

writer.close()

