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

from chainlit.user import User
from chainlit.utils import mount_chainlit
from chainlit.server import _authenticate_user
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


from rAgent.utils import Logger
@app.post("/custom-auth")
async def custom_auth(request: Request):
    try:
        Logger.info("Starting custom authentication")
        data = await request.json()
        project_id = data.get("project_id")
        project_name = data.get("project_name")
        if not project_id or not project_name:
            return {"error": "Both 'project_id' and 'project_name' are required."}

        # Ensure required fields are present
        if not project_id.strip() or not project_name.strip():
            return {"error": "'project_id' and 'project_name' cannot be empty or whitespace."}

        payload = {'project_id': project_id, 'project_name': project_name}
        user = User(identifier=project_name, metadata=payload)
        Logger.info(f"User created: {user}")
        response = await _authenticate_user(request,user)
        Logger.info("Authentication successful")
        return response
    except Exception as e:
        Logger.error(f"Error in custom_auth: {e}")
        return {"error": str(e)}

# Mount Chainlit application
mount_chainlit(app=app, target="rivalz_orchestration.py", path="/chat")

# Serve static files from the "public" directory
app.mount("/public", StaticFiles(directory="public"), name="public")


# New API endpoint to fetch projects
api_app_router = APIRouter()

from chainlit.user import User
from chainlit.utils import mount_chainlit
from chainlit.server import _authenticate_user
from rAgent.utils import Logger
@app.get("/custom-auth")
async def custom_auth(request: Request):
    try:
        Logger.info("Starting custom authentication")
        project_id = "67b465519870d36dd0fd9818"
        project_name = "Qualoo"
        payload = {'project_id': project_id, 'project_name': project_name}
        user = User(identifier=project_name, metadata=payload)
        Logger.info(f"User created: {user}")
        response = await _authenticate_user(request, user)
        Logger.info("Authentication successful")
        return response
    except Exception as e:
        Logger.error(f"Error in custom_auth: {e}")
        return {"error": str(e)}

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
