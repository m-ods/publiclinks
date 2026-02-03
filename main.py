import os
import uuid
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

from fastapi import FastAPI, Request, UploadFile, HTTPException, Depends
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware
from authlib.integrations.starlette_client import OAuth
import httpx

import database
import r2
import dub

# Config
SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret-key-change-me")
GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID")
GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET")
ALLOWED_EMAIL_DOMAIN = os.getenv("ALLOWED_EMAIL_DOMAIN", "assemblyai.com")
BASE_URL = os.getenv("BASE_URL", "http://localhost:8000")
R2_PUBLIC_URL = os.getenv("R2_PUBLIC_URL", "").rstrip("/")

# Initialize app
app = FastAPI(title="publiclinks")
app.add_middleware(SessionMiddleware, secret_key=SECRET_KEY)

# OAuth setup (lazy initialization)
oauth = OAuth()

@app.on_event("startup")
async def setup_oauth():
    oauth.register(
        name="google",
        client_id=GOOGLE_CLIENT_ID,
        client_secret=GOOGLE_CLIENT_SECRET,
        server_metadata_url="https://accounts.google.com/.well-known/openid-configuration",
        client_kwargs={"scope": "openid email profile"},
    )

# Initialize database on startup
@app.on_event("startup")
async def startup():
    database.init_db()


# Healthcheck for Railway
@app.get("/health")
async def healthcheck():
    return {"status": "ok"}


# Auth helpers
def get_current_user(request: Request) -> dict | None:
    """Get current user from session."""
    user_id = request.session.get("user_id")
    if not user_id:
        return None
    return database.get_user_by_id(user_id)


def require_auth(request: Request) -> dict:
    """Dependency that requires authentication."""
    user = get_current_user(request)
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated")
    return user


# Auth routes
@app.get("/auth/login")
async def login(request: Request):
    """Redirect to Google OAuth."""
    redirect_uri = f"{BASE_URL}/auth/callback"
    return await oauth.google.authorize_redirect(request, redirect_uri)


@app.get("/auth/callback")
async def auth_callback(request: Request):
    """Handle Google OAuth callback."""
    try:
        token = await oauth.google.authorize_access_token(request)
        user_info = token.get("userinfo")
        
        if not user_info:
            raise HTTPException(status_code=400, detail="Failed to get user info")
        
        email = user_info.get("email", "")
        
        # Check email domain
        if not email.endswith(f"@{ALLOWED_EMAIL_DOMAIN}"):
            return HTMLResponse(
                content=f"""
                <!DOCTYPE html>
                <html>
                <head><title>Access Denied</title></head>
                <body style="font-family: monospace; padding: 40px; max-width: 600px; margin: 0 auto;">
                    <h1>Access Denied</h1>
                    <p>Only @{ALLOWED_EMAIL_DOMAIN} accounts are allowed.</p>
                    <p>You tried to sign in with: {email}</p>
                    <a href="/">Back to home</a>
                </body>
                </html>
                """,
                status_code=403,
            )
        
        # Create or update user
        user = database.get_or_create_user(
            user_id=user_info.get("sub"),
            email=email,
            name=user_info.get("name"),
            picture=user_info.get("picture"),
        )
        
        # Set session
        request.session["user_id"] = user["id"]
        
        return RedirectResponse(url="/", status_code=302)
        
    except Exception as e:
        print(f"Auth error: {e}")
        raise HTTPException(status_code=400, detail="Authentication failed")


@app.get("/auth/logout")
async def logout(request: Request):
    """Clear session and logout."""
    request.session.clear()
    return RedirectResponse(url="/", status_code=302)


@app.get("/auth/me")
async def get_me(user: dict = Depends(require_auth)):
    """Get current user info."""
    return {
        "id": user["id"],
        "email": user["email"],
        "name": user["name"],
        "picture": user["picture"],
    }


# File API routes
@app.get("/api/files")
async def list_files(user: dict = Depends(require_auth)):
    """List all uploaded files."""
    files = database.get_all_files()
    return {"files": files}


@app.post("/api/files")
async def upload_file(request: Request, file: UploadFile, user: dict = Depends(require_auth)):
    """Upload a file to R2."""
    if not file.filename:
        raise HTTPException(status_code=400, detail="No filename provided")
    
    # Read file content
    content = await file.read()
    
    # Generate unique key
    ext = os.path.splitext(file.filename)[1]
    unique_id = str(uuid.uuid4())[:8]
    r2_key = f"{unique_id}-{file.filename}"
    
    # Upload to R2
    try:
        r2_url = r2.upload_file(content, r2_key, file.content_type or "application/octet-stream")
    except Exception as e:
        print(f"R2 upload error: {e}")
        raise HTTPException(status_code=500, detail="Failed to upload file")
    
    # Create database record
    db_file = database.create_file(
        user_id=user["id"],
        filename=file.filename,
        r2_key=r2_key,
        content_type=file.content_type or "application/octet-stream",
        size_bytes=len(content),
    )
    
    # Create dub.co short link (using our proxy URL for auth)
    proxy_url = f"{BASE_URL}/f/{r2_key}"
    dub_url = await dub.create_short_link(proxy_url)
    
    if dub_url:
        database.update_file_dub_url(db_file["id"], dub_url)
        db_file["dub_url"] = dub_url
    
    return {
        "id": db_file["id"],
        "filename": db_file["filename"],
        "r2_key": db_file["r2_key"],
        "dub_url": db_file["dub_url"],
        "proxy_url": proxy_url,
    }


@app.delete("/api/files/{file_id}")
async def delete_file(file_id: int, user: dict = Depends(require_auth)):
    """Delete a file."""
    file = database.get_file_by_id(file_id)
    if not file:
        raise HTTPException(status_code=404, detail="File not found")
    
    # Delete from R2
    try:
        r2.delete_file(file["r2_key"])
    except Exception as e:
        print(f"R2 delete error: {e}")
        # Continue anyway to clean up database
    
    # Delete from database
    database.delete_file(file_id)
    
    return {"success": True}


# File serving (auth required)
@app.get("/f/{r2_key:path}")
async def serve_file(r2_key: str, request: Request):
    """Serve a file (requires authentication)."""
    user = get_current_user(request)
    if not user:
        # Redirect to login, then back to this file
        return RedirectResponse(url=f"/auth/login?next=/f/{r2_key}", status_code=302)
    
    file = database.get_file_by_r2_key(r2_key)
    if not file:
        raise HTTPException(status_code=404, detail="File not found")
    
    try:
        content, content_type = r2.get_file(r2_key)
        return Response(
            content=content,
            media_type=content_type,
            headers={
                "Content-Disposition": f'inline; filename="{file["filename"]}"',
            },
        )
    except Exception as e:
        print(f"R2 get error: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve file")


# Serve static files and main page
@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    """Serve the main page."""
    with open("static/index.html", "r") as f:
        return HTMLResponse(content=f.read())


app.mount("/static", StaticFiles(directory="static"), name="static")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
