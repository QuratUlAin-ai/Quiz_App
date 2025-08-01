import gradio as gr
import os
import sys

# Path config: include backend
frontend_dir = os.path.dirname(os.path.abspath(__file__))
backend_dir = os.path.abspath(os.path.join(frontend_dir, "..", "backend"))
sys.path.append(backend_dir)

from node_funcs import QuizApp, openai_api_key

quiz_app = QuizApp(api_key=openai_api_key)

def start_quiz(user_name): #This function is called when the user clicks the "Start Quiz" button.
    """Initialize the quiz and return questions"""
    if not user_name.strip(): #This condition checks if the user has entered a name.
        return gr.update(visible=False), gr.update(visible=False), "Please enter your name first." #This line returns a tuple of three elements: a gr.update.object that sets the visibility of the quiz section to False, a gr.update.object that sets the visibility of the submit button to False, and a string that asks the user to enter their name.
    
    state = {"user_name": user_name} #This line creates a dictionary with the user's name.
    quiz_data = quiz_app.start_quiz(state)["quiz"] #This line invokes the start_quiz method with the state and retrieves the quiz data.
    
    # Create question display with radio buttons
    questions_html = ""
    for q_key, q_val in quiz_data.items(): #This loop iterates through each question key (q_key) and question value (q_val) from the quiz data.
        questions_html += f"<h3>Question {q_key}</h3>" #This line adds a header with the question number.
        questions_html += f"<p><strong>{q_val['text']}</strong></p>" #This line adds the question text.
        questions_html += "<div style='margin-left: 20px;'>" #This line adds a div with a margin-left of 20px.
        for opt, val in q_val["options"].items(): #This loop iterates through each option (opt) and value (val) from the question value.
            questions_html += f"<p><strong>{opt})</strong> {val}</p>" #This line adds the option and value to the questions_html string.
        questions_html += "</div><br>" #This line adds a line break.
    
    return gr.update(visible=True), gr.update(visible=True), questions_html #This line returns a tuple of three elements: a gr.update.object that sets the visibility of the quiz section to True, a gr.update.object that sets the visibility of the submit button to True, and a string that contains the questions.

def submit_quiz(user_name, *answers): #This function is called when the user clicks the "Submit Quiz" button.
    """Process quiz answers and return roadmap"""
    if not user_name.strip(): #This condition checks if the user has entered a name.
        return "Please enter your name first." #
    
    # Convert answers to the expected format
    user_answers = {} #This line creates an empty dictionary to store the user's answers.
    for i, answer in enumerate(answers, 1): #This loop iterates through each answer (answer) from the answers list.
        if answer: #This condition checks if the answer is not empty.
            user_answers[str(i)] = answer.lower() #This line adds the answer to the user_answers dictionary.
    
    if len(user_answers) < 10: #This condition checks if the user has answered all 10 questions.
        return "Please answer all 10 questions before submitting." #This line returns a string that asks the user to answer all 10 questions before submitting.
    
    try: #This block is used to handle any errors that may occur.
        # Run the quiz graph
        roadmap = quiz_app.run_quiz_graph(user_name, user_answers)
        
        # Calculate score and level
        score = sum(1 for q_no, correct in quiz_app.correct_answers.items() #This line calculates the score by iterating through each question number (q_no) and correct answer (correct) from the correct_answers dictionary.
                   if user_answers.get(q_no, "").lower().strip() == correct) #This line checks if the user's answer for the current question (q_no) matches the correct answer (correct).
        
        level = "Beginner" if score <= 3 else "Intermediate" if score <= 6 else "Advanced" #This line determines the proficiency level based on the score.
        
        # Format the roadmap 
        roadmap_text = "\n".join(roadmap) #This line joins the roadmap list into a single string with line breaks.
        #This string formats final output message.Catches and displays errors if the quiz backend fails.Starts the gradio ui with the soft theme and display introductory message.
        result = f""" 
# Quiz Results for {user_name}

**Score:** {score}/10  
**Level:** {level}

---

# Your Personalized Learning Roadmap

{roadmap_text}
        """
        
        return result
        
    except Exception as e:
        return f"An error occurred: {str(e)}"

