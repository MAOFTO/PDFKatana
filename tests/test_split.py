import io
import json

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def make_sample_pdf(num_pages=3):
    import pikepdf

    buf = io.BytesIO()
    pdf = pikepdf.Pdf.new()
    for _ in range(num_pages):
        pdf.add_blank_page(page_size=(100, 100))
    pdf.save(buf)
    buf.seek(0)
    return buf


def test_split_endpoint():
    pdf = make_sample_pdf(3)
    files = {
        "file": ("sample.pdf", pdf, "application/pdf"),
        "separators": (None, json.dumps([1, 3]), "application/json"),
    }
    response = client.post("/v1/split", files=files)
    assert response.status_code == 200
    # Check multipart/mixed response
    assert "multipart/mixed" in response.headers["content-type"]
