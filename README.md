```
usage: plagiarism.py [-h] [--input input_file_name.csv] [--output OUTPUT]

Plagiarism detection tool for Surpass. Given an ItemsDeliveredRawReport.csv
file produced by Surpass, this tool generates an Excel file. The Excel file
contains as many tabs as there are questions. For each question, the answer
for each pair of students is compared using the normalised Levenshtein similarity where 0

means completely different and 1 exactly the same.

optional arguments:
  -h, --help            show this help message and exit
  --input input_file_name.csv
                        Name of the input CSV file (defaults to
                        ItemsDeliveredRawReport.csv
  --output OUTPUT       Name of the generated Excel file (defaults to
                        plagiarism.xlsx
```
