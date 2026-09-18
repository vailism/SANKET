#!/bin/bash
echo "Waiting for extract_pdfs.py to finish..."
while pgrep -f "extract_pdfs.py" > /dev/null; do
    sleep 5
done
echo "extract_pdfs.py finished. Running downstream pipelines..."
export PYTHONPATH=.
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
