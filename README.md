# SimpleCalc TIA — ML-Based Impacted Test Selection Demo

This repository demonstrates a production-style test automation setup for a FastAPI calculator service using Behave (Cucumber-style BDD), CI/CD on GitHub Actions, and ML-ready scenario execution metadata for impacted test selection. It shows how to collect rich test signals, run smoke and regression suites, and simulate a model selecting only the tests most likely to fail after a code change.

## Quick start
```bash
git clone <your-repo-url>
cd calculator-tia
pip install -r app/requirements.txt
behave features/                  # run all tests
behave features/ --tags=@smoke    # smoke only
```

## Architecture
```text
[Commit Push]
    │
    ▼
[GitHub Actions CI]
    ├── Job 1: Full Regression Suite (all 35 tests) → test_run_log.jsonl
    ├── Job 2: Smoke Only (@smoke tag) → fast feedback
    └── Job 3: ML Selector reads log + changed files
               → selects subset → runs selected tests only
```

## Framework structure
- **Feature files** (`features/*.feature`): business-readable acceptance criteria.
- **Step definitions** (`features/steps/*.py`): executable automation logic bound to steps.
- **Locators/constants** (`features/locators/api_locators.py`): centralized endpoints, fields, and status codes.
- **Hooks** (`features/environment.py`): lifecycle, app startup/shutdown, metadata logging.

## Extending to a real ML model
Replace `scripts/simulate_ml_selection.py` logic with:
1. Loading a trained model artifact.
2. Building features from changed files + historical test metadata.
3. Predicting per-test risk score and selecting by threshold/budget.
4. Writing selected tags/tests in the same output contract used now.

## `test_run_log.jsonl` schema
Each scenario appends one JSON line:
- `scenario` (string)
- `feature` (string)
- `tags` (array[string])
- `status` (`passed` or `failed`)
- `duration_ms` (float)
- `endpoint` (string)
- `commit_sha` (string)
- `changed_files` (string)

## Evaluation metrics
- **Failure recall**: percent of truly failing tests captured by selection.
- **Selection rate**: selected tests ÷ total tests.
- **Execution time reduction**: full suite runtime vs selected subset runtime.
- **Precision (optional)**: fraction of selected tests that actually fail.
