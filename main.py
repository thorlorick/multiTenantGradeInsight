from fastapi import FastAPI
from app.routers import health

app = FastAPI()

app.include_router(health.router)

@app.get("/")
def root():
    return {"message": "Multi-Tenant Grade Insight API is up"}
