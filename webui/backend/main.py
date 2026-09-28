import os
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse

from webui.backend.api.v1 import (
    gdrive,
    jobs,
    library,
    preview,
    subtitles,
    system,
    upload,
)
from webui.backend.config import FRONTEND_DIST_DIR, ensure_directories


@asynccontextmanager
async def lifespan(app: FastAPI):
    ensure_directories()
    yield


app = FastAPI(
    title="ViralCutter API",
    version="1.0.0",
    description="FastAPI Backend for ViralCutter Video Generation Engine",
    lifespan=lifespan,
)

# CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# API Routers
app.include_router(jobs.router, prefix="/api/v1/jobs", tags=["jobs"])
app.include_router(upload.router, prefix="/api/v1/upload", tags=["upload"])
app.include_router(preview.router, prefix="/api/v1/preview", tags=["preview"])
app.include_router(library.router, prefix="/api/v1/library", tags=["library"])
app.include_router(subtitles.router, prefix="/api/v1/subtitles", tags=["subtitles"])
app.include_router(gdrive.router, prefix="/api/v1/gdrive", tags=["gdrive"])
app.include_router(system.router, prefix="/api/v1/system", tags=["system"])


@app.get("/api/v1/health", tags=["system"])
async def health_check():
    """Health check endpoint."""
    return {"status": "ok"}


# Serve static frontend SPA if built
if FRONTEND_DIST_DIR.exists() and (FRONTEND_DIST_DIR / "index.html").exists():
    app.mount("/assets", StaticFiles(directory=str(FRONTEND_DIST_DIR / "assets")), name="assets")

    @app.get("/{full_path:path}")
    async def serve_spa(full_path: str):
        file_path = FRONTEND_DIST_DIR / full_path
        if file_path.is_file():
            return FileResponse(file_path)
        return FileResponse(FRONTEND_DIST_DIR / "index.html")
else:
    @app.get("/")
    async def root_fallback():
        return JSONResponse({
            "name": "ViralCutter API",
            "version": "1.0.0",
            "status": "running",
            "note": "Frontend dist not built yet. Use API endpoints at /api/v1/*",
        })


if __name__ == "__main__":
    import uvicorn
    from webui.backend.config import HOST, PORT
    uvicorn.run("webui.backend.main:app", host=HOST, port=PORT, reload=True)
