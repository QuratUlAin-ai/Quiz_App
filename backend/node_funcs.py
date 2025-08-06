import sqlite3
import json
import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime, timedelta
from openai import OpenAI
from langgraph.graph import StateGraph
from typing import TypedDict, Dict, List, Optional
from dotenv import load_dotenv

# Load environment variables
load_dotenv()
openai_api_key = os.getenv("OPENAI_API_KEY")
email_password = os.getenv("EMAIL_PASSWORD")
email_address = os.getenv("EMAIL_ADDRESS")

if not openai_api_key:
    raise EnvironmentError("OPENAI_API_KEY not found in environment. Make sure your .env file is correctly configured.")

if not email_password or not email_address:
    raise EnvironmentError("EMAIL_PASSWORD and EMAIL_ADDRESS not found in environment. Configure your email settings.")


class QuizState(TypedDict):
    user_name: str
    user_answers: Dict[str, str]
    score: Optional[int]
    level: Optional[str]
    roadmap: Optional[List[str]]


class TaskManager:
    def __init__(self, api_key: str):
        self.client = OpenAI(api_key=api_key)
        self.setup_database()
    
    def setup_database(self):
        """Setup database tables for tasks and progress tracking"""
        conn = sqlite3.connect("user_learning.db")
        cursor = conn.cursor()
        
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
        
        conn.commit()
        conn.close()
    
    def send_email(self, to_email: str, subject: str, body: str):
        """Send email using SMTP"""
        try:
            msg = MIMEMultipart('alternative')
            msg['From'] = email_address
            msg['To'] = to_email
            msg['Subject'] = subject
            
            # Add both HTML and plain text versions
            html_part = MIMEText(body, 'html')
            msg.attach(html_part)
            
            # Create SMTP session
            server = smtplib.SMTP('smtp.gmail.com', 587)
            server.starttls()
            
            # Login to the server
            server.login(email_address, email_password)
            
            # Send email
            text = msg.as_string()
            server.sendmail(email_address, to_email, text)
            server.quit()
            
            print(f"Email sent successfully to {to_email}")
            return True
            
        except smtplib.SMTPAuthenticationError:
            print("SMTP Authentication failed. Check your email and app password.")
            return False
        except smtplib.SMTPRecipientsRefused:
            print("Recipient email address is invalid.")
            return False
        except smtplib.SMTPServerDisconnected:
            print("SMTP server disconnected unexpectedly.")
            return False
        except Exception as e:
            print(f"Email sending failed: {str(e)}")
            return False
    
    def generate_task(self, user_name: str, level: str, roadmap: List[str], task_number: int, previous_task: str = None):
        """Generate AI-based task based on user's performance and roadmap"""
        prompt = f"""
        Generate a learning task for a user named {user_name} who is at {level} level.
        
        User's Learning Roadmap:
        {chr(10).join(roadmap)}
        
        Task Number: {task_number}
        """
        
        if task_number == 2 and previous_task:
            prompt += f"""
            Previous Task: {previous_task}
            
            Generate a follow-up task that builds upon the previous task and continues the learning journey.
            """
        else:
            prompt += """
            Generate an initial task that helps the user start their learning journey based on their roadmap.
            """
        
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
        
        response = self.client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": "You are an expert learning coach that creates personalized, practical learning tasks."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.7,
            max_tokens=500
        )
        
        return response.choices[0].message.content.strip()
    
    def assign_task(self, user_name: str, user_email: str, level: str, roadmap: List[str]):
        """Assign a new task to the user"""
        conn = sqlite3.connect("user_learning.db")
        cursor = conn.cursor()
        
        # Check if user has existing tasks
        cursor.execute("""
        SELECT task_number, task_description, status FROM tasks 
        WHERE user_email = ? ORDER BY task_number DESC LIMIT 1
        """, (user_email,))
        
        result = cursor.fetchone()
        
        # Determine task number and check if previous task is completed
        if not result:
            task_number = 1
            previous_task = None
        else:
            last_task_number, last_task_description, last_task_status = result
            
            # Only assign task 2 if task 1 is completed
            if last_task_number == 1 and last_task_status != 'completed':
                return {
                    "error": True,
                    "message": "Task 1 must be completed before Task 2 can be assigned. Please submit your first task first."
                }
            elif last_task_number == 2 and last_task_status != 'completed':
                return {
                    "error": True,
                    "message": "You already have Task 2 assigned. Please complete it before requesting a new task."
                }
            elif last_task_number >= 2:
                return {
                    "error": True,
                    "message": "You have completed all available tasks. Great job!"
                }
            
            task_number = last_task_number + 1
            previous_task = last_task_description
        
        # Generate new task
        task_description = self.generate_task(user_name, level, roadmap, task_number, previous_task)
        
        # Calculate due date (3 days from now)
        assigned_date = datetime.now().strftime("%Y-%m-%d")
        due_date = (datetime.now() + timedelta(days=3)).strftime("%Y-%m-%d")
        
        # Save task to database
        cursor.execute("""
        INSERT INTO tasks (user_name, user_email, task_number, task_description, assigned_date, due_date, status)
        VALUES (?, ?, ?, ?, ?, ?, 'pending')
        """, (user_name, user_email, task_number, task_description, assigned_date, due_date))
        
        task_id = cursor.lastrowid
        conn.commit()
        conn.close()
        
        # Send email notification
        subject = f"New Learning Task #{task_number} - {user_name}"
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
        
        email_sent = self.send_email(user_email, subject, body)
        
        return {
            "task_id": task_id,
            "task_number": task_number,
            "task_description": task_description,
            "due_date": due_date,
            "email_sent": email_sent,
            "error": False
        }
    
    def submit_task(self, user_email: str, task_id: int, submission_content: str):
        """Submit a completed task"""
        conn = sqlite3.connect("user_learning.db")
        cursor = conn.cursor()
        
        # Update task status
        submitted_date = datetime.now().strftime("%Y-%m-%d")
        cursor.execute("""
        UPDATE tasks 
        SET status = 'completed', submitted_date = ?, submission_content = ?
        WHERE id = ? AND user_email = ?
        """, (submitted_date, submission_content, task_id, user_email))
        
        if cursor.rowcount > 0:
            # Update user progress
            cursor.execute("""
            UPDATE user_progress 
            SET tasks_completed = tasks_completed + 1
            WHERE user_email = ?
            """, (user_email,))
            
            conn.commit()
            conn.close()
            
            # Send confirmation email
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
            
            self.send_email(user_email, subject, body)
            
            return {"success": True, "message": "Task submitted successfully!"}
        else:
            conn.close()
            return {"success": False, "message": "Task not found or already submitted."}
    
    def get_user_tasks(self, user_email: str):
        """Get all tasks for a user"""
        conn = sqlite3.connect("user_learning.db")
        cursor = conn.cursor()
        
        cursor.execute("""
        SELECT id, task_number, task_description, assigned_date, due_date, status, submitted_date
        FROM tasks 
        WHERE user_email = ? 
        ORDER BY task_number
        """, (user_email,))
        
        tasks = cursor.fetchall()
        conn.close()
        
        return [
            {
                "id": task[0],
                "task_number": task[1],
                "description": task[2],
                "assigned_date": task[3],
                "due_date": task[4],
                "status": task[5],
                "submitted_date": task[6]
            }
            for task in tasks
        ]


