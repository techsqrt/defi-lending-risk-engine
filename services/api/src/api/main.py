from fastapi import FastAPI

app = FastAPI(title="Aave Risk Monitor API")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
