from fastapi import FastAPI, UploadFile, File, Form, HTTPException, Depends, Header# Import FastAPI framework components for building the API, handling file uploads, form data, exceptions, dependency injection, and reading HTTP headers
from fastapi.middleware.cors import CORSMiddleware# Import middleware for handling Cross-Origin Resource Sharing (CORS)
from fastapi.staticfiles import StaticFiles# Import static file serving capabilities
from pydantic import BaseModel, Field# Import Pydantic for data validation and structured data models
from typing import Dict, List, Optional# Import typing utilities for type hints
import os# Import standard library modules for file system operations
import sys
import tempfile
import sqlite3# Import SQLite library for local database interactions
from datetime import datetime, timedelta# Import datetime utilities for handling dates and times

from jose import JWTError, jwt# Import JWT utilities for encoding/decoding tokens
from passlib.context import CryptContext# Import password hashing and verification context

# Add backend directory to Python path
backend_dir = os.path.dirname(os.path.abspath(__file__))# Determine backend directory path based on this file’s location
sys.path.append(backend_dir)# Add backend directory to Python’s search path so local imports work

from quiz_app import QuizApp, openai_api_key# Import main application logic (QuizApp) and API key from node_funcs module


# Instantiate core app and services
quiz_app = QuizApp(api_key=openai_api_key)# Create an instance of QuizApp with the provided API key

app = FastAPI(title="PLP API", version="1.0.0")# Create the FastAPI application with metadata
# -------------------- AUTH SETUP --------------------
JWT_SECRET = os.getenv("JWT_SECRET", "dev_secret_change_me")# Load JWT secret key from environment variable or fallback to development secret
JWT_ALGO = "HS256"# Set the algorithm used for JWT signing
ACCESS_TOKEN_EXPIRE_MINUTES = 12 * 60# Define token expiration time (12 hours in minutes)

# Prefer a pure-Python hash (pbkdf2_sha256) to avoid platform issues, but also verify existing bcrypt hashes
pwd_context = CryptContext(schemes=["pbkdf2_sha256", "bcrypt"], deprecated="auto")# Create a password hashing context using pbkdf2 (default) and bcrypt for compatibility


def hash_password(password: str) -> str:# Hash a plain-text password
    return pwd_context.hash(password)


def verify_password(password: str, password_hash: str) -> bool:# Verify if a plain-text password matches a hashed password
    try:
        return pwd_context.verify(password, password_hash)
    except Exception:
        return False


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:# Create a JWT access token with optional expiration
    to_encode = data.copy()# Copy provided data to avoid mutating the original dictionary
    expire = datetime.utcnow() + (expires_delta or timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES))# Calculate expiration time (now + provided delta or default)
    to_encode.update({"exp": expire})# Add expiration claim to token payload
    return jwt.encode(to_encode, JWT_SECRET, algorithm=JWT_ALGO)# Encode and return the JWT token


def get_db_connection():# Open a new SQLite database connection to user_learning.db
    return sqlite3.connect("user_learning.db")


def get_user_by_id(user_id: int):# Retrieve user information by their ID from the auth_users table
    conn = get_db_connection()# Connect to database
    cursor = conn.cursor()
    cursor.execute("SELECT id, name, email, role FROM auth_users WHERE id = ?", (user_id,))# Query for the user record
    row = cursor.fetchone()# Fetch the first result row
    conn.close()# Close database connection
    if not row:# Return None if user not found
        return None
    return {"id": row[0], "name": row[1], "email": row[2], "role": row[3]}# Return user details as a dictionary


