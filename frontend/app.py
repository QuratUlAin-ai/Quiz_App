import gradio as gr
import os
import sys
import json

# Path config: include backend
frontend_dir = os.path.dirname(os.path.abspath(__file__))
backend_dir = os.path.abspath(os.path.join(frontend_dir, "..", "backend"))
sys.path.append(backend_dir)

from node_funcs import QuizApp, openai_api_key

quiz_app = QuizApp(api_key=openai_api_key)

def start_quiz(user_name):
    """Initialize the quiz and return questions"""
    if not user_name.strip():
        return gr.update(visible=False), gr.update(visible=False), gr.update(visible=True), "Please enter your name first."
    
    state = {"user_name": user_name}
    quiz_data = quiz_app.start_quiz(state)["quiz"]
    
    # Create question display with radio buttons
    questions_html = ""
    for q_key, q_val in quiz_data.items():
        questions_html += f"<h3>Question {q_key}</h3>"
        questions_html += f"<p><strong>{q_val['text']}</strong></p>"
        questions_html += "<div style='margin-left: 20px;'>"
        for opt, val in q_val["options"].items():
            questions_html += f"<p><strong>{opt})</strong> {val}</p>"
        questions_html += "</div><br>"
    
    return gr.update(visible=False), gr.update(visible=True), gr.update(visible=False), questions_html

def submit_quiz(user_name, *answers):
    """Process quiz answers and return roadmap"""
    if not user_name.strip():
        return gr.update(visible=False), gr.update(visible=False), gr.update(visible=True), "Please enter your name first."
    
    # Convert answers to the expected format
    user_answers = {}
    for i, answer in enumerate(answers, 1):
        if answer:
            user_answers[str(i)] = answer.lower()
    
    if len(user_answers) < 10:
        return gr.update(visible=False), gr.update(visible=False), gr.update(visible=True), "Please answer all 10 questions before submitting."
    
    try:
        # Run the quiz graph
        roadmap = quiz_app.run_quiz_graph(user_name, user_answers)
        
        # Calculate score and level
        score = sum(1 for q_no, correct in quiz_app.correct_answers.items()
                   if user_answers.get(q_no, "").lower().strip() == correct)
        
        level = "Beginner" if score <= 3 else "Intermediate" if score <= 6 else "Advanced"
        
        # Format the roadmap 
        roadmap_text = "\n".join(roadmap)
        result = f""" 
## Quiz Results for {user_name}

**Score:** {score}/10  
**Level:** {level}

---

## Your Personalized Learning Roadmap

{roadmap_text}
        """
        
        return gr.update(visible=False), gr.update(visible=False), gr.update(visible=True), result
        
    except Exception as e:
        return gr.update(visible=False), gr.update(visible=False), gr.update(visible=True), f"An error occurred: {str(e)}"

def reset_to_start():
    """Reset the interface to the start page"""
    return gr.update(visible=True), gr.update(visible=False), gr.update(visible=False), ""

def assign_task(user_name, user_email):
    """Assign a task to the user"""
    if not user_name.strip() or not user_email.strip():
        return gr.update(visible=False), gr.update(visible=False), gr.update(visible=False), gr.update(visible=True), "Please enter both name and email."
    
    try:
        # Get user's quiz results from database
        import sqlite3
        conn = sqlite3.connect("user_learning.db")
        cursor = conn.cursor()
        cursor.execute("""
        SELECT score, level, roadmap FROM users 
        WHERE name = ? ORDER BY id DESC LIMIT 1
        """, (user_name,))
        
        result = cursor.fetchone()
        conn.close()
        
        if not result:
            return gr.update(visible=False), gr.update(visible=False), gr.update(visible=False), gr.update(visible=True), "No quiz results found. Please complete the quiz first."
        
        score, level, roadmap_str = result
        roadmap = json.loads(roadmap_str)
        
        # Assign task
        task_result = quiz_app.assign_task_to_user(user_name, user_email, level, roadmap)
        
        # Check if there was an error in task assignment
        if task_result.get("error", False):
            return gr.update(visible=False), gr.update(visible=False), gr.update(visible=False), gr.update(visible=True), f"**Task Assignment Error:**\n\n{task_result['message']}"
        
        if task_result["email_sent"]:
            message = f"""
## Task Assigned Successfully!

**Task #{task_result['task_number']}** has been assigned to {user_name}.

**Task Description:**
{task_result['task_description']}

**Due Date:** {task_result['due_date']}

✅ An email has been sent to {user_email} with the task details.

**Next Steps:**
- Complete the task within the due date
- Submit your work using the "Submit Task" feature
- Task 2 will only be assigned after Task 1 is completed
            """
        else:
            message = f"""
## Task Assigned!

**Task #{task_result['task_number']}** has been assigned to {user_name}.

**Task Description:**
{task_result['task_description']}

**Due Date:** {task_result['due_date']}

⚠️ **Email delivery failed.** Please check your email settings in the .env file.

**Next Steps:**
- Complete the task within the due date
- Submit your work using the "Submit Task" feature
- Task 2 will only be assigned after Task 1 is completed
            """
        
        return gr.update(visible=False), gr.update(visible=False), gr.update(visible=False), gr.update(visible=True), message
        
    except Exception as e:
        return gr.update(visible=False), gr.update(visible=False), gr.update(visible=False), gr.update(visible=True), f"An error occurred: {str(e)}"

