import sqlite3 # Import SQLite3 to work with a local SQLite database
import json # Import JSON to parse and store data in JSON format
import os # Import OS module to interact with the operating system (file paths, environment variables, etc.)
import smtplib # Import smtplib for sending emails via SMTP protocol
from email.mime.text import MIMEText # Import MIMEText to create plain text email content
from email.mime.multipart import MIMEMultipart # Import MIMEMultipart to create email content with multiple parts (text, HTML, attachments)
from datetime import datetime, timedelta # Import datetime and timedelta for working with dates and times
from openai import OpenAI # Import OpenAI Python client to interact with OpenAI's API
from langgraph.graph import StateGraph # Import StateGraph from LangGraph to manage quiz application state transitions
from typing import TypedDict, Dict, List, Optional # Import TypedDict, Dict, List, Optional for type hinting
from dotenv import load_dotenv # Import load_dotenv to load environment variables from a .env file
import shutil # Import shutil for file operations like copying, moving, or deleting files


# Load environment variables
load_dotenv() # Load environment variables from .env file
openai_api_key = os.getenv("OPENAI_API_KEY") # Retrieve the OpenAI API key from environment variables
email_password = os.getenv("EMAIL_PASSWORD") # Retrieve the email account password from environment variables
email_address = os.getenv("EMAIL_ADDRESS")  # Retrieve the email address from environment variables


if not openai_api_key: # Ensure the OpenAI API key exists, otherwise raise an error
    raise EnvironmentError("OPENAI_API_KEY not found in environment. Make sure your .env file is correctly configured.")

if not email_password or not email_address: # Ensure email credentials exist, otherwise raise an error
    raise EnvironmentError("EMAIL_PASSWORD and EMAIL_ADDRESS not found in environment. Configure your email settings.")


class QuizState(TypedDict):
    user_name: str # Name of the quiz participant
    user_answers: Dict[str, str] # Dictionary storing question IDs and user's answers
    score: Optional[int]  # User's quiz score (optional because it may be None initially)
    level: Optional[str] # User's skill level (e.g., beginner, intermediate, expert)
    roadmap: Optional[List[str]]  # Personalized learning roadmap for the user


class TaskManager: #Define a TaskManager class to handle tasks, database setup, and OpenAI integration
    def __init__(self, api_key: str): # Constructor method to initialize TaskManager with OpenAI API key
        self.client = OpenAI(api_key=api_key) # Create an OpenAI client instance using the provided API key
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