def get_current_user(authorization: Optional[str] = Header(None)):# Extract the current user from the Authorization header using JWT
    if not authorization:# If no authorization header, reject request
        raise HTTPException(status_code=401, detail="Missing Authorization header")
    try:
        scheme, _, token = authorization.partition(" ")# Split header into scheme and token
        if scheme.lower() != "bearer" or not token:# Validate that scheme is Bearer and token exists
            raise HTTPException(status_code=401, detail="Invalid Authorization header")
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGO])# Decode JWT token to get payload
        user_id = int(payload.get("sub"))# Extract user ID from token's "sub" claim
    except (JWTError, ValueError):
        raise HTTPException(status_code=401, detail="Invalid or expired token")# Raise error if decoding fails or token is invalid
    user = get_user_by_id(user_id)# Fetch user from database
    if not user:# Reject if user does not exist
        raise HTTPException(status_code=401, detail="User not found")
    return user# Return authenticated user info


def is_admin(user: dict) -> bool: # Check if a given user dictionary belongs to an admin
    return bool(user) and user.get("role") == "admin"


def get_optional_user(authorization: Optional[str] = Header(None)): # Attempt to retrieve current user, but allow None if authentication fails
    try:
        return get_current_user(authorization)
    except HTTPException:
        return None


@app.on_event("startup") # Register a function to run when the FastAPI app starts
def seed_admin():
    """Ensure at least one admin exists; if none, create a default admin."""
    conn = get_db_connection()# Open database connection
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS auth_users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT NOT NULL UNIQUE,
            password_hash TEXT NOT NULL,
            role TEXT NOT NULL CHECK(role IN ('user','admin')) DEFAULT 'user',
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)# Create the auth_users table if it does not exist
    cursor.execute("SELECT COUNT(*) FROM auth_users WHERE role='admin'")# Count how many admins currently exist
    count_admin = cursor.fetchone()[0]
    if count_admin == 0:# If no admin exists, create a default admin user
        # Create default admin user
        cursor.execute(
            "INSERT OR IGNORE INTO auth_users (name, email, password_hash, role) VALUES (?, ?, ?, 'admin')",
            ("Admin", "admin@plp.local", hash_password(os.getenv("DEFAULT_ADMIN_PASSWORD", "Admin123!"))),
        )# Insert a default admin with name, email, and hashed password
        conn.commit()
    conn.close()


class RegisterRequest(BaseModel):# Pydantic model for registration requests
    name: str = Field(min_length=1)# User's name, must be at least 1 character
    email: str = Field(min_length=3)# User's email, must be at least 3 characters
    password: str = Field(min_length=6)# Password, must be at least 6 characters
    role: Optional[str] = Field(default="user")# Optional role, defaults to "user"


class AuthResponse(BaseModel): # Pydantic model for authentication responses
    token: str # JWT token for authentication
    name: str # User's name
    email: str # User's email
    role: str # User's role


class LoginRequest(BaseModel):# Pydantic model for login requests
    email: str # User's email
    password: str # User's password


@app.post("/auth/register", response_model=AuthResponse)# API endpoint for user registration
def register(payload: RegisterRequest, requester: Optional[dict] = Depends(get_optional_user)):
    # Determine desired role
    desired_role = "user"# Default role is "user"
    if requester and is_admin(requester):# If the requester is an admin, allow setting role to "user" or "admin"
        desired_role = payload.role if payload.role in ("user", "admin") else "user"

    # If no admin exists yet, allow first registered to be admin
    conn = get_db_connection()# Connect to database to check if an admin exists
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM auth_users WHERE role='admin'")
    has_admin = cursor.fetchone()[0] > 0
    if not has_admin:# If no admin exists yet, make this first registered user an admin
        desired_role = "admin"

    # Insert user
    try:# Insert the new user into the database
        cursor.execute(
            "INSERT INTO auth_users (name, email, password_hash, role) VALUES (?, ?, ?, ?)",
            (payload.name.strip(), payload.email.strip().lower(), hash_password(payload.password), desired_role),
        )
        user_id = cursor.lastrowid# Get the auto-generated user ID of the newly inserted user
        conn.commit()
        try:
            print(f"[AUTH] Registered user id={user_id} email={payload.email.strip().lower()} role={desired_role}")
        except Exception:
            pass
    except sqlite3.IntegrityError:# Email already exists, close connection and return error
        conn.close()
        raise HTTPException(status_code=400, detail="Email already registered")
    conn.close()

    token = create_access_token({"sub": str(user_id)})# Generate JWT token for the new user
    return AuthResponse(token=token, name=payload.name.strip(), email=payload.email.strip().lower(), role=desired_role)# Return authentication response


