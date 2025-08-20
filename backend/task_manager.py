# task_manager.py
import sqlite3
import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime, timedelta
from openai import OpenAI
from typing import List
import shutil

from dotenv import load_dotenv

# Load environment variables
load_dotenv()
openai_api_key = os.getenv("OPENAI_API_KEY")
email_password = os.getenv("EMAIL_PASSWORD")
email_address = os.getenv("EMAIL_ADDRESS")

# Gracefully handle missing environment configuration by disabling related features instead of raising
# hard errors that would prevent the API (and auth endpoints) from running
OPENAI_AVAILABLE = bool(openai_api_key)
EMAIL_AVAILABLE = bool(email_password and email_address)

class TaskManager: #Define a TaskManager class to handle tasks, database setup, and OpenAI integration
    def __init__(self, api_key: str): # Constructor method to initialize TaskManager with OpenAI API key
        self.client = OpenAI(api_key=api_key) if api_key else None # Create an OpenAI client instance using the provided API key
        self.setup_database() # Initialize and set up all required database tables
    
    def setup_database(self): # Method to create database tables if they do not exist
        """Setup database tables for tasks and progress tracking"""
        conn = sqlite3.connect("user_learning.db") # Connect to (or create) the SQLite database file 'user_learning.db'
        cursor = conn.cursor() 
        
        # Create a 'users' table for storing quiz results and user roadmap
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            score INTEGER,
            level TEXT,
            roadmap TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
        """)

        # Create auth_users table for application login/auth (if not exists)
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS auth_users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT NOT NULL UNIQUE,
            password_hash TEXT NOT NULL,
            role TEXT NOT NULL CHECK(role IN ('user','admin')) DEFAULT 'user',
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
        """)

        # Create tasks table
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS tasks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_name TEXT NOT NULL,
            user_email TEXT NOT NULL,
            task_number INTEGER NOT NULL,
            task_description TEXT NOT NULL,
            assigned_date TEXT NOT NULL,
            due_date TEXT NOT NULL,
            status TEXT DEFAULT 'pending',
            submitted_date TEXT,
            submission_content TEXT
        )
        """)
        
        # Create user_progress table
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS user_progress (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_name TEXT NOT NULL,
            user_email TEXT NOT NULL,
            quiz_score INTEGER,
            level TEXT,
            roadmap TEXT,
            last_task_assigned TEXT,
            tasks_completed INTEGER DEFAULT 0
        )
        """)
        
        conn.commit()# Save all changes to the database
        conn.close() # Close the database connection
    
    def send_email(self, to_email: str, subject: str, body: str): # Method to send an email using SMTP protocol
        """Send email using SMTP"""
        try:
            if not EMAIL_AVAILABLE:
                # Email configuration missing; skip sending and report False so callers can reflect this in UI
                print("Email config not set; skipping email send.")
                return False
            msg = MIMEMultipart('alternative')# Create a multipart email object that can hold both plain text and HTML
            msg['From'] = email_address# Set the "From" field to the sender's email address
            msg['To'] = to_email# Set the "To" field to the recipient's email address
            msg['Subject'] = subject# Set the subject of the email
            
            # Add both HTML and plain text versions
            html_part = MIMEText(body, 'html')# Create the HTML version of the email body
            msg.attach(html_part)  # Attach the HTML content to the email
            
            # Create SMTP session
            server = smtplib.SMTP('smtp.gmail.com', 587)# Connect to Gmail's SMTP server using port 587 for TLS
            server.starttls()# Start TLS encryption for secure communication
            
            # Login to the server
            server.login(email_address, email_password)# Login to the SMTP server using the sender's email and password
            
            # Send email
            text = msg.as_string() # Convert the email object to a string format ready for sending
            server.sendmail(email_address, to_email, text)# Send the email from sender to recipient
            server.quit()# Close the connection to the SMTP server
            
            print(f"Email sent successfully to {to_email}")# Confirmation message in console
            return True
            
        except smtplib.SMTPAuthenticationError: # Error handling for failed authentication (wrong email/password)
            print("SMTP Authentication failed. Check your email and app password.")
            return False
        except smtplib.SMTPRecipientsRefused:  # Error handling for invalid recipient address
            print("Recipient email address is invalid.")
            return False
        except smtplib.SMTPServerDisconnected:  # Error handling for unexpected SMTP disconnection
            print("SMTP server disconnected unexpectedly.")
            return False
        except Exception as e:  # General error handling for all other exceptions
            print(f"Email sending failed: {str(e)}")
            return False
    # Method to generate a personalized learning task using AI based on user's roadmap and progress

    def generate_task(self, user_name: str, level: str, roadmap: List[str], task_number: int, previous_task: str = None):
        """Generate AI-based task based on user's performance and roadmap"""
        # Create the base prompt that will be sent to the AI model
        if not self.client:
            # Fallback task when OpenAI is not configured
            intro = f"Initial task" if task_number == 1 else f"Follow-up task building on previous work"
            basics = "\n".join([
                "Learning Objectives:",
                "- Practice core concepts from your roadmap",
                "- Produce a small, tangible deliverable",
                "Instructions:",
                "- Pick one weak area from your roadmap and build a simple example",
                "- Document what you learned in a short README",
                "Why this matters:",
                "- Consolidates fundamentals and prepares you for the next task",
            ])
            previous = f"\nPrevious Task: {previous_task}\n" if (task_number == 2 and previous_task) else ""
            return (
                f"{intro} for {user_name} at {level} level.\n"
                f"Roadmap focus (excerpt):\n{chr(10).join(roadmap[:6])}\n"
                f"{previous}"
                f"{basics}\n"
                f"Estimated time: 2-4 hours"
            )
        prompt = f"""
        Generate a learning task for a user named {user_name} who is at {level} level.
        
        User's Learning Roadmap:
        {chr(10).join(roadmap)}
        
        Task Number: {task_number}
        """
        
        if task_number == 2 and previous_task:# If this is the second task and there was a previous task, create a follow-up task prompt
            prompt += f"""
            Previous Task: {previous_task}
            
            Generate a follow-up task that builds upon the previous task and continues the learning journey.
            """
        else:  # Otherwise, create an initial task prompt for starting the learning journey
            prompt += """
            Generate an initial task that helps the user start their learning journey based on their roadmap.
            """
        # Add detailed requirements for the AI-generated task to ensure clarity and usefulness
        prompt += """
        Requirements:
        - Task should be practical and hands-on
        - Include specific learning objectives
        - Provide clear instructions
        - Suggest resources or tools if needed
        - Make it achievable within 3-4 days
        - Include a brief explanation of why this task is important for their learning
        
        Format the response as a clear, structured task description.
        """
        
        response = self.client.chat.completions.create( # Send the constructed prompt to the OpenAI GPT-4o model for task generation
            model="gpt-4o", # Using OpenAI's GPT-4o model for better reasoning and text generation
            messages=[
                {"role": "system", "content": "You are an expert learning coach that creates personalized, practical learning tasks."},
                {"role": "user", "content": prompt}  # User's actual prompt with details
            ],
            temperature=0.7, # Adds creativity to the task generation
            max_tokens=500 # Limit the response length to 500 tokens
        )
        
        return response.choices[0].message.content.strip() # Extract the generated task text from the AI response, remove extra spaces, and return it
    
    def assign_task(self, user_name: str, user_email: str, level: str, roadmap: List[str]):# Method to assign a new learning task to a user
        """Assign a new task to the user"""
        conn = sqlite3.connect("user_learning.db")# Connect to the SQLite database
        cursor = conn.cursor()# Create a cursor object to run SQL queries
        
          # Check if the user already has any tasks assigned
        cursor.execute("""
        SELECT task_number, task_description, status FROM tasks 
        WHERE user_email = ? ORDER BY task_number DESC LIMIT 1
        """, (user_email,))
        
        result = cursor.fetchone()# Get the most recent task record for the user (if any)
        
          # If the user has no previous tasks, assign Task 1
        if not result:
            task_number = 1
            previous_task = None
        else:
            last_task_number, last_task_description, last_task_status = result# Extract last task details
            
            # Only assign task 2 if task 1 is completed
            if last_task_number == 1 and last_task_status != 'completed':# If the last assigned task was Task 1 but not completed, don't assign Task 2 yet
                return {
                    "error": True,
                    "message": "Task 1 must be completed before Task 2 can be assigned. Please submit your first task first."
                }
            elif last_task_number == 2 and last_task_status != 'completed':# If the last assigned task was Task 2 but not completed, don't assign a new task
                return {
                    "error": True,
                    "message": "You already have Task 2 assigned. Please complete it before requesting a new task."
                }
            elif last_task_number >= 2:# If the user has completed both available tasks, no new tasks can be assigned
                return {
                    "error": True,
                    "message": "You have completed all available tasks. Great job!"
                }
            
            task_number = last_task_number + 1 # Otherwise, increment the task number and store the last task description
            previous_task = last_task_description
        
        # Generate new task
        task_description = self.generate_task(user_name, level, roadmap, task_number, previous_task)# Generate a new task description using the AI model
        
        # Calculate due date (3 days from now)
        assigned_date = datetime.now().strftime("%Y-%m-%d")# Record the date the task was assigned
        due_date = (datetime.now() + timedelta(days=3)).strftime("%Y-%m-%d")# Set the due date for 3 days later
        
        # Save the newly assigned task into the database
        cursor.execute("""
        INSERT INTO tasks (user_name, user_email, task_number, task_description, assigned_date, due_date, status)
        VALUES (?, ?, ?, ?, ?, ?, 'pending')
        """, (user_name, user_email, task_number, task_description, assigned_date, due_date))
        
        task_id = cursor.lastrowid # Get the auto-generated task ID for reference
        conn.commit() # Commit the changes to the database
        conn.close() # Close the database connection
        
        # Create the subject line for the task assignment email
        subject = f"New Learning Task #{task_number} - {user_name}" # Create the HTML-formatted body of the email containing the task details
        body = f"""
        <html>
        <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
            <div style="max-width: 600px; margin: 0 auto; padding: 20px;">
                <h2 style="color: #2c3e50;">Hello {user_name}!</h2>
                <p>You have been assigned a new learning task based on your quiz performance.</p>
                
                <div style="background-color: #f8f9fa; border-left: 4px solid #007bff; padding: 15px; margin: 20px 0; border-radius: 5px;">
                    <h3 style="color: #007bff; margin-top: 0;">Task #{task_number}</h3>
                    <div style="white-space: pre-line;">{task_description}</div>
                </div>
                
                <div style="background-color: #e8f5e8; border: 1px solid #28a745; padding: 10px; border-radius: 5px; margin: 15px 0;">
                    <p style="margin: 0;"><strong>Due Date:</strong> {due_date}</p>
                </div>
                
                <p>To submit your task, please reply to this email with your work or use the submit button in the app.</p>
                
                <div style="margin-top: 30px; padding-top: 20px; border-top: 1px solid #eee;">
                    <p style="color: #666; font-size: 14px;">Keep up the great work!</p>
                </div>
            </div>
        </body>
        </html>
        """
        
        email_sent = self.send_email(user_email, subject, body) # Send the task assignment email to the user
        
        return { # Return a dictionary with task details and whether the email was sent
            "task_id": task_id,
            "task_number": task_number,
            "task_description": task_description,
            "due_date": due_date,
            "email_sent": email_sent,
            "error": False
        }
    
    def submit_task(self, user_email: str, task_id: int, submission_content: str): # Method to submit a completed task for a given user
        """Submit a completed task"""
        conn = sqlite3.connect("user_learning.db")# Connect to the SQLite database
        cursor = conn.cursor() # Create a cursor object to execute SQL commands
        
        # Update task status
        submitted_date = datetime.now().strftime("%Y-%m-%d")# Get the current date for submission record
        cursor.execute("""
        UPDATE tasks 
        SET status = 'completed', submitted_date = ?, submission_content = ?
        WHERE id = ? AND user_email = ?
        """, (submitted_date, submission_content, task_id, user_email))# Update the task status to 'completed' and store the submission content
        
        if cursor.rowcount > 0:# Check if the update affected any rows (ensures the task exists and belongs to the user)
            # Update user progress
            cursor.execute("""
            UPDATE user_progress 
            SET tasks_completed = tasks_completed + 1
            WHERE user_email = ?
            """, (user_email,))# Increment the user's "tasks_completed" count in the progress table
            
            conn.commit()
            conn.close()
            
            # Prepare the confirmation email subject.# Prepare the HTML-formatted confirmation email body
            subject = "Task Submission Confirmed"
            body = f"""
            <html>
            <body>
                <h2>Task Submission Confirmed!</h2>
                <p>Your task has been successfully submitted and recorded.</p>
                <p>We'll review your work and assign the next task soon.</p>
                <p>Keep up the excellent progress!</p>
            </body>
            </html>
            """
            
            self.send_email(user_email, subject, body) # Send the confirmation email to the user
            
            return {"success": True, "message": "Task submitted successfully!"}# Return success response
        else:
            conn.close()# Close database connection if no matching task was found or it’s already submitted
            return {"success": False, "message": "Task not found or already submitted."}# Return failure response
    
    def get_user_tasks(self, user_email: str):# Method to fetch all tasks assigned to a specific user
        """Get all tasks for a user"""
        conn = sqlite3.connect("user_learning.db")# Connect to the SQLite database
        cursor = conn.cursor()# Create a cursor to execute SQL queries
        
        cursor.execute("""
        SELECT id, task_number, task_description, assigned_date, due_date, status, submitted_date
        FROM tasks 
        WHERE user_email = ? 
        ORDER BY task_number
        """, (user_email,))  # Retrieve all tasks for the given user email, ordered by task number
        
        tasks = cursor.fetchall()# Fetch all rows from the executed query
        conn.close()# Close the database connection
        
        return [# Convert raw task tuples into a list of dictionaries for easier use in the app
            {
                "id": task[0], # Unique task ID
                "task_number": task[1], # Sequential task number
                "description": task[2],  # Task details/description
                "assigned_date": task[3], # Date the task was assigned
                "due_date": task[4], # Task deadline
                "status": task[5], # Current status (pending/completed)
                "submitted_date": task[6] # Date the task was submitted (if any)
            }
            for task in tasks
        ]

    def get_all_user_names(self): # Method to fetch all distinct user names from the users table
        """Fetch all unique user names from the users table."""
        conn = sqlite3.connect("user_learning.db")# Connect to the SQLite database
        cursor = conn.cursor()# Create a cursor to execute SQL queries
        cursor.execute("SELECT DISTINCT name FROM users")# Select distinct names to avoid duplicates
        names = [row[0] for row in cursor.fetchall()]# Convert the list of tuples into a flat list of names
        conn.close()# Close the database connection
        return names

    def save_task_file(self, user_email: str, task_number: int, file_path: str):# Method to save a file uploaded for a user's task and update the database record
        """Save uploaded file for a user's task. Store file path in tasks table."""
        # Ensure upload directory exists
        upload_dir = os.path.join("uploads", user_email, f"task_{task_number}")# Build the directory path where the uploaded file will be stored
        os.makedirs(upload_dir, exist_ok=True) # Create the directory (and parent dirs if needed) without throwing an error if it already exists
        # Copy file to upload dir
        filename = os.path.basename(file_path)# Extract just the filename from the full file path
        dest_path = os.path.join(upload_dir, filename)# Create the destination path inside the upload directory
        shutil.copy(file_path, dest_path)# Copy the uploaded file to the destination directory
        # Update DB with file path
        conn = sqlite3.connect("user_learning.db")# Connect to the SQLite database
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE tasks SET submission_content = ? WHERE user_email = ? AND task_number = ?
        """, (dest_path, user_email, task_number))# Update the task record with the path of the uploaded file
        conn.commit()
        conn.close()
        return dest_path# Return the stored file path for confirmation

    def get_task_file(self, user_email: str, task_number: int):# Method to fetch the saved file path for a given user's submitted task
        """Get the file path for a user's submitted task file."""
        conn = sqlite3.connect("user_learning.db")
        cursor = conn.cursor()
        cursor.execute("""
            SELECT submission_content FROM tasks WHERE user_email = ? AND task_number = ?
        """, (user_email, task_number))# Retrieve the stored file path for the specified task
        row = cursor.fetchone()# Fetch the first matching row
        conn.close()# Close the database connection
        if row and row[0]: # If a record is found and it has a file path, return it
            return row[0]
        return None# Otherwise, return None indicating no file was found
