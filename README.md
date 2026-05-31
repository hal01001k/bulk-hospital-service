# Hospital Bulk Processing System

A bulk processing API system built with FastAPI and Python 3.12, designed to handle CSV uploads of hospital records, parse and validate them, and perform individual creations and batch activation using the live Hospital Directory API.

## Project Structure

```
├── app/
│   ├── __init__.py
│   ├── config.py         # App configurations using Pydantic Settings
│   ├── main.py           # FastAPI routes and server definition
│   ├── models.py         # Pydantic schemas/models
│   └── services.py       # Core CSV parser, validator, and api batch integration
├── tests/
│   ├── __init__.py
│   ├── test_main.py      # End-to-end integration tests for endpoints
│   └── test_services.py  # Unit tests for CSV parser and validation
├── Dockerfile            # Python 3.12-slim multi-stage setup
├── docker-compose.yml    # Development orchestrator
├── run.py                # App runner script with native env fix
├── run_tests.py          # Pytest runner wrapper with native env fix
└── requirements.txt      # Dependency specification
```

## Running the Application Locally

1. Set up a virtual environment:
   ```bash
   python -m venv venv
   source venv/bin/activate
   pip install -r requirements.txt
   ```
2. Start the server:
   ```bash
   python run.py
   ```
   The application will be running at `http://localhost:8000`.

3. Run the test suite:
   ```bash
   python run_tests.py
   ```

## Running with Docker

1. Build and run via Docker Compose:
   ```bash
   docker-compose up --build
   ```
   This exposes the API on `http://localhost:8000`.

## Features implemented

- **Bulk Create (`POST /hospitals/bulk`)**: Accepts CSV upload up to 20 items, parses concurrently, and executes batch creation and activation on the real API.
- **CSV Validation (`POST /hospitals/validate-csv`)**: Immediate syntactic structural check on headers, column counts, missing values, and file size.
- **Bulk Progress Polling (`GET /hospitals/batch/{batch_id}/status`)**: Real-time polling endpoint to track total, processed, and failed rows in an upload batch. Fully integrated in-memory tracker.
