from fastapi import FastAPI

app = FastAPI(title="Fleet Server API")

@app.get("/")
async def root():
    return {"message": "Basecamp"}