@app.post("/auth/login", response_model=AuthResponse)# API endpoint for user login
def login(payload: LoginRequest):
    conn = get_db_connection()# Connect to database and fetch user by email
    cursor = conn.cursor()
    cursor.execute("SELECT id, name, email, password_hash, role FROM auth_users WHERE email = ?", (payload.email.strip().lower(),))
    row = cursor.fetchone()
    conn.close()
    if not row: # If no matching user found, reject login
        raise HTTPException(status_code=401, detail="Invalid credentials")
    user_id, name, email, password_hash, role = row # Extract user details
    verified = verify_password(payload.password, password_hash)
    try:
        print(f"[AUTH] Login attempt email={payload.email.strip().lower()} verified={bool(verified)} scheme={'bcrypt' if password_hash.startswith('$2') else 'pbkdf2' if 'pbkdf2' in password_hash else 'unknown'}")
    except Exception:
        pass
    if not verified:# Verify password hash matches provided password
        raise HTTPException(status_code=401, detail="Invalid credentials")
    token = create_access_token({"sub": str(user_id)})# Create JWT token for authenticated user
    return AuthResponse(token=token, name=name, email=email, role=role)# Return authentication response


@app.get("/auth/me", response_model=AuthResponse)# API endpoint to get details of the currently authenticated user
def me(user=Depends(get_current_user)):
    token = create_access_token({"sub": str(user["id"])}, timedelta(minutes=10))# Create short-lived (10 min) token for current user
    return AuthResponse(token=token, name=user["name"], email=user["email"], role=user["role"])# Return authentication response with user info

# CORS for local React dev server
app.add_middleware(# Add middleware to enable CORS for local React development
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173", # Localhost with Vite dev server
        "http://127.0.0.1:5173", # Localhost IP with Vite dev server
        "http://localhost:3000", # Localhost with Create React App
        "http://127.0.0.1:3000", # Localhost IP with Create React App
    ],
    allow_credentials=True, # Allow cookies and credentials
    allow_methods=["*"],  # Allow all HTTP methods
    allow_headers=["*"], # Allow all HTTP headers
)

# Ensure uploads directory exists and mount it for static serving
os.makedirs("uploads", exist_ok=True)# Create the "uploads" directory if it doesn't already exist, to store uploaded files
app.mount("/uploads", StaticFiles(directory="uploads"), name="uploads")# Mount the "uploads" directory so it can be accessed via the /uploads URL path



class StartQuizRequest(BaseModel):# Define request model for starting a quiz
    user_name: str = Field(min_length=1)    # The name of the user starting the quiz, must be at least 1 character


class StartQuizResponse(BaseModel):# Define response model for starting a quiz
    quiz: Dict[str, Dict]# Dictionary containing quiz questions and their related metadata
    message: str# Message to be sent along with the quiz (e.g., instructions)


class SubmitQuizRequest(BaseModel):# Define request model for submitting a quiz
    user_name: str = Field(min_length=1)# The name of the user submitting the quiz
    user_answers: Dict[str, str]# A dictionary mapping question numbers to the user's submitted answers


class SubmitQuizResponse(BaseModel):# Define response model for quiz submission
    score: int# The score achieved by the user
    level: str# The assigned level (e.g., Beginner, Intermediate, Advanced)
    roadmap: List[str]# The learning roadmap generated based on the score/level


class AssignTaskRequest(BaseModel): # Define request model for assigning a task
    user_name: str = Field(min_length=1)  # The name of the user receiving the task
    user_email: str = Field(min_length=3) # The email of the user receiving the task
    duration_weeks: int = Field(default=4, ge=1, le=52) # Duration in weeks for the learning journey