def submit_task(user_email, task_id, submission_content):
    """Submit a completed task"""
    if not user_email.strip() or not task_id or not submission_content.strip():
        return "Please fill in all fields."
    
    try:
        result = quiz_app.submit_user_task(user_email, int(task_id), submission_content)
        return result["message"]
    except Exception as e:
        return f"An error occurred: {str(e)}"

def get_user_tasks(user_email):
    """Get tasks for a user"""
    if not user_email.strip():
        return "Please enter your email address."
    
    try:
        tasks = quiz_app.get_user_tasks(user_email)
        if not tasks:
            return "No tasks found for this email address."
        
        tasks_html = "## Your Tasks\n\n"
        for task in tasks:
            status_emoji = "✅" if task["status"] == "completed" else "⏳"
            tasks_html += f"""
**{status_emoji} Task #{task['task_number']}** ({task['status']})
- **Assigned:** {task['assigned_date']}
- **Due:** {task['due_date']}
- **Description:** {task['description']}
"""
            if task["submitted_date"]:
                tasks_html += f"- **Submitted:** {task['submitted_date']}\n"
            tasks_html += "\n---\n\n"
        
        return tasks_html
    except Exception as e:
        return f"An error occurred: {str(e)}"

# Create the Gradio interface
with gr.Blocks(title="AI Learning Quiz", theme=gr.themes.Soft(), css="""
    .main-container {
        max-width: 800px;
        margin: 0 auto;
        padding: 20px;
        min-height: 100vh;
        display: flex;
        align-items: center;
        justify-content: center;
    }
    
    .page-container {
        width: 100%;
        max-width: 100%;
    }
    
    .content-box {
        background: white;
        border: 2px solid #e0e0e0;
        border-radius: 12px;
        padding: 30px;
        box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
        margin: 20px 0;
        min-height: 400px;
        display: flex;
        flex-direction: column;
        justify-content: center;
    }
    
    .welcome-page .content-box {
        max-width: 500px;
        margin: 0 auto;
    }
    
    .quiz-page .content-box {
        max-width: 700px;
        margin: 0 auto;
    }
    
    .results-page .content-box {
        max-width: 800px;
        margin: 0 auto;
    }
    
    .task-page .content-box {
        max-width: 600px;
        margin: 0 auto;
    }
    
    .input-section {
        text-align: center;
        margin-top: 30px;
    }
    
    .question-container {
        margin-bottom: 30px;
        padding: 20px;
        border: 1px solid #f0f0f0;
        border-radius: 8px;
        background: #fafafa;
    }
    
    .question-container:last-child {
        margin-bottom: 20px;
    }
    
    @media (max-width: 768px) {
        .main-container {
            padding: 10px;
        }
        
        .content-box {
            padding: 20px;
            margin: 10px 0;
        }
        
        .question-container {
            padding: 15px;
        }
    }
    
    @media (max-width: 480px) {
        .content-box {
            padding: 15px;
        }
        
        .question-container {
            padding: 10px;
        }
    }
""") as demo:
    # Main container with responsive styling
    with gr.Column(elem_classes=["main-container"]):
        # Page 1: Welcome and Name Input
        with gr.Column(visible=True, elem_classes=["page-container", "welcome-page"]) as welcome_page:
            with gr.Column(elem_classes=["content-box"]):
                gr.Markdown("""
                # Learning Quiz
                
                Welcome! This quiz will assess your knowledge of Python and AI concepts, then provide you with a personalized learning roadmap.
                """)
                
                with gr.Column(elem_classes=["input-section"]):
                    user_name = gr.Textbox(
                        label="Your Name",
                        placeholder="Enter your name here...",
                        container=True
                    )
                    start_button = gr.Button("Start Quiz", variant="primary", size="lg")
        
        # Page 2: Quiz Questions
        with gr.Column(visible=False, elem_classes=["page-container", "quiz-page"]) as quiz_page:
            with gr.Column(elem_classes=["content-box"]):
                gr.Markdown("### Answer the Questions")
                
                # Create questions with their options
                answer_inputs = []
                
                # Question 1
                with gr.Column(elem_classes=["question-container"]):
                    gr.Markdown("**Question 1:** What is the correct file extension for Python files?")
                    gr.Markdown("""
                    a) .pyth  
                    b) .pt  
                    c) .py  
                    d) .pyt
                    """)
                    q1_answer = gr.Radio(choices=["a", "b", "c", "d"], label="", container=False)
                    answer_inputs.append(q1_answer)
                
                # Question 2
                with gr.Column(elem_classes=["question-container"]):
                    gr.Markdown("**Question 2:** What is the output of print(3 + 2 * 2)?")
                    gr.Markdown("""
                    a) 10  
                    b) 7  
                    c) 12  
                    d) 9
                    """)
                    q2_answer = gr.Radio(choices=["a", "b", "c", "d"], label="", container=False)
                    answer_inputs.append(q2_answer)
                
                # Question 3
                with gr.Column(elem_classes=["question-container"]):
                    gr.Markdown("**Question 3:** Which data structure stores key-value pairs?")
                    gr.Markdown("""
                    a) List  
                    b) Set  
                    c) Tuple  
                    d) Dictionary
                    """)
                    q3_answer = gr.Radio(choices=["a", "b", "c", "d"], label="", container=False)
                    answer_inputs.append(q3_answer)
                
                # Question 4
                with gr.Column(elem_classes=["question-container"]):
                    gr.Markdown("**Question 4:** Which library is used for numerical computing?")
                    gr.Markdown("""
                    a) NumPy  
                    b) Seaborn  
                    c) Flask  
                    d) BeautifulSoup
                    """)
                    q4_answer = gr.Radio(choices=["a", "b", "c", "d"], label="", container=False)
                    answer_inputs.append(q4_answer)
                
                # Question 5
                with gr.Column(elem_classes=["question-container"]):
                    gr.Markdown("**Question 5:** Purpose of the fit() method in ML?")
                    gr.Markdown("""
                    a) It trains the model  
                    b) It tests the model  
                    c) It saves the model  
                    d) It visualizes the model
                    """)
                    q5_answer = gr.Radio(choices=["a", "b", "c", "d"], label="", container=False)
                    answer_inputs.append(q5_answer)
                
                # Question 6
                with gr.Column(elem_classes=["question-container"]):
                    gr.Markdown("**Question 6:** What does 'self' refer to in a class method?")
                    gr.Markdown("""
                    a) The method name  
                    b) The class itself  
                    c) An instance of the class  
                    d) A global variable
                    """)
                    q6_answer = gr.Radio(choices=["a", "b", "c", "d"], label="", container=False)
                    answer_inputs.append(q6_answer)
                
                # Question 7
                with gr.Column(elem_classes=["question-container"]):
                    gr.Markdown("**Question 7:** Activation function for non-linearity in DNN?")
                    gr.Markdown("""
                    a) Sigmoid  
                    b) ReLU  
                    c) Tanh  
                    d) All of the above
                    """)
                    q7_answer = gr.Radio(choices=["a", "b", "c", "d"], label="", container=False)
                    answer_inputs.append(q7_answer)
                
                # Question 8
                with gr.Column(elem_classes=["question-container"]):
                    gr.Markdown("**Question 8:** Technique to prevent overfitting in NNs?")
                    gr.Markdown("""
                    a) Batch normalization  
                    b) Regularization  
                    c) Dropout  
                    d) Backpropagation
                    """)
                    q8_answer = gr.Radio(choices=["a", "b", "c", "d"], label="", container=False)
                    answer_inputs.append(q8_answer)
                
                # Question 9
                with gr.Column(elem_classes=["question-container"]):
                    gr.Markdown("**Question 9:** Purpose of gradient descent?")
                    gr.Markdown("""
                    a) Making decisions  
                    b) Optimizing parameters  
                    c) Increasing complexity  
                    d) Normalizing dataset
                    """)
                    q9_answer = gr.Radio(choices=["a", "b", "c", "d"], label="", container=False)
                    answer_inputs.append(q9_answer)
                
                # Question 10
                with gr.Column(elem_classes=["question-container"]):
                    gr.Markdown("**Question 10:** Main difference: supervised vs unsupervised learning?")
                    gr.Markdown("""
                    a) Supervised doesn't use labels  
                    b) Supervised is faster  
                    c) Supervised uses labels  
                    d) No difference
                    """)
                    q10_answer = gr.Radio(choices=["a", "b", "c", "d"], label="", container=False)
                    answer_inputs.append(q10_answer)
                
                submit_button = gr.Button("Submit Quiz", variant="primary", size="lg")
        
        # Page 3: Results
        with gr.Column(visible=False, elem_classes=["page-container", "results-page"]) as results_page:
            with gr.Column(elem_classes=["content-box"]):
                results_display = gr.Markdown(label="Your Results")
                with gr.Row():
                    restart_button = gr.Button("Take Quiz Again", variant="secondary", size="lg")
                    assign_task_button = gr.Button("Assign Task", variant="primary", size="lg")
        
        # Page 4: Task Assignment
        with gr.Column(visible=False, elem_classes=["page-container", "task-page"]) as task_page:
            with gr.Column(elem_classes=["content-box"]):
                gr.Markdown("### Assign Learning Task")
                gr.Markdown("Enter your email to receive personalized learning tasks based on your quiz performance.")
                
                with gr.Column(elem_classes=["input-section"]):
                    task_user_name = gr.Textbox(
                        label="Your Name",
                        placeholder="Enter your name...",
                        container=True
                    )
                    task_user_email = gr.Textbox(
                        label="Your Email",
                        placeholder="Enter your email address...",
                        container=True
                    )
                    assign_task_btn = gr.Button("Assign Task", variant="primary", size="lg")
                
                task_result_display = gr.Markdown(label="Task Assignment Result")
        
        # Page 5: Task Management
        with gr.Column(visible=False, elem_classes=["page-container", "task-page"]) as task_management_page:
            with gr.Column(elem_classes=["content-box"]):
                gr.Markdown("### Task Management")
                
                with gr.Tabs():
                    with gr.Tab("View Tasks"):
                        gr.Markdown("Enter your email to view your assigned tasks:")
                        view_email = gr.Textbox(label="Email", placeholder="Enter your email...")
                        view_tasks_btn = gr.Button("View Tasks", variant="primary")
                        tasks_display = gr.Markdown(label="Your Tasks")
                    
                    with gr.Tab("Submit Task"):
                        gr.Markdown("Submit a completed task:")
                        submit_email = gr.Textbox(label="Email", placeholder="Enter your email...")
                        submit_task_id = gr.Number(label="Task ID", placeholder="Enter task ID...")
                        submit_content = gr.Textbox(
                            label="Task Submission", 
                            placeholder="Describe what you completed...",
                            lines=5
                        )
                        submit_task_btn = gr.Button("Submit Task", variant="primary")
                        submit_result = gr.Markdown(label="Submission Result")
    
    # Event handlers
    start_button.click(
        fn=start_quiz,
        inputs=[user_name],
        outputs=[welcome_page, quiz_page, results_page, results_display]
    )
    
    submit_button.click(
        fn=submit_quiz,
        inputs=[user_name] + answer_inputs,
        outputs=[welcome_page, quiz_page, results_page, results_display]
    )
    
    restart_button.click(
        fn=reset_to_start,
        outputs=[welcome_page, quiz_page, results_page, results_display]
    )
    
    assign_task_button.click(
        fn=lambda: (gr.update(visible=False), gr.update(visible=False), gr.update(visible=False), gr.update(visible=True)),
        outputs=[welcome_page, quiz_page, results_page, task_page]
    )
    
    assign_task_btn.click(
        fn=assign_task,
        inputs=[task_user_name, task_user_email],
        outputs=[welcome_page, quiz_page, results_page, task_page, task_result_display]
    )
    
    view_tasks_btn.click(
        fn=get_user_tasks,
        inputs=[view_email],
        outputs=[tasks_display]
    )
    
    submit_task_btn.click(
        fn=submit_task,
        inputs=[submit_email, submit_task_id, submit_content],
        outputs=[submit_result]
    )

if __name__ == "__main__":
    demo.launch(share=False, debug=True)
