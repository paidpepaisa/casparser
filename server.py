"""
server.py — FastAPI HTTP wrapper around the casparser library.

Exposes a single endpoint:
  POST /parse-cas
    - Accepts a multipart/form-data upload with:
        file     : the CAS PDF (required)
        password : PDF password as a query param (optional)
    - Returns the parsed CAS data as JSON.

Run with:
  uv run uvicorn server:app --reload --port 8000
"""

import io

from fastapi import FastAPI, File, HTTPException, Query, UploadFile
from fastapi.middleware.cors import CORSMiddleware

import casparser
from casparser.exceptions import ParserException

app = FastAPI(
    title="CAS Parser API",
    description="HTTP wrapper around the casparser library for parsing CAMS/KFintech/NSDL/CDSL CAS PDFs.",
    version=casparser.__version__,
)

# Allow the Rails dev server (localhost:3000) to call this API directly from
# the browser during development. Tighten origins in production.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000", "https://wealth-analysis.onrender.com"],
    allow_methods=["POST"],
    allow_headers=["*"],
)


@app.get("/health")
def health():
    """Simple liveness check."""
    return {"status": "ok", "casparser_version": casparser.__version__}


@app.post("/parse-cas")
async def parse_cas(
    file: UploadFile = File(..., description="CAS PDF file"),
    password: str = Query(default="", description="PDF password (if encrypted)"),
):
    """
    Parse a CAS (Consolidated Account Statement) PDF and return structured JSON.

    The response shape mirrors casparser's CASData model:
      {
        "statement_period": { "from": "...", "to": "..." },
        "file_type": "CAMS" | "KARVY" | "NSDL" | "CDSL",
        "cas_type": "DETAILED" | "SUMMARY",
        "investor_info": { ... },
        "folios": [ { "folio": "...", "amc": "...", "schemes": [ ... ] } ]
      }
    """
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are accepted.")

    content = await file.read()
    if not content:
        raise HTTPException(status_code=400, detail="Uploaded file is empty.")

    try:
        cas_data = casparser.read_cas_pdf(io.BytesIO(content), password)
        return cas_data.model_dump(by_alias=True)
    except ParserException as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Unexpected error: {exc}") from exc