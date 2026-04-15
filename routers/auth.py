from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from passlib.context import CryptContext
import jwt
from datetime import datetime, timedelta
from config import get_settings
from services.bigquery_service import get_bigquery_service

router = APIRouter(prefix="/auth", tags=["auth"])

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

class LoginRequest(BaseModel):
    username: str
    password: str

class LoginResponse(BaseModel):
    access_token: str
    token_type: str

def verify_password(plain_password, hashed_password):
    return pwd_context.verify(plain_password, hashed_password)

def create_access_token(data: dict):
    settings = get_settings()
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(days=1)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, settings.api_auth_token, algorithm="HS256")
    return encoded_jwt

@router.post("/login", response_model=LoginResponse)
async def login(request: LoginRequest):
    """Autentica al usuario contra BigQuery y devuelve un JWT."""
    bq = get_bigquery_service()
    
    query = f"""
        SELECT user_id, username, password_hash
        FROM `{bq.dataset_id}.users`
        WHERE username = @username
        LIMIT 1
    """
    job_config = bq.client.query.QueryJobConfig(
        query_parameters=[
            bq.client.query.ScalarQueryParameter("username", "STRING", request.username)
        ]
    )
    
    try:
        results = list(bq.client.query(query, job_config=job_config).result())
    except Exception as e:
        # Si la tabla no existe aún, avisar
        raise HTTPException(status_code=500, detail="Database error or 'users' table not found.")

    if not results:
        raise HTTPException(status_code=401, detail="Usuario o contraseña incorrectos")

    user_row = results[0]
    
    if not verify_password(request.password, user_row.password_hash):
        raise HTTPException(status_code=401, detail="Usuario o contraseña incorrectos")

    access_token = create_access_token(data={"sub": user_row.username, "user_id": user_row.user_id})
    return {"access_token": access_token, "token_type": "bearer"}
