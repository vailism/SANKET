#!/bin/bash
set -e
export PYTHONPATH=.
echo "--- 1. Extracting PDFs ---"
.venv/bin/python scripts/extract_pdfs.py --input "DATA(RAW) " --output DATA

echo "--- 2. Timelines ---"
.venv/bin/python -m sanket.timeline

echo "--- 3. Trajectories ---"
.venv/bin/python -m sanket.trajectory

echo "--- 4. Targets ---"
.venv/bin/python -m sanket.targets

echo "--- 5. Features ---"
.venv/bin/python -m sanket.features

echo "--- 6. Precompute Portfolio ---"
.venv/bin/python scripts/precompute_portfolio.py
echo "--- ALL DATA PIPELINES COMPLETED SUCESSFULLY ---"
