import asyncio

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.routes import health, metrics, split
from app.core.sweeper import sweeper_task

app = FastAPI(title="PDFKatana", version="v1", docs_url="/docs", redoc_url=None)

# Allow CORS for /docs
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(split.router)
app.include_router(health.router)
app.include_router(metrics.router)


@app.on_event("startup")
async def startup_event():
    asyncio.create_task(sweeper_task())


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    return JSONResponse(
        status_code=exc.status_code,
        content={"error": exc.detail, "code": exc.status_code},
    )


# Placeholder: background tasks (e.g., sweeper)
# @app.on_event("startup")
# async def startup_event():
#     ...
