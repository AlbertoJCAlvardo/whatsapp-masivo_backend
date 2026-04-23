from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from passlib.context import CryptContext
import jwt
from datetime import datetime, timedelta
from google.cloud import bigquery
from config import get_settings
from services.bigquery_service import get_bigquery_service

router = APIRouter(prefix="/auth", tags=["auth"])

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

import uuid

class LoginRequest(BaseModel):
    username: str
    password: str

class UserCreate(BaseModel):
    username: str
    password: str
    role: str = "agent"

@router.post("/register")
async def register(request: UserCreate):
    """Registra un nuevo usuario en BigQuery con contraseña cifrada."""
    bq = get_bigquery_service()
    
    # Hash de la contraseña inmediatamente
    hashed_pwd = pwd_context.hash(request.password)
    user_id = str(uuid.uuid4())
    
    try:
        bq.add_user(user_id, request.username, hashed_pwd, role=request.role)
        return {"message": "Usuario registrado exitosamente", "username": request.username}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

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
        SELECT user_id, username, password_hash, role
        FROM `{bq.dataset_id}.users`
        WHERE username = @username
        LIMIT 1
    """
    job_config = bigquery.QueryJobConfig(
        query_parameters=[
            bigquery.ScalarQueryParameter("username", "STRING", request.username)
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

    # Si el usuario es legacy y no tiene role, asumimos admin, de lo contrario usamos su role
    user_role = getattr(user_row, 'role', None) or "admin"
    access_token = create_access_token(data={"sub": user_row.username, "user_id": user_row.user_id, "role": user_role})
    return {"access_token": access_token, "token_type": "bearer"}
