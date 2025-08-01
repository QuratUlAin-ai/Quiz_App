import sqlite3
import json
import os
from openai import OpenAI
from langgraph.graph import StateGraph
from typing import TypedDict, Dict, List, Optional
from dotenv import load_dotenv

# Load environment variables
load_dotenv()
openai_api_key = os.getenv("OPENAI_API_KEY")

if not openai_api_key:
    raise EnvironmentError("OPENAI_API_KEY not found in environment. Make sure your .env file is correctly configured.")


class QuizState(TypedDict): #creating a custom dictionary type called QuizState that inherits from TypedDict. Each key of the dictionary has a name and a specific expected type.
    user_name: str #This key must be a string.
    user_answers: Dict[str, str] #both keys and values are strings each key is question number and value is the answer.
    score: Optional[int] #it represents the user total score. optional means either int or none.
    level: Optional[str] #it indicates proficiency level based on score.
    roadmap: Optional[List[str]] #it indicates list of strings which is roadmap generated after quiz evaluation.


class QuizApp: #this is custom class it will encapsulate all the logic and state of quiz application.
    def __init__(self, api_key: str): #constructor method that contains API key which is a string.
        self.client = OpenAI(api_key=api_key) #This line creates an instance of the OpenAI client using the provided API key.
        self.correct_answers = {  #This dictionary holds the correct answers for each quiz question.
            "1": "c", "2": "b", "3": "d", "4": "a", "5": "a", 
            "6": "c", "7": "d", "8": "c", "9": "b", "10": "c"
        } # This enables automated scoring after the quiz is submitted.
        self.graph = self.build_graph()#This line builds the LangGraph state machine by calling a custom method build_graph() defined later in the class.
        self.app = self.graph.compile()#This compiles the LangGraph object (self.graph) into a runnable application.

    def start_quiz(self, state):#This begins the definition of a dictionary named questions.self refers to the current instance of the class.State a dictionary (likely of type `QuizState`) that holds information about the current user
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
            "options": {"a": "Supervised doesn’t use labels", "b": "Supervised is faster", "c": "Supervised uses labels", "d": "No difference"}
        },
    }

        return { #This line returns a dictionary. It's the output of the start_quiz method.
        "quiz": questions, #Adds a key called "quiz" which contains the entire `questions` dictionary.
        "message": f"Welcome {state.get('user_name', 'Guest')}! Please answer the following quiz questions." #Adds a "message" key that returns a personalized welcome message.
    }

    def evaluate_quiz(self, state):
        user_answers = state.get("user_answers", {}) #Tries to retrieve the value associated with the key "user_answers" from the state dictionary.If the key is missing, it defaults to an empty dictionary {}.
        score = sum( #score will store the total number of correct answer by the user.
            1 for q_no, correct in self.correct_answers.items()#this is a generator expression that iterates through each question number (q_no) and correct option (correct) from the self.correct_answers dictionary.
            if user_answers.get(q_no, "").lower().strip() == correct#this is a condition that checks if the user's answer for the current question (q_no) matches the correct answer (correct).
        )
        return {"score": score}#Returns a dictionary with the calculated score.

    def check_proficiency(self, state):#This method checks the proficiency level of the user based on their score.
        score = state["score"]#This line retrieves the score from the state dictionary.
        if score <= 3:
            level = "Beginner"
        elif score <= 6:
            level = "Intermediate"
        else:
            level = "Advanced"
        return {"level": level}

    def suggest_roadmap(self, state):#This method generates a personalized learning roadmap based on the user's quiz answers.
        user_answers = state.get("user_answers", {})#This line retrieves the user's answers from the state dictionary.
        score = state.get("score")#This line retrieves the score from the state dictionary.
        level = state.get("level")#This line retrieves the proficiency level from the state dictionary.

        question_topics = { #This dictionary maps each question number to a topic.
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

        wrong_questions = []#This list will store questions that the user got wrong.
        correct_questions = []#This list will store questions that the user got correct.

        for q_no, correct_ans in self.correct_answers.items():#This loop iterates through each question number (q_no) and correct answer (correct_ans) from the self.correct_answers dictionary.
            if user_answers.get(q_no, "").lower().strip() == correct_ans: #This condition checks if the user's answer for the current question (q_no) matches the correct answer (correct_ans).
                correct_questions.append((q_no, question_topics[q_no])) #If the user's answer is correct, it adds the question number and topic to the correct_questions list.
            else:
                wrong_questions.append((q_no, question_topics[q_no])) #If the user's answer is incorrect, it adds the question number and topic to the wrong_questions list.

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
- Use numbering or bullet points.
- Use indentation for resources or sub-items.
- Add line breaks between major sections to make it readable in a terminal.
"""#This is the string that conatin prompt for AI tutor to generate a personalized learning roadmap.

        response = self.client.chat.completions.create(#This line creates a chat completion using the OpenAI API.
            model="gpt-4o",#This specifies the model to use for the chat completion.
            messages=[ #This is a list of messages that will be sent to the AI tutor.
                {"role": "system", "content": "You are an expert tutor that builds personalized learning plans."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.7, #This sets the temperature to reduce hallucinations.
            max_tokens=700, #This sets the maximum number of tokens in the response.
        )

        roadmap_text = response.choices[0].message.content.strip() #This line extracts the content of the response.
        roadmap_lines = [] #This list will store the roadmap as a list of strings.
        for line in roadmap_text.splitlines(): #This loop iterates through each line in the roadmap text.
            stripped = line.strip() #This line removes any leading or trailing whitespace from the line.
            if not stripped: #This condition checks if the line is empty.
                roadmap_lines.append("") #If the line is empty, it adds an empty string to the roadmap_lines list.
                continue
            if stripped.lower().startswith("weak areas") or "reinforce" in stripped.lower(): #This condition checks if the line start with "weak areas" or contains "reinforce" in lowercase.
                roadmap_lines.append("") #If the line start with "weak areas" or contains "reinforce" in lowercase, it adds an empty string to the roadmap_lines list.
                roadmap_lines.append(f"{stripped}".center(60, "-")) #This line centers the line with 60 characters and dashes.
                roadmap_lines.append("") #This line adds an empty string to the roadmap_lines list.
                continue
            if stripped[:1].isdigit() and "." in stripped[:3]: #This condition checks if the line starts with a digit and contains a dot in the first three characters.
                roadmap_lines.append(f"  {stripped}") #If the line starts with a digit and contains a dot in the first three characters, it adds the line to the roadmap_lines list.
            elif stripped.startswith(("-", "*")): #This condition checks if the line starts with a dash or an asterisk.
                roadmap_lines.append(f"     - {stripped[1:].strip()}") #If the line starts with a dash or an asterisk, it adds the line to the roadmap_lines list.
            else:
                roadmap_lines.append(f"     {stripped}") #If the line does not start with a digit and does not start with a dash or an asterisk, it adds the line to the roadmap_lines list.
        return {"roadmap": roadmap_lines} #This line returns a dictionary with the roadmap as a list of strings.

    def store_result(self, state): #This method stores the result of the quiz in a database.
        name = state.get("user_name", "Unknown") #This line retrieves the user's name from the state dictionary.
        roadmap = state.get("roadmap", []) #This line retrieves the roadmap from the state dictionary.
        score = state.get("score") #This line retrieves the score from the state dictionary.
        level = state.get("level") #This line retrieves the proficiency level from the dictionary.

        roadmap_str = json.dumps(roadmap) #This line converts the roadmap list into a JSON string.
        conn = sqlite3.connect("user_learning.db") #This line connects to the SQLite database file named "user_learning.db"
        cursor = conn.cursor() #This line creates a cursor object that allows us to execute SQL commands.
        cursor.execute(""" 
        INSERT INTO users (name, score, level, roadmap)
        VALUES (?, ?, ?, ?)
        """, (name, score, level, roadmap_str)) #This line executes an SQL command to insert the user's name, score, level, and roadmap into the database.
        conn.commit() #This line commits the changes to the database.
        conn.close() #This line closes the connection to the database.

        return {"message": f"Roadmap saved for {name}."} #This line returns a dictionary with a message indicating that the roadmap has been saved.

    def end(self, state): #This method is called when the quiz is complete.
        return {"status": "Quiz and roadmap complete."} #This line returns a dictionary with a message indiacting that the quiz and roadmap are complete.

    def build_graph(self): #This method builds the state machine for the quiz application.
        graph = StateGraph(state_schema=QuizState) #This line creates a state machine object with the QuizState schema.
        graph.add_node("start_quiz", self.start_quiz) #This line adds a node to the state machine that represents the start of the quiz.
        graph.add_node("evaluate_quiz", self.evaluate_quiz) #This line adds a node to the state machine that represents the evaluation of the quiz.
        graph.add_node("check_proficiency", self.check_proficiency) #This line adds a node to the state machine that check the proficiency of the quiz.
        graph.add_node("suggest_roadmap", self.suggest_roadmap) #This line adds a node to the state machine that suggest the roadmap for the quiz.
        graph.add_node("store_result", self.store_result) #This line adds a node to the state machine that store the result of the quiz.
        graph.add_node("end", self.end)#This line adds a node to the state machine that represents the end of the quiz.

        graph.set_entry_point("start_quiz") #This line sets the entry point of the state machine to the start_quiz mode.
        graph.add_edge("start_quiz", "evaluate_quiz") #This line adds an edge from the start_quiz node to the evaluate_quiz node.
        graph.add_edge("evaluate_quiz", "check_proficiency") #This line adds an edge from the evaluate_quiz node to the check_proficiency node.
        graph.add_edge("check_proficiency", "suggest_roadmap") #This line adds an edge from the check_proficiency node to the suggest_roadmap node.
        graph.add_edge("suggest_roadmap", "store_result") #This line adds an edge from the suggest_roadmap node to the store_result node.
        graph.add_edge("store_result", "end") #This line adds an edge from the store_result node to the end node.

        return graph #This line returns the state machine object.

    def run_quiz_graph(self, user_name: str, user_answers: Dict[str, str]) -> List[str]: #This method runs the quiz application.
        final_state = self.app.invoke({ #This line invokes the state machine with the user's name and answers.
            "user_name": user_name, #This line adds the user's name to the state.
            "user_answers": user_answers #This line adds the user's answers to the state.
        })
        return final_state.get("roadmap", []) #This line returns the roadmap from the state.


# ------------------ CLI RUNNER ------------------

def run_cli(): #This function is the entry point for the CLI application.
    app = QuizApp(api_key=openai_api_key) #This line creates an instance of the QuizApp class.
    print("\n Welcome to the Personalized Learning Quiz\n") #This line prints a welcome message.
    user_name = input("Enter your name: ").strip() #This line prompts the user to enter their name and strips any leading or trailing whitespace.

    # Just call the start_quiz method directly
    initial_state = {"user_name": user_name} #This line creates a dictionary with the user's name.
    start_response = app.start_quiz(initial_state) #This line invokes the start_quiz method with the initial state.
    questions = start_response.get("quiz", {}) #This line retrieves the quiz questions from the start_response.

    print("\nAnswer the following questions (type a, b, c, or d):\n") #This line prints a message asking the user to answer the quetions.

    answers = {} #This line creates an empty dictionary to store the user's answers.
    for q_num, q_data in questions.items(): #This loop iterates through each question number (q_num) and question data (q_data) from the questions dictionary.
        print(f"{q_num}. {q_data['text']}") #This line prints the question number and question text.
        for opt, val in q_data["options"].items(): #This loop iterates through each option (opt) and value (val) from the question data.
            print(f"   {opt}) {val}") #This line prints the option and value.
        while True: #This loop prompts the user to enter their answer until they provide a valid input.
            user_answer = input("Your answer (a/b/c/d): ").lower().strip() #This line prompts the user to enter their answer and strips any leading or trailing whitespace.
            if user_answer in q_data["options"]: #This condition checks if the user's answer is in the question options.
                answers[q_num] = user_answer #This line adds the user's answer to the answers dictionary.
                break 
            else:
                print("Invalid input. Please choose a, b, c, or d.") #This line prints a message asking the user to choose a, b, c, or d.
        print() #This line prints a blank line

    # Now run the full graph with user answers
    roadmap = app.run_quiz_graph(user_name, answers) #This line invokes the run_quiz_graph method with the user's name and answers.
    print(f"\nRecommended Roadmap for {user_name}:\n") #This line prints a message indicating the recommended roadmap for the user.
    for line in roadmap: #This loop iterates through each line in the roadmap.
        print(line) #This line prints the line.


if __name__ == "__main__": 
    run_cli() 
