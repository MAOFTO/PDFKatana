from fastapi import APIRouter, Response
from prometheus_client import CONTENT_TYPE_LATEST, Counter, Histogram, generate_latest

router = APIRouter()

split_duration_seconds = Histogram(
    "split_duration_seconds",
    "Time taken for PDF split requests",
)
split_pages_total = Counter(
    "split_pages_total",
    "Total number of pages split",
)


@router.get("/metrics")
def metrics():
    data = generate_latest()
    return Response(content=data, media_type=CONTENT_TYPE_LATEST)
