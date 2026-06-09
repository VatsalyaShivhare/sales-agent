"""
NexusHQ Sales Assistant API
----------------------------
Entry point. Creates tables on startup, mounts routes.
"""
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.db.database import engine, Base
from app.db.models import Message  # ensure model is registered
from app.api.routes import router
from dotenv import load_dotenv
load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(name)s  %(message)s",
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Create DB tables on startup (idempotent)
    Base.metadata.create_all(bind=engine)
    logging.getLogger("startup").info("Database tables ready.")
    yield


app = FastAPI(
    title="NexusHQ Sales Assistant API",
    description=(
        "A persistent, memory-aware AI sales assistant with tool use and self-evaluation. "
        "Built for NexusHQ B2B SaaS."
    ),
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router)
