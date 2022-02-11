from io import StringIO

class TestVisionCSVSource(StringIO):
    """CSV files exported with TestVision are incorrect. This class sanitizes them.

    CSV files exported with the learning analytics tool of TestVision has an extra
    trailing semicolumn at the end of data lines but not on the first line
    containing the fields. There pandas (or any csv tool) cannot correctly read
    those files. This class strips out the trailing semicolumn.

    It can be used as follows:

    >>> import pandas as pd
    >>> df = pd.read_csv(TestVisionCSVSource('learning_analytics.csv'), encoding='latin-1', sep=';')

    This module can also be called from the command line as:

    python3 testvision_csv_sanitizer.py incorrect.csv > correct.csv
    """

    def __init__(self, input_file):
        stringbuffer = StringIO()
        header_read = False
        with open(input_file, 'rt', encoding='latin-1') as file:
            for line in file:
                if header_read:
                    line = line.rstrip(';\n') + '\n'
                stringbuffer.write(line)
                header_read = True
        super().__init__(stringbuffer.getvalue())


if __name__ == '__main__':
    from sys import argv
    print(TestVisionCSVSource(argv[1]).getvalue())
