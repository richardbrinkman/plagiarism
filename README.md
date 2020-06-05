```
usage: plagiarism.py [-h] [--input input_file_name.csv]
                     [--output output_file_name.xlsx]

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
```
