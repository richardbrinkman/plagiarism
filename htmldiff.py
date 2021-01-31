import difflib
import sys
from blackboard import convert_file_to_string

content1 = str(convert_file_to_string(sys.argv[1])).split('\n')
content2 = str(convert_file_to_string(sys.argv[2])).split('\n')
output = sys.argv[3] if len(sys.argv) == 4 else 'diff.html'

diff = difflib.HtmlDiff(wrapcolumn=60)

with open(output, 'w') as file:
    file.write(diff.make_file(content1, content2))
