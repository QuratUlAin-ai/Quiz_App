
import sqlite3
import json
import os
from openai import OpenAI
from langgraph.graph import StateGraph
from typing import TypedDict, Dict, List, Optional
from dotenv import load_dotenv

from task_manager import TaskManager  # Import TaskManager

# Load environment
load_dotenv()
openai_api_key = os.getenv("OPENAI_API_KEY")
OPENAI_AVAILABLE = bool(openai_api_key)

class QuizState(TypedDict):
    user_name: str
    user_answers: Dict[str, str]
    score: Optional[int]
    level: Optional[str]
    roadmap: Optional[List[str]]


class QuizApp: # Main class that handles quiz logic, evaluation, and roadmap creation
    def __init__(self, api_key: str):
        self.client = OpenAI(api_key=api_key) if api_key else None # Initialize OpenAI client for roadmap generation
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

        if not self.client:
            # Fallback deterministic roadmap when OpenAI is not configured
            roadmap_text = "\n".join([
                "Weak Areas",
                "1. Review incorrect topics",
                "- Watch 1-2 short tutorials per topic",
                "- Complete a small exercise for each",
                "Strong Areas",
                "1. Reinforce strengths",
                "- Try a slightly harder problem",
                "- Teach the concept to someone or write notes",
            ])
        else:
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
