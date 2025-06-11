import os

workers = int(os.getenv("MAX_WORKERS", 2))
worker_class = "uvicorn.workers.UvicornWorker"
timeout = 30
loglevel = os.getenv("LOG_LEVEL", "info")
accesslog = "-"
errorlog = "-"
