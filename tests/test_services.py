import pytest
from app.services import validate_csv_format

def test_validate_csv_format_valid():
    content = "name,address,phone\nHospital A,Address A,12345\nHospital B,Address B,67890"
    errors = validate_csv_format(content)
    assert len(errors) == 0

def test_validate_csv_format_missing_columns():
    content = "name,phone\nHospital A,12345"
    errors = validate_csv_format(content)
    assert "CSV must contain 'name' and 'address' columns." in errors

def test_validate_csv_format_missing_values():
    content = "name,address,phone\n,Address A,12345\nHospital B,,67890"
    errors = validate_csv_format(content)
    assert "Row 1: Name is required." in errors
    assert "Row 2: Address is required." in errors

def test_validate_csv_format_exceeds_size():
    content = "name,address,phone\n" + "\n".join([f"H{i},A{i},P{i}" for i in range(25)])
    errors = validate_csv_format(content)
    assert "CSV exceeds maximum size of 20 hospitals." in errors
