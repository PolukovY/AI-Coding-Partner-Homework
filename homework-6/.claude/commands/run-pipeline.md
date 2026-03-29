# Run Pipeline

Run the multi-agent banking pipeline end-to-end.

## Steps

1. **Check prerequisites**
   - Verify `sample-transactions.json` exists in the project root (homework-6/).
   - Verify `integrator.py` exists.
   - If either is missing, report the error and stop.

2. **Clear shared directories**
   - Remove all `.json` files from `shared/input/`, `shared/processing/`, `shared/output/`, and `shared/results/`.
   - You may run: `python -c "from common.paths import *; from common.io_utils import clear_directory; [clear_directory(d) for d in (INPUT_DIR, PROCESSING_DIR, OUTPUT_DIR, RESULTS_DIR)]"`

3. **Run the pipeline**
   - Execute: `python integrator.py`
   - Capture and display the full terminal output.

4. **Show results summary**
   - Read `shared/results/pipeline_summary.json` and display:
     - Total transactions processed
     - Validated count
     - Rejected count
     - Fraud level breakdown (LOW / MEDIUM / HIGH)
     - Timestamp

5. **Report rejected transactions**
   - List every `shared/results/TXN*.json` file where `"status": "rejected"`.
   - For each rejected transaction show: transaction_id, rejection_reason, rejection_detail.

6. **Final status**
   - Confirm all 8 transactions appear in `shared/results/`.
   - Print a success or failure message.
