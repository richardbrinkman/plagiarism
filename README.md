Surpass plagiarism detection tool
=================================

Command line version
--------------------

```
usage: plagiarism.py [-h] [--input input_file_name.csv]
                     [--output output_file_name.xlsx] [--no-ansi]

Plagiarism detection tool for Surpass. Given an ItemsDeliveredRawReport.csv
file produced by Surpass, this tool generates an Excel file. The Excel file
contains as many tabs as there are questions. For each question, the answers
for each pair of students are compared using the normalised Levenshtein
similarity where 0 means completely different and 1 means exactly the same.

optional arguments:
  -h, --help            show this help message and exit
  --input input_file_name.csv
                        Name of the input CSV file (defaults to
                        ItemsDeliveredRawReport.csv
  --output output_file_name.xlsx
                        Name of the generated Excel file (defaults to
                        plagiarism.xlsx
  --no-ansi             Using this option will prevent ansi colors and line
                        movements
```

Web app
-------

You can also run a webapp with `python3 web.py`. The standard port of 8080 can
be changed with setting the `PORT` environment variable. You can also start the
webapp with `PORT=80 python3 web.py`.

Blackboard plagiarism detection tool
====================================

```
usage: blackboard.py [-h] [--input assignment.zip] [--output plagiarism.xlsx]
Plagiarism detection tool for Blackboard. Given a zip file exported by
Blackboard, this tool generates an Excel file. The Excel file contains a
matrix where the assignment of each student is compared each other student.

The following file types are supported. Some require external tools to convert it to text.

.pdf: pdftotext is required
.odt, .docx: pandoc is required
.db, .sqlite: sqlite3 is required
.csv, .txt, .md or something with mime-type text/*

optional arguments:
  -h, --help            show this help message and exit
  --input assignment.zip
                        Name of the ZIP file or the directory of the unzipped
                        file
  --output plagiarism.xlsx
                        Name of the generated Excel file (defaults to
                        plagiarism.xlsx)
  --no-ansi             Using this option will prevent ansi colors and line
                        movements
```