class AssignTaskResponse(BaseModel):# Define response model for assigning a task
    task_id: int  # The ID of the assigned task
    task_number: int # The task number in sequence
    task_description: str # The description of the assigned task
    due_date: str # The due date for the task
    email_sent: bool  # Whether an email notification was successfully sent
    error: bool = False # Whether the assignment encountered an error
    message: Optional[str] = None # Optional message containing extra details or error info


class SubmitTaskRequest(BaseModel):# Define request model for submitting a task
    user_email: str # The email of the user submitting the task
    task_id: int# The unique ID of the task being submitted
    submission_content: str # The content of the user's task submission


class SubmitTaskResponse(BaseModel): # Define response model for submitting a task
    success: bool  # Whether the task submission was successful
    message: str  # Message containing submission confirmation or error details


@app.get("/health") # Health check endpoint to verify that the API is running
def health_check():
    return {"status": "ok"} # Return a simple status message


@app.post("/quiz/start", response_model=StartQuizResponse) # Endpoint to start a quiz
def start_quiz(payload: StartQuizRequest):
    state = {"user_name": payload.user_name} # Store user name in state for quiz tracking
    data = quiz_app.start_quiz(state) # Start the quiz using the quiz application logic
    return {"quiz": data["quiz"], "message": data["message"]} # Return the quiz questions and message


@app.post("/quiz/submit", response_model=SubmitQuizResponse) # Endpoint to submit quiz answers
def submit_quiz(payload: SubmitQuizRequest):
    user_name = payload.user_name.strip() # Remove extra spaces from the user name
    if not user_name: # Validate that user name is not empty
        raise HTTPException(status_code=400, detail="user_name is required")

    # Run the quiz graph to process answers and generate a learning roadmap
    roadmap = quiz_app.run_quiz_graph(user_name, payload.user_answers)

     # Calculate the score based on correct answers
    score = sum(
        1 for q_no, correct in quiz_app.correct_answers.items()
        if payload.user_answers.get(q_no, "").lower().strip() == correct
    )
    level = "Beginner" if score <= 3 else ("Intermediate" if score <= 6 else "Advanced")# Determine user's skill level based on score

    return {"score": score, "level": level, "roadmap": roadmap}# Return score, level, and roadmap


@app.post("/tasks/assign", response_model=AssignTaskResponse) # Endpoint to assign a task to a user based on quiz results
def assign_task(payload: AssignTaskRequest):
    # Fetch last quiz result (score/level/roadmap) inside backend the same way app.py did
    import sqlite3 # Import SQLite to interact with the database
    conn = sqlite3.connect("user_learning.db") # Connect to the database storing user learning progress
    cursor = conn.cursor() # Create a cursor object to execute SQL queries
    cursor.execute(# Fetch the last quiz result (score, level, and roadmap) for the given user
        """
        SELECT score, level, roadmap FROM users 
        WHERE name = ? ORDER BY id DESC LIMIT 1
        """,
        (payload.user_name,), # Parameterized query to avoid SQL injection
    )
    row = cursor.fetchone() # Retrieve the first (latest) matching row
    conn.close()# Close the database connection

    if not row: # If no quiz result was found, inform the user to complete the quiz first
        raise HTTPException(status_code=404, detail="No quiz results found for this user. Complete the quiz first.")

    score, level, roadmap_str = row # Unpack retrieved values from the database
    try:
        roadmap = [] if not roadmap_str else __import__("json").loads(roadmap_str)# If roadmap exists, parse it from JSON string into a Python list
    except Exception:
        roadmap = []# If parsing fails, set an empty roadmap

    result = quiz_app.assign_task_to_user(payload.user_name, payload.user_email, level, roadmap, payload.duration_weeks)# Call the quiz_app logic to assign a task to the user based on quiz data

    # If assignment returned an error (e.g., prerequisites not met), propagate gracefully
    if result.get("error"): # If there was an error in task assignment, return a response with error info
        return AssignTaskResponse(
            task_id=0, # No valid task ID when there’s an error
            task_number=result.get("task_number", 0), # Task number if provided
            task_description=result.get("task_description", ""), # Task description if available
            due_date=result.get("due_date", ""), # Due date if available
            email_sent=result.get("email_sent", False), # Whether notification email was sent
            error=True,  # Mark response as error
            message=result.get("message", "Task assignment failed"),  # Error message
        )

    return AssignTaskResponse( # If task assignment succeeded, return the task details
        task_id=int(result["task_id"]), # Convert task ID to integer
        task_number=int(result["task_number"]), # Convert task number to integer
        task_description=result["task_description"], # Task details
        due_date=result["due_date"], # Task due date
        email_sent=bool(result["email_sent"]),   # Whether email was sent
        error=False, # No error occurred
    )


