# AI Learning Quiz Application

This is an AI-powered quiz application that assesses your knowledge of Python and AI concepts, then provides a personalized learning roadmap.

## Features

- **Interactive Quiz**: 10 questions covering Python and AI concepts
- **Personalized Assessment**: Determines your proficiency level (Beginner/Intermediate/Advanced)
- **AI-Generated Roadmap**: Creates a customized learning plan based on your performance
- **Modern UI**: Clean Gradio interface with step-by-step workflow

## Setup Instructions

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

### 2. Environment Setup

Create a `.env` file in the root directory with your OpenAI API key:

```
OPENAI_API_KEY=your_openai_api_key_here
```

### 3. Run the Application

```bash
cd frontend
python app.py
```

The application will start and be available at `http://localhost:7860`

## How to Use

1. **Enter Your Name**: Start by entering your name in the text field
2. **Start Quiz**: Click the "Start Quiz" button to begin
3. **Answer Questions**: Answer all 10 multiple-choice questions
4. **Submit Quiz**: Click "Submit Quiz" to get your results
5. **View Roadmap**: See your score, level, and personalized learning roadmap

## Project Structure

```
PLP/
├── backend/
│   └── node_funcs.py      # Backend logic and quiz engine
├── frontend/
│   └── app.py            # Gradio UI interface
├── requirements.txt       # Python dependencies
├── user_learning.db      # SQLite database for storing results
└── README.md            # This file
```

## Technical Details

- **Backend**: Uses LangGraph for workflow management and OpenAI GPT-4 for generating personalized roadmaps
- **Frontend**: Gradio-based web interface
- **Database**: SQLite for storing user results and learning roadmaps
- **AI Integration**: OpenAI API for intelligent assessment and roadmap generation

## Quiz Topics Covered

The quiz covers various topics including:
- Python syntax and file handling
- Data structures and algorithms
- Machine learning concepts
- Deep learning fundamentals
- Object-oriented programming
- Optimization techniques 