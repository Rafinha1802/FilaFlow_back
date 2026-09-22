from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

from app.core.config import CORS_ORIGINS, PROJECT_NAME, PROJECT_VERSION
from app.core.database import engine, Base
from app.seed import seed_data

from app.routers import (
    auth,
    companies,
    queues,
    tickets,
    reception,
    checkout,
    websocket
)

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: create tables and seed demo data
    Base.metadata.create_all(bind=engine)
    seed_data()
    yield
    # Shutdown

app = FastAPI(
    title=PROJECT_NAME,
    version=PROJECT_VERSION,
    description="Backend FastAPI para Gestão de Filas em Tempo Real, Recepção e Autorização de Convênios do FilaFlow",
    lifespan=lifespan
)

# CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include Routers
app.include_router(auth.router)
app.include_router(companies.router)
app.include_router(queues.router)
app.include_router(tickets.router)
app.include_router(reception.router)
app.include_router(checkout.router)
app.include_router(websocket.router)

@app.get("/api/health", tags=["Health"])
def health_check():
    return {
        "status": "healthy",
        "service": PROJECT_NAME,
        "version": PROJECT_VERSION
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="127.0.0.1", port=8000, reload=True)
