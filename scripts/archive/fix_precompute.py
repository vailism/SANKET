with open("scripts/precompute_portfolio.py", "r") as f:
    content = f.read()

# Replace my custom is_genuine_project definition with an import
import_statement = "from sanket.portfolio import is_genuine_project\n"

# find def is_genuine_project to return True block
import re
content = re.sub(r'def is_genuine_project\(pid: str, name: str\).*?return True\n', '', content, flags=re.DOTALL)

# Add the import
content = content.replace("from sanket.inference import load_inference_engine, get_risk_tier",
                          "from sanket.inference import load_inference_engine, get_risk_tier\n    from sanket.portfolio import is_genuine_project")

with open("scripts/precompute_portfolio.py", "w") as f:
    f.write(content)
