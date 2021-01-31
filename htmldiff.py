import difflib
import sys

file1 = sys.argv[1]
file2 = sys.argv[2]
output = sys.argv[3] if len(sys.argv) == 4 else 'diff.html'

with open(file1) as file:
    content1 = file.readlines()

with open(file2) as file:
    content2 = file.readlines()

diff = difflib.HtmlDiff(wrapcolumn=60)

with open(output, 'w') as file:
    file.write(diff.make_file(content1, content2))