# Create the Gradio interface
with gr.Blocks(title="AI Learning Quiz", theme=gr.themes.Soft()) as demo:
    gr.Markdown("""
    # Learning Quiz
    
    Welcome! This quiz will assess your knowledge of Python and AI concepts, then provide you with a personalized learning roadmap.
    """)
    
    with gr.Column(elem_classes=["center-align"]): #Input box and start button in one column.
        user_name = gr.Textbox(
            label="Your Name",
            placeholder="Enter your name here...",
            container=True
        )
        start_button = gr.Button("Start Quiz", variant="primary", size="sm")
    
    # Quiz section (initially hidden)
    with gr.Column(visible=False, elem_classes=["center-align"]) as quiz_section: 
        gr.Markdown("### Answer the Questions")#This column holds the actual quiz UI (initially hidden).


        
        # Create questions with their options
        answer_inputs = []
        
        # Question 1
        gr.Markdown("**Question 1:** What is the correct file extension for Python files?") #This adds each question manually. Followed by appending each radio input to answer_inputs.
        gr.Markdown("a) .pyth  b) .pt  c) .py  d) .pyt")
        q1_answer = gr.Radio(choices=["a", "b", "c", "d"], label="Select your answer for Question 1")
        answer_inputs.append(q1_answer)
        gr.Markdown("---")
        
        # Question 2
        gr.Markdown("**Question 2:** What is the output of print(3 + 2 * 2)?")
        gr.Markdown("a) 10  b) 7  c) 12  d) 9")
        q2_answer = gr.Radio(choices=["a", "b", "c", "d"], label="Select your answer for Question 2")
        answer_inputs.append(q2_answer)
        gr.Markdown("---")
        
        # Question 3
        gr.Markdown("**Question 3:** Which data structure stores key-value pairs?")
        gr.Markdown("a) List  b) Set  c) Tuple  d) Dictionary")
        q3_answer = gr.Radio(choices=["a", "b", "c", "d"], label="Select your answer for Question 3")
        answer_inputs.append(q3_answer)
        gr.Markdown("---")
        
        # Question 4
        gr.Markdown("**Question 4:** Which library is used for numerical computing?")
        gr.Markdown("a) NumPy  b) Seaborn  c) Flask  d) BeautifulSoup")
        q4_answer = gr.Radio(choices=["a", "b", "c", "d"], label="Select your answer for Question 4")
        answer_inputs.append(q4_answer)
        gr.Markdown("---")
        
        # Question 5
        gr.Markdown("**Question 5:** Purpose of the fit() method in ML?")
        gr.Markdown("a) It trains the model  b) It tests the model  c) It saves the model  d) It visualizes the model")
        q5_answer = gr.Radio(choices=["a", "b", "c", "d"], label="Select your answer for Question 5")
        answer_inputs.append(q5_answer)
        gr.Markdown("---")
        
        # Question 6
        gr.Markdown("**Question 6:** What does 'self' refer to in a class method?")
        gr.Markdown("a) The method name  b) The class itself  c) An instance of the class  d) A global variable")
        q6_answer = gr.Radio(choices=["a", "b", "c", "d"], label="Select your answer for Question 6")
        answer_inputs.append(q6_answer)
        gr.Markdown("---")
        
        # Question 7
        gr.Markdown("**Question 7:** Activation function for non-linearity in DNN?")
        gr.Markdown("a) Sigmoid  b) ReLU  c) Tanh  d) All of the above")
        q7_answer = gr.Radio(choices=["a", "b", "c", "d"], label="Select your answer for Question 7")
        answer_inputs.append(q7_answer)
        gr.Markdown("---")
        
        # Question 8
        gr.Markdown("**Question 8:** Technique to prevent overfitting in NNs?")
        gr.Markdown("a) Batch normalization  b) Regularization  c) Dropout  d) Backpropagation")
        q8_answer = gr.Radio(choices=["a", "b", "c", "d"], label="Select your answer for Question 8")
        answer_inputs.append(q8_answer)
        gr.Markdown("---")
        
        # Question 9
        gr.Markdown("**Question 9:** Purpose of gradient descent?")
        gr.Markdown("a) Making decisions  b) Optimizing parameters  c) Increasing complexity  d) Normalizing dataset")
        q9_answer = gr.Radio(choices=["a", "b", "c", "d"], label="Select your answer for Question 9")
        answer_inputs.append(q9_answer)
        gr.Markdown("---")
        
        # Question 10
        gr.Markdown("**Question 10:** Main difference: supervised vs unsupervised learning?")
        gr.Markdown("a) Supervised doesn't use labels  b) Supervised is faster  c) Supervised uses labels  d) No difference")
        q10_answer = gr.Radio(choices=["a", "b", "c", "d"], label="Select your answer for Question 10")
        answer_inputs.append(q10_answer)
        
        submit_button = gr.Button("Submit Quiz", variant="primary") #Button to submit quiz.
    
    # Results section
    with gr.Row():
        results_display = gr.Markdown(label="Your Results") #Final display area for the roadmap and score.
    
    # Event handlers
    start_button.click( #Connects the Start Quiz button to show the questions.
        fn=start_quiz,
        inputs=[user_name],
        outputs=[quiz_section, submit_button]
    )
    
    submit_button.click( #Connects the Submit button to run the backend and show the result.
        fn=submit_quiz,
        inputs=[user_name] + answer_inputs,
        outputs=[results_display]
    )

if __name__ == "__main__":
    demo.launch(share=False, debug=True)