class QuizApp: # Main class that handles quiz logic, evaluation, and roadmap creation
    def __init__(self, api_key: str):
        self.client = OpenAI(api_key=api_key) # Initialize OpenAI client for roadmap generation
        self.correct_answers = {# Dictionary of correct answers (question_number: correct_option)
            "1": "c", "2": "b", "3": "d", "4": "a", "5": "a", 
            "6": "c", "7": "d", "8": "c", "9": "b", "10": "c"
        }
        self.graph = self.build_graph()# Build the quiz flow graph
        self.app = self.graph.compile()# Compile the state machine for execution
        self.task_manager = TaskManager(api_key)# Task manager instance to handle task assignments and submissions

    def start_quiz(self, state):# Step 1: Start quiz by returning questions and welcome message
        questions = {# Dictionary of quiz questions with text and multiple-choice options
        "1": {
            "text": "What is the correct file extension for Python files?",
            "options": {"a": ".pyth", "b": ".pt", "c": ".py", "d": ".pyt"}
        },
        "2": {
            "text": "What is the output of print(3 + 2 * 2)?",
            "options": {"a": "10", "b": "7", "c": "12", "d": "9"}
        },
        "3": {
            "text": "Which data structure stores key-value pairs?",
            "options": {"a": "List", "b": "Set", "c": "Tuple", "d": "Dictionary"}
        },
        "4": {
            "text": "Which library is used for numerical computing?",
            "options": {"a": "NumPy", "b": "Seaborn", "c": "Flask", "d": "BeautifulSoup"}
        },
        "5": {
            "text": "Purpose of the fit() method in ML?",
            "options": {"a": "It trains the model", "b": "It tests the model", "c": "It saves the model", "d": "It visualizes the model"}
        },
        "6": {
            "text": "What does 'self' refer to in a class method?",
            "options": {"a": "The method name", "b": "The class itself", "c": "An instance of the class", "d": "A global variable"}
        },
        "7": {
            "text": "Activation function for non-linearity in DNN?",
            "options": {"a": "Sigmoid", "b": "ReLU", "c": "Tanh", "d": "All of the above"}
        },
        "8": {
            "text": "Technique to prevent overfitting in NNs?",
            "options": {"a": "Batch normalization", "b": "Regularization", "c": "Dropout", "d": "Backpropagation"}
        },
        "9": {
            "text": "Purpose of gradient descent?",
            "options": {"a": "Making decisions", "b": "Optimizing parameters", "c": "Increasing complexity", "d": "Normalizing dataset"}
        },
        "10": {
            "text": "Main difference: supervised vs unsupervised learning?",
            "options": {"a": "Supervised doesn't use labels", "b": "Supervised is faster", "c": "Supervised uses labels", "d": "No difference"}
        },
    }

        return {# Return the quiz questions along with a personalized welcome message
        "quiz": questions,
        "message": f"Welcome {state.get('user_name', 'Guest')}! Please answer the following quiz questions."
    }

    def evaluate_quiz(self, state):# Step 2: Evaluate quiz and calculate score
        user_answers = state.get("user_answers", {}) # Get user's submitted answers
        score = sum(# Compare each answer with correct answers and count matches
            1 for q_no, correct in self.correct_answers.items()
            if user_answers.get(q_no, "").lower().strip() == correct
        )
        return {"score": score}

    def check_proficiency(self, state):# Step 3: Determine proficiency level based on score
        score = state["score"]
        if score <= 3:# Classify proficiency level based on score range
            level = "Beginner"
        elif score <= 6:
            level = "Intermediate"
        else:
            level = "Advanced"
        return {"level": level}

    def suggest_roadmap(self, state):# Step 4: Suggest a learning roadmap based on quiz results
        user_answers = state.get("user_answers", {})# Extract user answers, score, and level
        score = state.get("score")
        level = state.get("level")

        question_topics = {# Map each question to its related topic
            "1": "Python syntax and file handling",
            "2": "Python operator precedence",
            "3": "Python data structures - Dictionary",
            "4": "Numerical computing with NumPy",
            "5": "Machine learning model training concepts",
            "6": "OOP and class methods in Python",
            "7": "Deep learning activation functions",
            "8": "Overfitting and regularization techniques",
            "9": "Gradient descent and optimization in ML",
            "10": "Difference between supervised and unsupervised learning"
        }

        wrong_questions = [] # Separate correct and incorrect answers for roadmap generation
        correct_questions = []

        for q_no, correct_ans in self.correct_answers.items():
            if user_answers.get(q_no, "").lower().strip() == correct_ans:
                correct_questions.append((q_no, question_topics[q_no]))
            else:
                wrong_questions.append((q_no, question_topics[q_no]))
        # Build a prompt for the AI tutor to generate a roadmap
        prompt = f""" 
You are an AI tutor. A user scored {score}/10 in AI quiz and is categorized as {level} level.
Based on their answers, identify:

1. Their weak areas (the questions they got wrong)
2. Their strong areas (the ones they got right)

Each question is mapped to a topic.

Incorrect Topics:
{json.dumps(wrong_questions, indent=2)}

Correct Topics:
{json.dumps(correct_questions, indent=2)}

Now generate a focused learning roadmap:
- Group weak areas first and suggest how to study/improve each.
- Recommend specific resources (e.g., topics to search on YouTube, courses, or exercises).
- Then briefly reinforce strong areas (encourage practice or learning deeper concepts).

Return the roadmap as a structured list:
- Use clear section headers like "Weak Areas" and "Strong Areas"
- Use numbered lists for main topics
- Use bullet points for resources and sub-items
- Keep descriptions concise and actionable
- Focus on practical learning steps
"""

        response = self.client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": "You are an expert tutor that builds personalized learning plans."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.7,
            max_tokens=700,
        )

        roadmap_text = response.choices[0].message.content.strip()
        roadmap_lines = []
        for line in roadmap_text.splitlines():
            stripped = line.strip()
            if not stripped:
                roadmap_lines.append("")
                continue
            if stripped.lower().startswith("weak areas") or "reinforce" in stripped.lower():
                roadmap_lines.append("")
                roadmap_lines.append(f"**{stripped}**")
                roadmap_lines.append("")
                continue
            if stripped[:1].isdigit() and "." in stripped[:3]:
                roadmap_lines.append(f"**{stripped}**")
            elif stripped.startswith(("-", "*")):
                roadmap_lines.append(f"  • {stripped[1:].strip()}")
            else:
                roadmap_lines.append(f"  {stripped}")
        return {"roadmap": roadmap_lines}

    def store_result(self, state):# Step 5: Store quiz result and roadmap in the database
        name = state.get("user_name", "Unknown") # Extract relevant data from state
        roadmap = state.get("roadmap", [])
        score = state.get("score")
        level = state.get("level")

        roadmap_str = json.dumps(roadmap)# Convert roadmap list to JSON string for storage
        conn = sqlite3.connect("user_learning.db")# Save data to SQLite database
        cursor = conn.cursor()
        cursor.execute(""" 
        INSERT INTO users (name, score, level, roadmap)
        VALUES (?, ?, ?, ?)
        """, (name, score, level, roadmap_str))
        conn.commit()
        conn.close()

        return {"message": f"Roadmap saved for {name}."}

    def end(self, state):# Step 6: End the quiz process
        return {"status": "Quiz and roadmap complete."}

    def build_graph(self):# Method to build the quiz flow as a state graph
        graph = StateGraph(state_schema=QuizState)
        graph.add_node("start_quiz", self.start_quiz)# Define quiz flow steps as nodes
        graph.add_node("evaluate_quiz", self.evaluate_quiz)
        graph.add_node("check_proficiency", self.check_proficiency)
        graph.add_node("suggest_roadmap", self.suggest_roadmap)
        graph.add_node("store_result", self.store_result)
        graph.add_node("end", self.end)

        graph.set_entry_point("start_quiz")# Set the entry point and define execution order
        graph.add_edge("start_quiz", "evaluate_quiz")
        graph.add_edge("evaluate_quiz", "check_proficiency")
        graph.add_edge("check_proficiency", "suggest_roadmap")
        graph.add_edge("suggest_roadmap", "store_result")
        graph.add_edge("store_result", "end")

        return graph

    def run_quiz_graph(self, user_name: str, user_answers: Dict[str, str]) -> List[str]:# Method to run the complete quiz process
        final_state = self.app.invoke({
            "user_name": user_name,
            "user_answers": user_answers
        })
        return final_state.get("roadmap", [])

    # Task management methods
    def assign_task_to_user(self, user_name: str, user_email: str, level: str, roadmap: List[str]):# Task management methods (delegated to TaskManager)
        """Assign a task to a user"""
        return self.task_manager.assign_task(user_name, user_email, level, roadmap)# Calls TaskManager to create and assign a new task based on user's name, email, skill level, and roadmap
    
    def submit_user_task(self, user_email: str, task_id: int, submission_content: str):
        """Submit a task for a user"""
        return self.task_manager.submit_task(user_email, task_id, submission_content) # Sends the user's task submission to TaskManager to update the database
    
    def get_user_tasks(self, user_email: str):
        """Get all tasks for a user"""
        return self.task_manager.get_user_tasks(user_email) # Retrieves all tasks assigned to the user from TaskManager

    def get_all_user_names(self):
        return self.task_manager.get_all_user_names() # Fetches a list of distinct user names from the TaskManager

    def save_task_file(self, user_email: str, task_number: int, file_path: str):
        return self.task_manager.save_task_file(user_email, task_number, file_path) # Saves an uploaded file to the server and updates the task record with the file path

    def get_task_file(self, user_email: str, task_number: int):
        return self.task_manager.get_task_file(user_email, task_number) # Retrieves the stored file path for a specific submitted task


# ------------------ CLI RUNNER ------------------

def run_cli():
    app = QuizApp(api_key=openai_api_key)
    print("\n Welcome to the Personalized Learning Quiz\n")
    user_name = input("Enter your name: ").strip()

    # Just call the start_quiz method directly
    initial_state = {"user_name": user_name}
    start_response = app.start_quiz(initial_state)
    questions = start_response.get("quiz", {})

    print("\nAnswer the following questions (type a, b, c, or d):\n")

    answers = {}
    for q_num, q_data in questions.items():
        print(f"{q_num}. {q_data['text']}")
        for opt, val in q_data["options"].items():
            print(f"   {opt}) {val}")
        while True:
            user_answer = input("Your answer (a/b/c/d): ").lower().strip()
            if user_answer in q_data["options"]:
                answers[q_num] = user_answer
                break 
            else:
                print("Invalid input. Please choose a, b, c, or d.")
        print()

    # Now run the full graph with user answers
    roadmap = app.run_quiz_graph(user_name, answers)
    print(f"\nRecommended Roadmap for {user_name}:\n")
    for line in roadmap:
        print(line)


if __name__ == "__main__": 
    run_cli() 
