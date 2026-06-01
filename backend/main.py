from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from contextlib import asynccontextmanager
from dotenv import load_dotenv
import traceback
import os

load_dotenv()

from db.database import create_tables
from api.routes.auth import router as auth_router
from api.routes.chat import router as chat_router
from api.routes.quiz import router as quiz_router
from api.routes.notes import router as notes_router
from api.routes.performance import router as perf_router
from api.routes.roadmap import router as roadmap_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    create_tables()
    print("✅ NeuroLearn AI backend started")
    yield


app = FastAPI(
    title="NeuroLearn AI",
    description="Adaptive learning backend",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[os.getenv("FRONTEND_URL", "http://localhost:3000")],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    error_detail = traceback.format_exc()
    print("\n❌ ERROR:\n", error_detail)
    return JSONResponse(
        status_code=500,
        content={"detail": str(exc), "traceback": error_detail},
    )


app.include_router(auth_router, prefix="/api")
app.include_router(chat_router, prefix="/api")
app.include_router(quiz_router, prefix="/api")
app.include_router(notes_router, prefix="/api")
app.include_router(perf_router, prefix="/api")
app.include_router(roadmap_router, prefix="/api")


@app.get("/api/health")
def health():
    return {"status": "ok", "service": "NeuroLearn AI"}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