@app.get("/tasks") # Endpoint to get all tasks assigned to a specific user
def get_tasks(user_email: str):
    return quiz_app.get_user_tasks(user_email) # Fetch tasks for the user using quiz_app’s logic


@app.post("/tasks/submit", response_model=SubmitTaskResponse) # Endpoint for users to submit their completed task
def submit_task(payload: SubmitTaskRequest):
    result = quiz_app.submit_user_task(payload.user_email, payload.task_id, payload.submission_content)# Call quiz_app logic to handle task submission
    return SubmitTaskResponse(success=bool(result.get("success")), message=result.get("message", "")) # Return submission success status and message


@app.get("/users")# Endpoint to retrieve all registered users (admin only)
def get_users(user=Depends(get_current_user)):
    if not is_admin(user): # Restrict access to admins only
        raise HTTPException(status_code=403, detail="Forbidden")
    return {"users": quiz_app.get_all_user_names()} # Fetch and return all user names


@app.get("/admin/user_summary")# Endpoint for admin to view a summary of a specific user’s activity
def admin_user_summary(user_email: str, user=Depends(get_current_user)):
    if not is_admin(user): # Ensure only admins can access
        raise HTTPException(status_code=403, detail="Forbidden")

    # Find user's name from auth_users if available
    conn = get_db_connection() # Connect to database to fetch user details
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM auth_users WHERE email = ?", (user_email.strip().lower(),))# Try to get the user's name from the auth_users table using their email
    row = cursor.fetchone()
    user_name = row[0] if row else None

    # Latest quiz result by user name. # Initialize quiz stats
    quiz_score = None
    quiz_level = None
    if user_name: # If user name exists, fetch their latest quiz score and level
        cursor.execute(
            """
            SELECT score, level FROM users
            WHERE name = ?
            ORDER BY id DESC LIMIT 1
            """,
            (user_name,),
        )
        qrow = cursor.fetchone()
        if qrow:
            quiz_score, quiz_level = qrow[0], qrow[1]

    # Tasks list and stats by email
    cursor.execute( # Fetch all tasks assigned to the user by email
        """
        SELECT id, task_number, task_description, assigned_date, due_date, status, submitted_date, submission_content
        FROM tasks
        WHERE user_email = ?
        ORDER BY task_number
        """,
        (user_email.strip().lower(),),
    )
    tasks = cursor.fetchall()
    conn.close()

    def to_url(path: Optional[str]) -> Optional[str]: # Helper function to convert file paths to public URLs
        if not path:
            return None
        norm = path.replace("\\", "/") # Normalize backslashes for URLs
        if norm.startswith("uploads/"): # Ensure path is inside uploads directory
            return f"/uploads/{norm.split('uploads/', 1)[1]}"
        return None

    task_items = [  # Transform raw database task data into structured dictionaries
        {
            "id": t[0],
            "task_number": t[1],
            "description": t[2],
            "assigned_date": t[3],
            "due_date": t[4],
            "status": t[5],
            "submitted_date": t[6],
            "file_url": to_url(t[7]), # Convert file path to URL
        }
        for t in tasks
    ]
    tasks_assigned = len(task_items)  # Count total tasks and completed tasks
    tasks_completed = sum(1 for t in task_items if t["status"] == "completed")

    return { # Return complete user summary
        "name": user_name,
        "email": user_email.strip().lower(),
        "quiz": {"score": quiz_score, "level": quiz_level},
        "tasks_assigned": tasks_assigned,
        "tasks_completed": tasks_completed,
        "tasks": task_items,
    }