class QuizApp:
    def __init__(self, api_key: str):
        self.client = OpenAI(api_key=api_key)
        self.correct_answers = {
            "1": "c", "2": "b", "3": "d", "4": "a", "5": "a", 
            "6": "c", "7": "d", "8": "c", "9": "b", "10": "c"
        }
        self.graph = self.build_graph()
        self.app = self.graph.compile()
        self.task_manager = TaskManager(api_key)

    def start_quiz(self, state):
        questions = {
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

        return {
        "quiz": questions,
        "message": f"Welcome {state.get('user_name', 'Guest')}! Please answer the following quiz questions."
    }

    def evaluate_quiz(self, state):
        user_answers = state.get("user_answers", {})
        score = sum(
            1 for q_no, correct in self.correct_answers.items()
            if user_answers.get(q_no, "").lower().strip() == correct
        )
        return {"score": score}

    def check_proficiency(self, state):
        score = state["score"]
        if score <= 3:
            level = "Beginner"
        elif score <= 6:
            level = "Intermediate"
        else:
            level = "Advanced"
        return {"level": level}

    def suggest_roadmap(self, state):
        user_answers = state.get("user_answers", {})
        score = state.get("score")
        level = state.get("level")

        question_topics = {
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

        wrong_questions = []
        correct_questions = []

        for q_no, correct_ans in self.correct_answers.items():
            if user_answers.get(q_no, "").lower().strip() == correct_ans:
                correct_questions.append((q_no, question_topics[q_no]))
            else:
                wrong_questions.append((q_no, question_topics[q_no]))

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

    def store_result(self, state):
        name = state.get("user_name", "Unknown")
        roadmap = state.get("roadmap", [])
        score = state.get("score")
        level = state.get("level")

        roadmap_str = json.dumps(roadmap)
        conn = sqlite3.connect("user_learning.db")
        cursor = conn.cursor()
        cursor.execute(""" 
        INSERT INTO users (name, score, level, roadmap)
        VALUES (?, ?, ?, ?)
        """, (name, score, level, roadmap_str))
        conn.commit()
        conn.close()

        return {"message": f"Roadmap saved for {name}."}

    def end(self, state):
        return {"status": "Quiz and roadmap complete."}

    def build_graph(self):
        graph = StateGraph(state_schema=QuizState)
        graph.add_node("start_quiz", self.start_quiz)
        graph.add_node("evaluate_quiz", self.evaluate_quiz)
        graph.add_node("check_proficiency", self.check_proficiency)
        graph.add_node("suggest_roadmap", self.suggest_roadmap)
        graph.add_node("store_result", self.store_result)
        graph.add_node("end", self.end)

        graph.set_entry_point("start_quiz")
        graph.add_edge("start_quiz", "evaluate_quiz")
        graph.add_edge("evaluate_quiz", "check_proficiency")
        graph.add_edge("check_proficiency", "suggest_roadmap")
        graph.add_edge("suggest_roadmap", "store_result")
        graph.add_edge("store_result", "end")

        return graph

    def run_quiz_graph(self, user_name: str, user_answers: Dict[str, str]) -> List[str]:
        final_state = self.app.invoke({
            "user_name": user_name,
            "user_answers": user_answers
        })
        return final_state.get("roadmap", [])

    # Task management methods
    def assign_task_to_user(self, user_name: str, user_email: str, level: str, roadmap: List[str]):
        """Assign a task to a user"""
        return self.task_manager.assign_task(user_name, user_email, level, roadmap)
    
    def submit_user_task(self, user_email: str, task_id: int, submission_content: str):
        """Submit a task for a user"""
        return self.task_manager.submit_task(user_email, task_id, submission_content)
    
    def get_user_tasks(self, user_email: str):
        """Get all tasks for a user"""
        return self.task_manager.get_user_tasks(user_email)


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
