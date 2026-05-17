from math import sqrt as math_sqrt

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

app = FastAPI(title="SimpleCalc API")


class BinaryInput(BaseModel):
    a: float
    b: float


class UnaryInput(BaseModel):
    a: float


@app.post("/add")
def add(payload: BinaryInput):
    return {"result": payload.a + payload.b}


@app.post("/subtract")
def subtract(payload: BinaryInput):
    return {"result": payload.a - payload.b}


@app.post("/multiply")
def multiply(payload: BinaryInput):
    return {"result": payload.a * payload.b}


@app.post("/divide")
def divide(payload: BinaryInput):
    if payload.b == 0:
        return {"result": None, "error": "Division by zero"}
    return {"result": payload.a / payload.b, "error": None}


@app.post("/power")
def power(payload: BinaryInput):
    try:
        return {"result": payload.a**payload.b}
    except Exception as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@app.post("/sqrt")
def sqrt(payload: UnaryInput):
    if payload.a < 0:
        return {"result": None, "error": "Cannot sqrt negative"}
    try:
        return {"result": math_sqrt(payload.a), "error": None}
    except Exception as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@app.get("/health")
def health():
    return {"status": "ok"}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=False)
