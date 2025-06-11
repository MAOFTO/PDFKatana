from fastapi import APIRouter, Response

router = APIRouter()


@router.get("/v1/health")
@router.get("/v1/healthz")
def health():
    return {"status": "ok"}


@router.get("/v1/ready")
@router.get("/v1/readyz")
def ready():
    return Response(status_code=204)
