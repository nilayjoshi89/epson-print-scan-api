from epson_api import openapi_export


def test_committed_spec_is_current() -> None:
    assert openapi_export.SPEC_PATH.read_text(encoding="utf-8") == openapi_export.render()


def test_spec_is_available_without_api_key(client) -> None:
    assert client.get("/openapi.json", headers={"X-API-Key": ""}).status_code == 200


def test_every_operation_is_documented(client) -> None:
    spec = client.get("/openapi.json").json()
    operations = [operation for path in spec["paths"].values() for operation in path.values()]
    assert {operation["operationId"] for operation in operations} == {
        "scan_document",
        "print_document",
        "get_device_status",
    }
    for operation in operations:
        assert operation["summary"]
        assert operation["description"]
        assert operation["security"] == [{"ApiKey": []}]
        assert "401" in operation["responses"]


def test_scan_documents_binary_responses(client) -> None:
    content = client.get("/openapi.json").json()["paths"]["/scan"]["post"]["responses"]["200"]["content"]
    assert set(content) == {"image/png", "image/jpeg", "image/tiff", "application/pdf"}


def test_status_uses_ipp_field_names_in_schema(client) -> None:
    schemas = client.get("/openapi.json").json()["components"]["schemas"]
    assert "printer-state" in schemas["PrinterSection"]["properties"]
    assert "job-state" in schemas["JobSection"]["properties"]
