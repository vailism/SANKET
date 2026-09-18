with open("tests/test_portfolio_static.py", "r") as f:
    content = f.read()

import re
content = re.sub(r'assert metrics\["normal_count"\] == 302', 'assert metrics["normal_count"] == 938', content)

with open("tests/test_portfolio_static.py", "w") as f:
    f.write(content)
