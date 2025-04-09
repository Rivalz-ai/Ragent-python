from fastapi import FastAPI
from chainlit.utils import mount_chainlit
from backend.api import app as api_router
from fastapi import APIRouter, Depends
from typing import List, Dict
import httpx
from fastapi.staticfiles import StaticFiles
from fastapi import Request
from fastapi.responses import HTMLResponse
from chainlit.context import init_http_context
from fastapi.middleware.cors import CORSMiddleware
app = FastAPI()


app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allow all origins
    allow_credentials=True,
    allow_methods=["*"],  # Allow all HTTP methods
    allow_headers=["*"],  # Allow all headers
)

# Mount API router
app.mount("/api", api_router)

# Mount Chainlit application
mount_chainlit(app=app, target="rivalz_multiRX.py", path="/chat")

# Serve static files from the "public" directory
app.mount("/public", StaticFiles(directory="public"), name="public")


# New API endpoint to fetch projects
api_app_router = APIRouter()

async def get_projects(authen_key: str, page: int = 1, page_size: int = 10) -> Dict:
    """
    Fetches projects from the Rivalz API.
    """
    url = f"https://staging-rome-api-v2.rivalz.ai/agent/rx/swarm?authen_key={authen_key}&page={page}&page_size={page_size}"
    async with httpx.AsyncClient() as client:
        response = await client.get(url)
        return response.json()

@api_app_router.get("/projects")
async def list_projects(authen_key: str, page:int = 1, page_size:int =10) -> Dict:
    """
    Lists projects with pagination.
    """
    projects = await get_projects(authen_key=authen_key, page= page, page_size = page_size)
    return projects

app.mount("/api_app", api_app_router)

# Route to serve the index.html file
@app.get("/", response_class=HTMLResponse)
async def read_root():
    with open("public/index.html", "r") as f:
        return HTMLResponse(content=f.read(), status_code=200)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
