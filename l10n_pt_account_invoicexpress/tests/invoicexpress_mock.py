from unittest.mock import Mock


def mock_response(json, status_code=200):
    """Create a mock HTTP response with the given JSON data and status code."""
    response = Mock()
    response.json.return_value = json
    response.text = str(json)
    response.status_code = status_code
    return response


def mock_request_side_effect(method, url, **kwargs):
    """
    Mock side effect for InvoiceXpress API requests.
    Returns appropriate mock responses for different endpoints.
    """
    if "clients/find-by-code" in url:
        return mock_response(
            {"client": {"id": 999, "fiscal_id": "500000000", "name": "Customer A"}},
            status_code=200,
        )
    elif "clients.json" in url and method == "POST":
        return mock_response(
            {"client": {"id": 999, "fiscal_id": "500000000", "name": "Customer A"}},
            status_code=200,
        )
    elif "invoice_receipts.json" in url and method == "POST":
        return mock_response(
            {
                "invoice_receipt": {
                    "id": 12345678,
                    "inverted_sequence_number": "MYSEQ/123",
                }
            },
            status_code=200,
        )
    elif "transports.json" in url and method == "POST":
        return mock_response(
            {"transport": {"id": 12345678, "inverted_sequence_number": "MYSEQ/123"}},
            status_code=200,
        )
    elif "shippings.json" in url and method == "POST":
        return mock_response(
            {"shipping": {"id": 12345678, "inverted_sequence_number": "MYSEQ/123"}},
            status_code=200,
        )
    elif "devolutions.json" in url and method == "POST":
        return mock_response(
            {"devolution": {"id": 12345678, "inverted_sequence_number": "MYSEQ/123"}},
            status_code=200,
        )
    elif "change-state.json" in url and method == "PUT":
        # Detect document type from URL and return appropriate response
        if "transports" in url:
            return mock_response(
                {
                    "transport": {
                        "id": 12345678,
                        "inverted_sequence_number": "MYSEQ/123",
                    }
                },
                status_code=200,
            )
        elif "shippings" in url:
            return mock_response(
                {"shipping": {"id": 12345678, "inverted_sequence_number": "MYSEQ/123"}},
                status_code=200,
            )
        elif "devolutions" in url:
            return mock_response(
                {
                    "devolution": {
                        "id": 12345678,
                        "inverted_sequence_number": "MYSEQ/123",
                    }
                },
                status_code=200,
            )
        else:
            return mock_response(
                {
                    "invoice_receipt": {
                        "id": 12345678,
                        "inverted_sequence_number": "MYSEQ/123",
                    }
                },
                status_code=200,
            )
    return mock_response({}, status_code=200)