# User self summary (non-admin). Returns latest quiz (score/level/roadmap) and tasks for the authenticated user
@app.get("/user/summary")
def user_self_summary(user=Depends(get_current_user)):
    # Identify current user
    email = user["email"].strip().lower()
    name = user.get("name")

    conn = get_db_connection()
    cursor = conn.cursor()

    # Latest quiz result by user name
    quiz_score = None
    quiz_level = None
    quiz_roadmap = []
    if name:
        cursor.execute(
            """
            SELECT score, level, roadmap FROM users
            WHERE name = ?
            ORDER BY id DESC LIMIT 1
            """,
            (name,),
        )
        qrow = cursor.fetchone()
        if qrow:
            quiz_score, quiz_level, roadmap_str = qrow[0], qrow[1], qrow[2]
            try:
                quiz_roadmap = [] if not roadmap_str else __import__("json").loads(roadmap_str)
            except Exception:
                quiz_roadmap = []

    # Tasks by email
    cursor.execute(
        """
        SELECT id, task_number, task_description, assigned_date, due_date, status, submitted_date, submission_content
        FROM tasks
        WHERE user_email = ?
        ORDER BY task_number
        """,
        (email,),
    )
    tasks = cursor.fetchall()
    conn.close()

    def to_url(path: Optional[str]) -> Optional[str]:
        if not path:
            return None
        norm = path.replace("\\", "/")
        if norm.startswith("uploads/"):
            return f"/uploads/{norm.split('uploads/', 1)[1]}"
        return None

    task_items = [
        {
            "id": t[0],
            "task_number": t[1],
            "description": t[2],
            "assigned_date": t[3],
            "due_date": t[4],
            "status": t[5],
            "submitted_date": t[6],
            "file_url": to_url(t[7]),
        }
        for t in tasks
    ]

    return {
        "name": name,
        "email": email,
        "quiz": {"score": quiz_score, "level": quiz_level, "roadmap": quiz_roadmap},
        "tasks": task_items,
    }


@app.get("/admin/users") # Endpoint for admin to list all non-admin users
def admin_list_users(user=Depends(get_current_user)):
    if not is_admin(user): # Restrict access to admins only
        raise HTTPException(status_code=403, detail="Forbidden")
    conn = get_db_connection() # Connect to database
    cursor = conn.cursor()
    cursor.execute("SELECT name, email FROM auth_users WHERE role != 'admin' ORDER BY name COLLATE NOCASE") # Fetch names and emails of all users except admins
    rows = cursor.fetchall()
    conn.close()
    users = [# Convert query results to list of dictionaries
        {"name": r[0], "email": r[1]}
        for r in rows
    ]
    return {"users": users} # Return user list

