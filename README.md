# Hospital Bulk Processing System

A bulk processing API built with FastAPI and Python 3.12.

This service accepts hospital records as CSV uploads, validates and parses them, then performs asynchronous bulk operations against an external live Hospital Directory API. The implementation includes create, update, delete, and batch activation flows, with polling support for long-running uploads.

## Project Structure

```
├── app/
│   ├── __init__.py
│   ├── config.py         # App configurations using Pydantic Settings
│   ├── main.py           # FastAPI routes and server definition
│   ├── models.py         # Pydantic schemas/models
│   └── services.py       # Core CSV parser, validator, and API batch integration
├── tests/
│   ├── __init__.py
│   ├── test_main.py      # End-to-end integration tests for endpoints
│   └── test_services.py  # Unit tests for CSV parser and validation
├── Dockerfile            # Python 3.12-slim multi-stage setup
├── docker-compose.yml    # Development orchestrator
├── run.py                # App runner script with native env fix
├── run_tests.py          # Pytest runner wrapper with native env fix
├── requirements.txt      # Dependency specification
└── test_deployment.py    # Live deployment endpoint verification script
```

## Key Features

- **Asynchronous bulk processing** using FastAPI `BackgroundTasks` so large uploads and batch operations do not block the HTTP request.
- **CSV validation** before processing to catch missing fields, incorrect headers, and malformed rows.
- **Batch state tracking** with `GET /hospitals/batch/{batch_id}/status` so clients can poll progress and verify completion.
- **Bulk update support** to send multiple hospital update requests in a single batch.
- **Bulk delete support** to remove many hospitals with a single API call.
- **Batch activation** support for existing batch IDs so created hospitals can be activated after creation.

## API Endpoints

- `GET /`
  - Health check endpoint returning `{ "status": "ok" }`.
- `POST /hospitals/bulk`
  - Upload a CSV file to create hospitals in bulk.
  - Returns `202 Accepted` with `batch_id`, `status`, and `eta_seconds`.
- `POST /hospitals/validate-csv`
  - Upload a CSV file for validation only.
  - Returns `valid: true|false` and a list of validation errors.
- `GET /hospitals/batch/{batch_id}/status`
  - Poll the current status of a bulk upload batch.
  - Returns counts, processed rows, results, and activation state.
- `POST /hospitals/bulk-update`
  - Submit many hospital updates in one request.
  - Returns `202 Accepted` and a `batch_id` for the update batch.
- `POST /hospitals/bulk-delete`
  - Submit multiple hospital IDs for deletion.
  - Returns `202 Accepted` and a deletion batch ID.
- `PATCH /hospitals/batch/{batch_id}/activate`
  - Activate hospitals created in the specified batch.
  - Returns activation status and a message.
- `POST /hospitals/batch/{batch_id}/resume`
  - Retry failed or incomplete hospitals for an existing batch.
  - Useful when a previous batch ended with failures or partial completion.

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
3. Open the FastAPI docs at `http://localhost:8000/docs` to interact with the endpoints.
4. Run the test suite:
   ```bash
   python run_tests.py
   ```

## Running with Docker

1. Build and run via Docker Compose:
   ```bash
   docker-compose up --build
   ```
2. Access the API at `http://localhost:8000`.

## Deployment and Render

This project is intended for deployment to a rendering service such as Render. The current example deployment base URL is:

```bash
https://bulk-hospital-service.onrender.com
```

If your Render deployment uses a different domain, substitute it in the test script command below.

## Live Deployment Verification

Use the included script to verify the rendered deployment and exercise the main endpoints.

```bash
python test_deployment.py --base-url https://bulk-hospital-service.onrender.com
```

If you deploy to a different host:

```bash
python test_deployment.py --base-url https://your-deployment-url.example.com
```

### Sample curl workflow

These curl commands demonstrate a typical deployment workflow against the live app.

1. Health check:

```bash
curl -X GET https://bulk-hospital-service.onrender.com/
```

2. Upload a CSV for bulk creation:

```bash
curl -X POST https://bulk-hospital-service.onrender.com/hospitals/bulk \
  -F "file=@hospitals.csv"
```

3. Poll the batch status (replace `<batch_id>`):

```bash
curl -X GET https://bulk-hospital-service.onrender.com/hospitals/batch/<batch_id>/status
```

4. Bulk update hospitals:

```bash
curl -X POST https://bulk-hospital-service.onrender.com/hospitals/bulk-update \
  -H "Content-Type: application/json" \
  -d '{"hospitals":[{"id":1,"name":"Updated Hospital 1"}]}'
```

5. Activate a batch (replace `<batch_id>`):

```bash
curl -X PATCH https://bulk-hospital-service.onrender.com/hospitals/batch/<batch_id>/activate
```

6. Bulk delete hospitals:

```bash
curl -X POST https://bulk-hospital-service.onrender.com/hospitals/bulk-delete \
  -H "Content-Type: application/json" \
  -d '{"hospital_ids":[1,2,3]}'
```

### What the script checks

- service health check
- bulk hospital creation via CSV upload
- batch status polling until completion
- bulk update of hospitals created by the test batch
- activation request for the created batch
- bulk delete request for updated hospitals

## Notes for reviewers

- The app uses background tasks for long-running operations, returning `202 Accepted` for bulk create/update/delete requests.
- Batch progress is tracked in memory and returned via a dedicated status endpoint.
- The live deployment script is intentionally simple so it can be used as a one-shot verification step for Render or other hosting platforms.
