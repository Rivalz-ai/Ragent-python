from fastapi import FastAPI
from chainlit.utils import mount_chainlit
from backend.api import app as api_router

app = FastAPI()

# Mount API router
app.mount("/api", api_router)

# Mount Chainlit application
mount_chainlit(app=app, target="rivalz_multiRX.py", path="/chainlit")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)