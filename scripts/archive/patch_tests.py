import re

with open("tests/test_api.py", "r") as f:
    content = f.read()

content = content.replace(
    'pids = ["180100210", "150100650", "220100133", "180100262", "150101111"]',
    'pids = ["N08000004", "N08000005", "N16000090"]'
)
content = content.replace(
    'pids = ["180100210", "150100650", "220100133"]',
    'pids = ["N08000004", "N08000005", "N16000090"]'
)

with open("tests/test_api.py", "w") as f:
    f.write(content)
