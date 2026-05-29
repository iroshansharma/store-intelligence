import datetime
import csv
import os
import uuid
import time
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.database import engine, Base, SessionLocal
from app.models import POSTransaction
from app.config import settings
from app.logging_config import logger

# Import Routers
from app import health, ingestion, metrics, funnel, heatmap, anomalies

# Create tables
Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="Purplle Store Intelligence API",
    description="AI-powered customer behavior telemetry and analytics system.",
    version=settings.VERSION
)

# CORS middleware config
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# JSON Request Logging Middleware
@app.middleware("http")
async def log_requests(request: Request, call_next):
    trace_id = str(uuid.uuid4())
    request.state.trace_id = trace_id
    
    start_time = time.time()
    try:
        response = await call_next(request)
    except Exception as e:
        # Prevent leaking raw tracebacks
        logger.error(f"Crash during {request.method} {request.url.path}: {str(e)}", exc_info=True)
        return JSONResponse(
            status_code=500,
            content={"detail": "An internal server error occurred."}
        )
        
    latency_ms = int((time.time() - start_time) * 1000)
    
    path = request.url.path
    store_id = None
    if "/stores/" in path:
        parts = path.split("/")
        if len(parts) >= 3:
            store_id = parts[2]
            
    logger.info(
        f"API Request completed: {request.method} {path} with status {response.status_code} in {latency_ms}ms.",
        extra={
            "trace_id": trace_id,
            "endpoint": path,
            "method": request.method,
            "latency_ms": latency_ms,
            "status_code": response.status_code,
            "store_id": store_id
        }
    )
    return response

# Custom Global Exception Handler to capture all unhandled errors cleanly
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    trace_id = getattr(request.state, "trace_id", str(uuid.uuid4()))
    logger.error(f"Global Exception Handler: {str(exc)}", extra={"trace_id": trace_id}, exc_info=True)
    return JSONResponse(
        status_code=500,
        content={
            "detail": "An unhandled server exception occurred.",
            "trace_id": trace_id
        }
    )

# Include Routers
app.include_router(health.router)
app.include_router(ingestion.router)
app.include_router(metrics.router)
app.include_router(funnel.router)
app.include_router(heatmap.router)
app.include_router(anomalies.router)

# Seed CSV on Startup
@app.on_event("startup")
def startup_populate():
    db = SessionLocal()
    try:
        # Seed from csv
        csv_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "sample_data", "pos_transactions.csv")
        if not os.path.exists(csv_path):
            logger.warning(f"Seed file not found at {csv_path}. Skipping seeding transactions.")
            return
            
        # Clear existing transactions to ensure dynamic updates are loaded on startup
        db.query(POSTransaction).delete()
        db.commit()
            
        with open(csv_path, mode="r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            transactions = []
            for row in reader:
                dt = datetime.datetime.strptime(row["timestamp"].replace("Z", ""), "%Y-%m-%dT%H:%M:%S")
                transactions.append(
                    POSTransaction(
                        store_id=row["store_id"],
                        transaction_id=row["transaction_id"],
                        timestamp=dt,
                        basket_value_inr=float(row["basket_value_inr"])
                    )
                )
            if transactions:
                db.bulk_save_objects(transactions)
                db.commit()
                logger.info(f"Successfully seeded {len(transactions)} POS records from CSV.")
    except Exception as e:
        logger.error(f"Startup transaction seeding failed: {str(e)}")
    finally:
        db.close()
