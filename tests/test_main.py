import pytest
from httpx import AsyncClient, ASGITransport
from app.main import app
from uuid import UUID

@pytest.mark.asyncio
async def test_health_check():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.get("/")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}

@pytest.mark.asyncio
async def test_validate_csv_endpoint():
    csv_content = "name,address,phone\nHospital A,Address A,12345"
    files = {"file": ("test.csv", csv_content, "text/csv")}
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.post("/hospitals/validate-csv", files=files)
    assert response.status_code == 200
    assert response.json()["valid"] is True

@pytest.mark.asyncio
async def test_bulk_create_invalid_file():
    files = {"file": ("test.txt", "some text", "text/plain")}
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.post("/hospitals/bulk", files=files)
    assert response.status_code == 400
    assert response.json()["detail"] == "Only CSV files are allowed."
