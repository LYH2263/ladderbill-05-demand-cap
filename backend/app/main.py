from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app import seed
from app.engines.demand_cap import DomainValidationError
from app.routers import api

app = FastAPI(title="Ladderbill", version="0.2.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(DomainValidationError)
def _domain_error_handler(request: Request, exc: DomainValidationError):
    return JSONResponse(
        status_code=422,
        content={"error": {"code": exc.code, "field": exc.field, "message": exc.message}},
    )


@app.on_event("startup")
def _startup():
    seed.init_db()


app.include_router(api)


@app.get("/api/health")
def health():
    return {"ok": True, "project": "ladderbill"}
