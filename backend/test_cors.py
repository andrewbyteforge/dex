"""
Quick CORS test script to verify backend configuration.
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

# Create minimal test app
app = FastAPI()

# Add CORS middleware directly
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)

@app.get("/")
def root():
    return {"message": "CORS test working"}

@app.get("/api/v1/test")
def api_test():
    return {"status": "ok", "cors": "enabled"}

if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8001)