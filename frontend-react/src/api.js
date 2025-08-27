import axios from 'axios' // Import the axios HTTP client library for making API requests
// Define the base URL for API requests from environment variables, 
// falling back to 'http://localhost:8000' if not set
const API_BASE = import.meta.env.VITE_API_BASE || 'http://localhost:8000'

  // Create a reusable axios instance configured with the base URL
export const api = axios.create({  
  baseURL: API_BASE,
})

// Attach Authorization header automatically if token exists. 
// Add a request interceptor to automatically attach the Authorization header if a token exists
api.interceptors.request.use((config) => {  
  const token = localStorage.getItem('auth_token') // Retrieve the JWT token from localStorage
  if (token) { // If a token is found, ensure headers exist and set Authorization to "Bearer <token>"
    config.headers = config.headers || {}
    config.headers['Authorization'] = `Bearer ${token}`
  }
  return config // Return the updated request configuration
})

export const startQuiz = async (userName) => { // Start a new quiz for a given user
  const { data } = await api.post('/quiz/start', { user_name: userName })  // Send POST request to '/quiz/start' with the user's name
  return data // Return the server's response data
}

export const submitQuiz = async (userName, answers) => { // Submit quiz answers for a user
  const { data } = await api.post('/quiz/submit', { // Send POST request to '/quiz/submit' with user name and answers
    user_name: userName,
    user_answers: answers,
  })
  return data // Return the server's response data
}

export const assignTask = async (userName, userEmail, durationWeeks = 4) => { // Assign a task to a user based on their quiz results
  const { data } = await api.post('/tasks/assign', { // Send POST request to '/tasks/assign' with the user's name and email
    user_name: userName,
    user_email: userEmail,
    duration_weeks: durationWeeks,
  })
  return data // Return the assigned task data from the server
}

export const getTasks = async (email) => { // Get all tasks for a specific user
  const { data } = await api.get('/tasks', { params: { user_email: email } })   // Send GET request to '/tasks' with the user's email as a query parameter
  return data // Return the list of tasks
}

export const submitTask = async (email, taskId, submission) => { // Submit a completed task for a user
  const { data } = await api.post('/tasks/submit', { // Send POST request to '/tasks/submit' with email, task ID, and submission content
    user_email: email,
    task_id: taskId,
    submission_content: submission,
  })
  return data // Return the server's response (success/failure)
}

export const getUsers = async () => { // Retrieve the list of all non-admin users (Admin only)
  const { data } = await api.get('/admin/users') // Send GET request to '/admin/users'
  return data.users  // Return only the "users" array from the response
}

export const getTaskFiles = async (email) => { // Get file URLs for tasks submitted by a specific user
  const { data } = await api.get('/tasks/files', { params: { user_email: email } }) // Send GET request to '/tasks/files' with the user's email
  return data// Return the file URLs for tasks
}

export const uploadTaskFile = async (email, taskNumber, file) => { // Upload a file for a specific task
  const form = new FormData()  // Create a new FormData object for file upload
  form.append('user_email', email) // Append the user email to the form
  form.append('task_number', String(taskNumber))  // Append the task number (as string) to the form
  form.append('file', file)  // Append the file object to the form
  const { data } = await api.post('/tasks/upload', form, {  // Send POST request to '/tasks/upload' with multipart/form-data headers
    headers: { 'Content-Type': 'multipart/form-data' },
  })
  return data   // Return the server's response (uploaded file URL)
}

// ---------- Auth APIs ----------
export const login = async (email, password) => { // Log in a user with email and password
  const { data } = await api.post('/auth/login', { email, password }) // Send POST request to '/auth/login' with email and password
  return data  // Return the authentication response (token and user info)
}

export const register = async (name, email, password, role = 'user') => { // Register a new user (role can be provided if admin)
  // Optional: role honored only when caller is admin
  const { data } = await api.post('/auth/register', { name, email, password, role }) // Send POST request to '/auth/register' with user details
  return data // Return the authentication response
}

export const me = async () => { // Get the currently logged-in user's info (requires authentication)
  const { data } = await api.get('/auth/me') // Send GET request to '/auth/me'
  return data // Return the user data
}

// ---------- Admin APIs ----------
export const getUserSummary = async (email) => { // Retrieve detailed summary of a user (Admin only)
  const { data } = await api.get('/admin/user_summary', { params: { user_email: email } }) // Send GET request to '/admin/user_summary' with the user's email
  return data  // Return the detailed user summary from the server
}

export const mySummary = async () => { // Get current user's latest quiz and tasks
  const { data } = await api.get('/user/summary')
  return data
}