@app.delete("/admin/users/{user_email}") # Endpoint for admin to delete a user
def admin_delete_user(user_email: str, user=Depends(get_current_user)):
    if not is_admin(user): # Restrict access to admins only
        raise HTTPException(status_code=403, detail="Forbidden")
    
    # Prevent admin from deleting themselves
    if user_email.lower() == user["email"].lower():
        raise HTTPException(status_code=400, detail="Cannot delete your own account")
    
    conn = get_db_connection() # Connect to database
    cursor = conn.cursor()
    
    try:
        # Check if user exists
        cursor.execute("SELECT name, role FROM auth_users WHERE email = ?", (user_email.lower(),))
        user_to_delete = cursor.fetchone()
        
        if not user_to_delete:
            conn.close()
            raise HTTPException(status_code=404, detail="User not found")
        
        user_name, user_role = user_to_delete
        
        # Prevent deletion of other admins
        if user_role == "admin":
            conn.close()
            raise HTTPException(status_code=400, detail="Cannot delete other admin accounts")
        
        # Delete user's tasks
        cursor.execute("DELETE FROM tasks WHERE user_email = ?", (user_email.lower(),))
        tasks_deleted = cursor.rowcount
        
        # Delete user's quiz results
        cursor.execute("DELETE FROM users WHERE name = ?", (user_name,))
        quiz_results_deleted = cursor.rowcount
        
        # Delete user's progress
        cursor.execute("DELETE FROM user_progress WHERE user_email = ?", (user_email.lower(),))
        progress_deleted = cursor.rowcount
        
        # Delete user's uploaded files (if any)
        user_upload_dir = os.path.join("uploads", user_email.lower())
        if os.path.exists(user_upload_dir):
            import shutil
            shutil.rmtree(user_upload_dir)
        
        # Finally, delete the user account
        cursor.execute("DELETE FROM auth_users WHERE email = ?", (user_email.lower(),))
        user_deleted = cursor.rowcount
        
        conn.commit()
        conn.close()
        
        if user_deleted > 0:
            return {
                "success": True,
                "message": f"User {user_name} ({user_email}) deleted successfully",
                "details": {
                    "tasks_deleted": tasks_deleted,
                    "quiz_results_deleted": quiz_results_deleted,
                    "progress_deleted": progress_deleted,
                    "user_deleted": user_deleted
                }
            }
        else:
            raise HTTPException(status_code=500, detail="Failed to delete user")
            
    except Exception as e:
        conn.close()
        raise HTTPException(status_code=500, detail=f"Error deleting user: {str(e)}")


@app.get("/tasks/files") # Endpoint to get the file URLs for a user's tasks
def get_task_files(user_email: str):
    def path_to_url(path: Optional[str]) -> Optional[str]: # Helper function to convert file paths to URLs
        if not path:
            return None
        # Normalize windows backslashes and ensure it's relative to uploads
        norm = path.replace("\\", "/") # Normalize slashes
        if norm.startswith("uploads/"): # Ensure file is in uploads
            return f"/uploads/{norm.split('uploads/', 1)[1]}"
        return None

    file1 = quiz_app.get_task_file(user_email, 1) # Retrieve file paths for task 1 and task 2 from quiz_app
    file2 = quiz_app.get_task_file(user_email, 2)
    return { # Return converted URLs for each task file
        "task1": path_to_url(file1),
        "task2": path_to_url(file2),
    }


@app.post("/tasks/upload") # Endpoint to upload a file for a specific task
async def upload_task_file(
    user_email: str = Form(...), # User’s email from form data
    task_number: int = Form(...), # Task number from form data
    file: UploadFile = File(...), # Uploaded file object
):
    # Persist uploaded file temporarily, then delegate to TaskManager to save/move
    suffix = os.path.splitext(file.filename or "")[1] # Get file extension for later saving
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:  # Save uploaded file temporarily to a temp location
        content = await file.read() # Read uploaded file content
        tmp.write(content) # Write content to temp file
        tmp_path = tmp.name # Store temp file path

    try:
        dest_path = quiz_app.save_task_file(user_email, int(task_number), tmp_path)  # Pass temp file to quiz_app to handle permanent storage
    finally:
        # Cleanup temp file
        try: # Always try to delete temp file after saving
            os.remove(tmp_path)
        except Exception:
            pass # Ignore deletion errors

    # Convert to a URL under /uploads
    url_path = dest_path.replace("\\", "/") # Convert saved file path to public URL
    if url_path.startswith("uploads/"):
        url_path = f"/uploads/{url_path.split('uploads/', 1)[1]}"

    return {"file_url": url_path} # Return file URL in response




