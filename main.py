from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import logging
import os
from datetime import datetime
import uuid
import asyncio

app = FastAPI(title="Cognivex", version="1.0.0")

# ====================== 
# CONFIGURATION 
# ====================== 

# Load API keys securely from environment
API_KEYS = os.getenv("API_KEYS", "key-acme-123,key-beta-456").split(",")
ALLOWED_ORIGINS = os.getenv("ALLOWED_ORIGINS", "https://yourdomain.com").split(",")

# ====================== 
# SECURITY 
# ====================== 

security = HTTPBearer()

async def resolve_customer(credentials: HTTPAuthorizationCredentials = Depends(security)):
    """Authenticate customer using API key in Authorization header."""
    if credentials.credentials not in API_KEYS:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API key"
        )
    # Extract customer ID from API key (e.g., "key-acme-123" -> "acme")
    customer_id = credentials.credentials.split("-")[1]
    return customer_id

# ====================== 
# MIDDLEWARE 
# ====================== 

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["POST", "GET"],
    allow_headers=["Authorization"],
)

# ====================== 
# LOGGING 
# ====================== 

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# ====================== 
# MODELS 
# ====================== 

class InferenceRequest(BaseModel):
    """Validated inference request."""
    features: list[float]
    model_name: str = "baseline-v1"

class InferenceResponse(BaseModel):
    """Inference response."""
    customer: str
    request_id: str
    model: str
    prediction: str
    timestamp: str

# ====================== 
# AUDIT LOGGING 
# ====================== 

async def audit_log(customer_id: str, model: str, request_id: str, status: str = "success"):
    """Log audit trail asynchronously."""
    record = {
        "request_id": request_id,
        "customer_id": customer_id,
        "model": model,
        "status": status,
        "timestamp": datetime.utcnow().isoformat()
    }
    # Log without exposing sensitive token values
    logger.info(f"Audit: {record}")
    await asyncio.sleep(0)  # Non-blocking

# ====================== 
# INFERENCE 
# ====================== 

async def baseline_predict(data: dict) -> dict:
    """Run baseline model inference."""
    try:
        # Placeholder for actual model inference
        return {"prediction": "ok", "input": data}
    except Exception as e:
        logger.error(f"Prediction error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Inference failed"
        )

async def route_inference(data: dict, customer_id: str, request_id: str) -> dict:
    """Route inference request to appropriate model."""
    model = "baseline-v1"
    
    try:
        result = await baseline_predict(data)
        await audit_log(customer_id, model, request_id, "success")
        return result
    except Exception as e:
        await audit_log(customer_id, model, request_id, "error")
        raise

# ====================== 
# API ENDPOINTS 
# ====================== 

@app.get("/")
def root():
    """Health check root endpoint."""
    return {"status": "Cognivex running", "version": "1.0.0"}

@app.get("/health")
def health():
    """Health check endpoint."""
    return {"status": "ok", "timestamp": datetime.utcnow().isoformat()}

@app.post("/v1/infer", response_model=InferenceResponse)
async def infer(
    data: InferenceRequest,
    customer_id: str = Depends(resolve_customer)
) -> InferenceResponse:
    """
    Run inference with tenant isolation.
    
    Args:
        data: Inference request with features
        customer_id: Authenticated customer from API key
    
    Returns:
        InferenceResponse with prediction results
    """
    request_id = str(uuid.uuid4())
    
    try:
        result = await route_inference(data.dict(), customer_id, request_id)
        
        return InferenceResponse(
            customer=customer_id,
            request_id=request_id,
            model=data.model_name,
            prediction=result["prediction"],
            timestamp=datetime.utcnow().isoformat()
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Request {request_id} failed: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error"
        )

# ====================== 
# ERROR HANDLERS 
# ====================== 

@app.exception_handler(HTTPException)
async def http_exception_handler(request, exc):
    """Custom HTTP exception handler."""
    logger.warning(f"HTTP {exc.status_code}: {exc.detail}")
    return {
        "detail": exc.detail,
        "status_code": exc.status_code
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)