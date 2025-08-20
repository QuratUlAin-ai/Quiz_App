import React, { useEffect, useMemo, useState } from 'react' // Import React core and specific hooks for state, side effects, and memoization
import { startQuiz, submitQuiz, assignTask, getUsers, getTaskFiles, uploadTaskFile, getTasks as apiGetTasks, submitTask as apiSubmitTask, login as apiLogin, register as apiRegister, me as apiMe, getUserSummary } from './api' // Import all necessary API functions from the local 'api' module

const PAGES = {// Define all possible page states for the application
  WELCOME: 'WELCOME', // Welcome screen
  QUIZ: 'QUIZ', // Quiz-taking screen
  RESULTS: 'RESULTS', // Quiz results screen
  TASK_ASSIGN: 'TASK_ASSIGN', // Assign task screen (admin)
  ADMIN_USERS: 'ADMIN_USERS', // Admin user list screen
  ADMIN_DASHBOARD: 'ADMIN_DASHBOARD', // Admin dashboard screen
  MY_TASKS: 'MY_TASKS', // My tasks screen (user)
  LOADING: 'LOADING', // Generic loading state
  LOGIN: 'LOGIN',  // Login screen
}

export default function App() { // Define and export the main application component
  const [page, setPage] = useState(PAGES.WELCOME)   // Track the current page being displayed
  const [loadingText, setLoadingText] = useState('Loading...') // Track text displayed when loading something
  const [auth, setAuth] = useState(() => { // Retrieve stored authentication details from localStorage
    const token = localStorage.getItem('auth_token')
    const name = localStorage.getItem('auth_name')
    const email = localStorage.getItem('auth_email')
    const role = localStorage.getItem('auth_role') // If token exists, return the auth object; otherwise return null
    return token ? { token, name, email, role } : null
  })

  // Shared state
  const [userName, setUserName] = useState('')   // Track the user's name (shared across features)

  // Quiz state
  const [quiz, setQuiz] = useState(null) // Track quiz data loaded from the server
  const [answers, setAnswers] = useState({}) // Track the user's answers for the quiz

  // Results state
  const [results, setResults] = useState(null)// Track quiz results returned from the server
  const roadmapText = useMemo(() => (results?.roadmap || []).join('\n'), [results])   // Compute and memoize the roadmap text from the quiz results

  // Task assign state
  const [taskUserName, setTaskUserName] = useState('')   // Track task assignment form's "user name" field (admin use)
  const [taskEmail, setTaskEmail] = useState('')   // Track task assignment form's "email" field (admin use)
  const [taskMessage, setTaskMessage] = useState('')   // Track any message related to assigning tasks

  // Admin users list state
  const [adminUsers, setAdminUsers] = useState([])   // Track the list of all users (for admin view)
  const [adminUsersMsg, setAdminUsersMsg] = useState('')   // Track any message related to admin user management

  // Admin dashboard state
  const [dashboardEmail, setDashboardEmail] = useState('')   // Track the email entered into the admin dashboard search
  const [dashboardData, setDashboardData] = useState(null)   // Track the data returned from the admin dashboard for a given user
  const [dashboardMsg, setDashboardMsg] = useState('')// Track any message shown in the admin dashboard

  // Deprecated admin file upload view state removed

  // My tasks (user profiling)
  const [myTasks, setMyTasks] = useState([])// Track tasks assigned to the current logged-in user
  const [myTasksMsg, setMyTasksMsg] = useState('')// Track any message shown in the "My Tasks" section

  // -------- Auth Effects --------
  useEffect(() => {// useEffect hook to check authentication status on first render
    const checkAuth = async () => {// Define an async function to verify authentication
      const token = localStorage.getItem('auth_token')// Get the stored authentication token
      if (!token) { // If no token exists, go to the login page
        setPage(PAGES.LOGIN)
        return
      }
      try { // Fetch the user's profile from the backend
        const profile = await apiMe()
        localStorage.setItem('auth_token', profile.token)// Store updated auth info in localStorage
        localStorage.setItem('auth_name', profile.name)
        localStorage.setItem('auth_email', profile.email)
        localStorage.setItem('auth_role', profile.role)
        setAuth({ token: profile.token, name: profile.name, email: profile.email, role: profile.role })// Update local state with auth details
        setUserName(profile.name || '')// Set the user's name for display purposes
        if (profile.role === 'admin') {// If the user is an admin, load the admin user list and go to admin users page
          await loadAdminUsers()
          setPage(PAGES.ADMIN_USERS)
          return
        }
      } catch (e) {
        // invalid token // If the token is invalid, clear all stored auth data
        localStorage.removeItem('auth_token')
        localStorage.removeItem('auth_name')
        localStorage.removeItem('auth_email')
        localStorage.removeItem('auth_role')
        setAuth(null) // Set auth state to null
        setPage(PAGES.LOGIN)  // Redirect to login page
      }
    }
    checkAuth() // Call the authentication check
    // eslint-disable-next-line react-hooks/exhaustive-deps// Disable linting rule for missing dependency array entries
    // eslint-disable-next-line react-hooks/exhaustive-dep
  }, [])

  const handleLogout = () => { // Function to log the user out// Remove authentication details from localStorage
    localStorage.removeItem('auth_token')
    localStorage.removeItem('auth_name')
    localStorage.removeItem('auth_email')
    localStorage.removeItem('auth_role')
    setAuth(null)  // Reset auth state to null
    setUserName('') // Reset the user name
    setPage(PAGES.LOGIN) // Redirect to the login page
  }

  const openMyTasksPage = async () => {// Function to open the "My Tasks" page and fetch the user's tasks
    if (!auth?.email) return // If user email is not available, exit early
    setLoadingText('Loading your tasks...') // Show loading message specific to fetching tasks
    setPage(PAGES.LOADING) // Switch the app to the loading page
    try {
      const tasks = await apiGetTasks(auth.email)// Fetch tasks from API using the user's email
      setMyTasks(tasks || [])// Store the tasks in state (or empty array if null)
      setMyTasksMsg(tasks?.length ? '' : 'No tasks assigned yet.')// Show message if no tasks were returned
    } catch (e) {
      setMyTasks([])// On error, clear tasks
      setMyTasksMsg('Failed to load tasks.')// Display an error message
    }
    setPage(PAGES.MY_TASKS)// Finally, show the "My Tasks" page
  }

  const uploadMyTaskFile = async (taskNumber, file) => { // Function to upload a file for a specific task
    if (!auth?.email) return // If user email is not available, exit early
    if (!file) { setMyTasksMsg('No file selected.'); return } // If no file is provided, show a message and stop
    const res = await uploadTaskFile(auth.email, taskNumber, file) // Upload the file to the server for the specified task
    setMyTasksMsg(`Task ${taskNumber} file uploaded.`)// Show confirmation message for successful upload
  }

  const markTaskCompleted = async (taskId) => {// Function to mark a task as completed
    if (!auth?.email) return // If user email is not available, exit early
    const res = await apiSubmitTask(auth.email, taskId, 'Completed via button')// Submit the task as completed via API
    setMyTasksMsg(res?.message || 'Task marked as completed.')// Show message from API or a default success message
    // Refresh list
    try { // Refresh the task list to reflect changes
      const tasks = await apiGetTasks(auth.email)// Fetch updated tasks
      setMyTasks(tasks || [])// Update the state with refreshed tasks
    } catch {} // Silently ignore errors here
  }

  const handleLogin = async (email, password) => {// Function to handle user login
    setLoadingText('Signing you in...')// Show loading message for login process
    setPage(PAGES.LOADING) // Switch to the loading page
    const res = await apiLogin(email, password) // Call API to log the user in
    localStorage.setItem('auth_token', res.token)// Save authentication token to local storage
    localStorage.setItem('auth_name', res.name)// Save user's name to local storage
    localStorage.setItem('auth_email', res.email)// Save user's email to local storage
    localStorage.setItem('auth_role', res.role)// Save user's role to local storage
    setAuth({ token: res.token, name: res.name, email: res.email, role: res.role })// Update authentication state in React
    setUserName(res.name || '')// Store user's name in component state
    if (res.role === 'admin') { // If user is an admin, load admin users and switch to admin page
      await loadAdminUsers()
      setPage(PAGES.ADMIN_USERS)
    } else {
      setPage(PAGES.WELCOME)// Otherwise, go to the welcome page
    }
  }

  const handleRegister = async (name, email, password) => {// Function to handle user registration
    setLoadingText('Creating your account...')    // Show loading message for registration process
    setPage(PAGES.LOADING)// Switch to loading page
    const res = await apiRegister(name, email, password)// Call API to register the user
    localStorage.setItem('auth_token', res.token)// Save authentication token to local storage
    localStorage.setItem('auth_name', res.name)// Save user's name to local storage
    localStorage.setItem('auth_email', res.email)// Save user's email to local storage
    localStorage.setItem('auth_role', res.role)// Save user's role to local storage
    setAuth({ token: res.token, name: res.name, email: res.email, role: res.role })// Update authentication state in React
    setUserName(res.name || '')// Store user's name in component state
    if (res.role === 'admin') {// If user is an admin, load admin users and switch to admin page
      await loadAdminUsers()
      setPage(PAGES.ADMIN_USERS)
    } else {
      setPage(PAGES.WELCOME)// Otherwise, go to the welcome page
    }
  }

  const handleStartQuiz = async () => {// Function to start the quiz for the current user
    if (!auth) { setPage(PAGES.LOGIN); return }// If no user is logged in, redirect to login page
    if (auth.role === 'admin') { return }  // If user is admin, do not allow quiz
    const effectiveName = auth?.name || userName // Determine user's name (from auth or manual input)
    if (!effectiveName?.trim()) return // If no valid name, exit early
    setLoadingText('Preparing your quiz...')  // Show loading message while quiz is prepared
    setPage(PAGES.LOADING)// Switch to loading page
    const data = await startQuiz(effectiveName.trim()) // Fetch quiz data from API
    setQuiz(data.quiz) // Store quiz data in state
    setAnswers({})// Reset answers state to empty
    setPage(PAGES.QUIZ)// Switch to quiz page
  }

  const handleSubmitQuiz = async () => {// Function to submit quiz answers
    const answered = Object.keys(answers).length // Count the number of questions answered
    if (answered < 10) { // If fewer than 10 questions answered, show error result
      setResults({ score: 0, level: 'N/A', roadmap: [
        'Please answer all 10 questions before submitting.'
      ]})
      setPage(PAGES.RESULTS)// Switch to results page immediately
      return
    }
    setLoadingText('Submitting your quiz...')// Show loading message for quiz submission
    setPage(PAGES.LOADING)// Switch to loading page
    const effectiveName = auth?.name || userName// Determine effective name to send with submission
    const data = await submitQuiz(effectiveName, answers)// Send answers to the API
    setResults(data)// Store results returned by the API
    setPage(PAGES.RESULTS)// Switch to results page
  }

  // --- Roadmap rendering helpers ---
  const parseRoadmap = (lines) => {// Function to parse a roadmap text into structured sections and items
    const sections = []// Array to hold all parsed sections
    let currentSection = null// Variable to store the section currently being processed
    let currentItem = null// Variable to store the current item (topic) being processed

    const commitItem = () => {// Helper function to finalize and store the current item into the current section
      if (currentItem && currentSection) {// Only push item if it exists and a section is active
        currentSection.items.push(currentItem)
      }
      currentItem = null// Reset current item after storing
    }
    const commitSection = () => {// Helper function to finalize and store the current section into the sections array
      commitItem()// First commit any pending item before ending the section
      if (currentSection) sections.push(currentSection)// Push the section into the sections array if it exists
      currentSection = null// Reset current section after storing
    }

    const isWrappedBold = (s) => s.startsWith('**') && s.endsWith('**') // Checks if a string is wrapped in **bold markdown**
    const unwrapBold = (s) => s.replace(/^\*\*/, '').replace(/\*\*$/, '').trim() // Removes ** markers from start and end of a bold string

    lines.forEach((raw) => {// Iterate through each line of the roadmap text
      const line = (raw || '').trim()// Trim whitespace and ensure we’re working with a safe string
      if (!line) return// Skip empty lines

      if (isWrappedBold(line)) {// If the line is bold, it could be a section title or an item title
        const text = unwrapBold(line) // Remove bold markers and get clean text
        const lower = text.toLowerCase()// Convert text to lowercase for keyword checking
        const isSection = lower.includes('weak areas') || lower.includes('strong areas')// Determine if this is a "section" header (weak areas / strong areas)
        if (isSection) {
          commitSection()// End the previous section before starting a new one
          currentSection = { title: text, items: [] }// Create a new section with an empty items list
          return
        }
        // Otherwise treat as an item title (e.g., "1. Topic ...")
        commitItem()// Otherwise treat as an item title under the current section
        currentItem = { title: text, bullets: [] }// Create a new item with an empty bullet list
        return
      }

      // Bullets like "• something" or "- something"
      const bulletMatch = line.match(/^([•\-])\s*(.*)$/)// Detect bullet points starting with • or -
      if (bulletMatch) {
        if (!currentItem) currentItem = { title: '', bullets: [] }// If no current item exists, create a placeholder item
        currentItem.bullets.push(bulletMatch[2])// Add the bullet text to the current item’s bullets array
        return
      }
    })

    commitSection() // Commit the last section after processing all lines
    return sections// Return the fully structured sections array
  }

  const RoadmapView = ({ lines }) => {// React component to display the parsed roadmap in a styled layout
    const sections = useMemo(() => parseRoadmap(lines || []), [lines])// Use useMemo to parse roadmap only when lines change
    if (!sections.length) return <pre style={{ wordWrap: 'break-word', whiteSpace: 'pre-wrap' }}>{(lines || []).join('\n')}</pre>// If no sections found, render raw text with wrapping
    return (// Otherwise, render roadmap sections and items
      <div className="roadmap">
        {sections.map((sec, si) => (
          <div key={si} className="roadmap-section">
            <div className="roadmap-title">{sec.title}</div>
            {sec.items.map((it, ii) => (
              <div key={ii}>
                {it.title && <div className="roadmap-item">{it.title}</div>}
                {!!it.bullets.length && (
                  <ul className="roadmap-list">
                    {it.bullets.map((b, bi) => (
                      <li key={bi} style={{ wordWrap: 'break-word', maxWidth: '100%' }}>
                        {b}
                      </li>
                    ))}
                  </ul>
                )}
              </div>
            ))}
          </div>
        ))}
      </div>
    )
  }

  const handleAssignTask = () => { // Function to open the task assignment page and prefill with current user's info
    const defaultName = auth?.name || userName// Default to current auth name or manually entered name
    const defaultEmail = auth?.email || ''// Default to current auth email or empty string
    setTaskUserName(defaultName)// Store the task user name in state
    setTaskEmail(defaultEmail)// Store the task user email in state
    setTaskMessage('')// Clear any existing task message
    setPage(PAGES.TASK_ASSIGN)// Switch to the task assignment page
  }
  const loadAdminUsers = async () => {// Function to load the list of admin users from API
    try {
      const list = await getUsers() // Fetch users from API
      setAdminUsers(list || [])// Store the list in state, defaulting to empty array if null
      setAdminUsersMsg(list?.length ? '' : 'No users found.') // Show message if no users were found
    } catch (e) {
      setAdminUsers([])// On error, clear admin users
      setAdminUsersMsg('Failed to load users.')// Show error message for failed fetch
    }
  }

  const openAdminDashboardForEmail = async (email) => {// Async function to open the admin dashboard for a specific user's email
    setLoadingText('Loading dashboard...')// Show loading message while fetching dashboard data
    setPage(PAGES.LOADING)// Navigate to loading page
    try {
      const data = await getUserSummary(email)// Fetch the summary data for the given user email
      setDashboardEmail(email)// Store the selected dashboard email in state
      setDashboardData(data)// Store the retrieved dashboard data in state
      setDashboardMsg('')// Clear any previous dashboard error message
    } catch (e) {
      setDashboardEmail(email)// Store the email even if data retrieval failed
      setDashboardData(null)// Clear dashboard data on failure
      setDashboardMsg('Could not load user dashboard.')// Set an error message indicating the dashboard couldn't load
    }
    setPage(PAGES.ADMIN_DASHBOARD)// Navigate to the admin dashboard page
  }


  const submitAssignTask = async () => {// Async function to handle task assignment submission
    if (!taskUserName.trim() || !taskEmail.trim()) {// Validate that both name and email are entered (non-empty after trimming)
      setTaskMessage('Please enter both name and email.')// Show error if name or email is missing
      return// Stop execution if validation fails
    }
    setLoadingText('Assigning your task...')// Show loading message while assigning task
    setPage(PAGES.LOADING)// Navigate to loading page
    const result = await assignTask(taskUserName.trim(), taskEmail.trim())// Call backend to assign task using trimmed name and email
    if (result.error) {// If the backend returned an error
      setTaskMessage(`Task Assignment Error: ${result.message}`) // Show a detailed error message
    } else {
      const lines = [// Prepare a list of message lines to display to the user
        `Task #${result.task_number} assigned to ${taskUserName}.`, // Show assigned task number
        '',// Blank line for spacing
        'Task Description:',  // Label for the task description section
        result.task_description,  // Show the actual task description
        '',// Blank line for spacing
        `Due Date: ${result.due_date}`,  // Show task due date
        result.email_sent ? `An email has been sent to ${taskEmail}.` : 'Email delivery failed. Check email settings.',// Show whether an email was successfully sent
      ]
      setTaskMessage(lines.join('\n'))// Join all message lines into a single string separated by newlines
    }
    setPage(PAGES.TASK_ASSIGN)// Return to the task assignment page with the result
  }

  // Task display component for better formatting
  const TaskDisplay = ({ taskMessage }) => { // React component to neatly display a task message
    if (!taskMessage) return null // If no task message exists, don't render anything
    
    const lines = taskMessage.split('\n') // Split the task message into individual lines
    const sections = [] // Array to hold sections of related lines
    let currentSection = [] // Array to hold the lines of the currently processed section
    
    lines.forEach((line, index) => {  // Iterate through each line of the message
      if (line === 'Task Description:' || line === 'Due Date:' || line.startsWith('Task #') || line.startsWith('An email') || line.startsWith('Email delivery')) { // If the line marks a new section or important label// Section for task description// Section for due date// Section for task header// Section for email status// Section for email failure status
        if (currentSection.length > 0) {// If there are lines in the current section, store them first
          sections.push(currentSection)
        }
        currentSection = [line]// Start a new section containing only the current line
      } else if (line.trim() === '') { // If the line is empty, it signals the end of a section
        if (currentSection.length > 0) { // Store the current section if it has content
          sections.push(currentSection)
          currentSection = [] // Reset section for new lines
        }
      } else { // Otherwise, add the line to the current section
        currentSection.push(line)
      }
    })
    
    if (currentSection.length > 0) {// After loop, if there's still a section in progress, store it
      sections.push(currentSection)
    }
    
    return ( // Render the task message sections into styled HTML
      <div className="task-display">
        {sections.map((section, sectionIndex) => (
          <div key={sectionIndex} className="task-section">
            {section.map((line, lineIndex) => {
              if (line === 'Task Description:') {
                return <h4 key={lineIndex} className="task-section-title">{line}</h4>
              } else if (line === 'Due Date:') {
                return <h4 key={lineIndex} className="task-section-title">{line}</h4>
              } else if (line.startsWith('Task #')) {
                return <div key={lineIndex} className="task-header">{line}</div>
              } else if (line.startsWith('An email') || line.startsWith('Email delivery')) {
                return <div key={lineIndex} className="task-status">{line}</div>
              } else if (line.trim() === '') {
                return <div key={lineIndex} className="task-spacer"></div>
              } else if (line.includes(':')) {
                return <div key={lineIndex} className="task-info">{line}</div>
              } else {
                return <div key={lineIndex} className="task-description">{line}</div>
              }
            })}
          </div>
        ))}
      </div>
    )
  }

  const handleViewAllUsers = async () => {// Async function to handle viewing all users (admin only)
    if (!auth || auth.role !== 'admin') return// Check if the user is authenticated and has the 'admin' role
    const names = await getUsers()// Fetch the list of user names from the backend
    setUsers(names)// Save the retrieved names in state
    if (!names || names.length === 0) {  // If no users are found or the list is empty
      setUserListMarkdown('No users found in the database.')  // Display a message saying no users are found
    } else {
      const md = ['### Available Users', ''] // Create a markdown array starting with a heading
      names.forEach((n, i) => md.push(`${i + 1}. ${n}`))// Add each user to the markdown list with a numbering
      setUserListMarkdown(md.join('\n'))// Convert the markdown array into a single string and save it
    }
    setPage(PAGES.USER_LIST) // Navigate to the user list page
  }

  const openUserTasks = (name) => {// Function to open a specific user's tasks
    if (!name) return  // If no name is provided, do nothing
    setSelectedUser(name)// Store the selected user's name
    setSelectedEmail('')// Reset the selected email to empty
    setUserTaskMsg('')// Clear any user task messages
    setFile1Url('')// Clear URL for the first file
    setFile2Url('')// Clear URL for the second file
    setPage(PAGES.USER_TASKS) // Navigate to the user tasks page
  }

  const refreshFiles = async (email) => { // Async function to refresh the files linked to a specific email
    if (!email.trim()) { setFile1Url(''); setFile2Url(''); return } // If the email is empty after trimming// Clear both file URLs// Stop execution here
    const files = await getTaskFiles(email.trim()) // Fetch task files for the given email
    setFile1Url(files.task1 || '') // Set the first file URL or empty string if not found
    setFile2Url(files.task2 || '')// Set the second file URL or empty string if not found
  }

  const onEmailChange = async (val) => {// Async function to handle changes in the email field
    setSelectedEmail(val)// Update the selected email value in state
    await refreshFiles(val)// Refresh files associated with the new email
  }

  const submitTaskFile = async (taskNumber, file) => {// Async function to handle uploading a task file
    if (!selectedEmail.trim()) { setUserTaskMsg('Enter your email first.'); return }// If email is empty, show a message and stop
    if (!file) { setUserTaskMsg('No file selected.'); return }// If no file is selected, show a message and stop
    const res = await uploadTaskFile(selectedEmail.trim(), taskNumber, file) // Upload the task file for the given email and task number
    setUserTaskMsg(`Task ${taskNumber} file uploaded.`)// Show a success message
    if (taskNumber === 1) setFile1Url(res.file_url)// If the uploaded file is for Task 1, update File 1 URL
    if (taskNumber === 2) setFile2Url(res.file_url)// If the uploaded file is for Task 2, update File 2 URL
  }

  // --- Login View ---
  const LoginView = ({ onLogin, onRegister }) => {
    const [email, setEmail] = useState('')// State to store email input
    const [password, setPassword] = useState('') // State to store password input
    const [name, setName] = useState('') // State to store name input (for registration)
    const [mode, setMode] = useState('login') // 'login' | 'register'  // State to track mode: 'login' or 'register'
    const [error, setError] = useState('')// State to store error messages

    const submit = async () => {// Function to handle form submission
      try {
        setError('') // Clear any previous error
        if (mode === 'login') {// If in login mode, call onLogin function
          await onLogin(email, password)
        } else {
          await onRegister(name, email, password)// If in register mode, call onRegister function
        }
      } catch (e) {
        setError(e?.response?.data?.detail || 'Authentication failed')// Show an error message from server or a fallback message
      }
    }

    return (// JSX for the login/register form
      <div>
        <h3>{mode === 'login' ? 'Sign In' : 'Create Account'}</h3>
        {mode === 'register' && (
          <>
            <label>Name</label>
            <input value={name} onChange={(e) => setName(e.target.value)} placeholder="Your name" />
          </>
        )}
        <label>Email</label>
        <input value={email} onChange={(e) => setEmail(e.target.value)} placeholder="you@example.com" />
        <label>Password</label>
        <input type="password" value={password} onChange={(e) => setPassword(e.target.value)} placeholder="Your password" />
        <div className="row" style={{ marginTop: 8 }}>
          <button className="btn primary" onClick={submit}>{mode === 'login' ? 'Login' : 'Register'}</button>
          <button className="btn" onClick={() => setMode(mode === 'login' ? 'register' : 'login')}>
            {mode === 'login' ? 'Create account' : 'Have an account? Sign in'}
          </button>
        </div>
        {error && <div style={{ color: '#dc2626', marginTop: 8 }}>{error}</div>}
      </div>
    )
  }

  return (// JSX for main container
    <div className="main-container">
      {/* Top Right Dropdown */}
      {auth && (
        <div style={{ position: 'fixed', top: 12, right: 12 }}>
          <div className="content-box" style={{ margin: 0, padding: 8, minHeight: 'auto' }}>
            <div style={{ position: 'relative' }}>
              <details>
                <summary style={{ listStyle: 'none', cursor: 'pointer' }}>
                  <span style={{ fontSize: 14, color: '#555' }}>
                    {auth.name} ({auth.role})
                  </span>
                </summary>
                <div style={{ marginTop: 8, display: 'flex', flexDirection: 'column', gap: 6 }}>
                  {auth.role === 'admin' && (
                    <button className="btn sm" onClick={async () => { await loadAdminUsers(); setPage(PAGES.ADMIN_USERS) }}>Users</button>
                  )}
                  {auth.role !== 'admin' && (
                    <button className="btn sm" onClick={openMyTasksPage}>My Tasks</button>
                  )}
                  <button className="btn sm" onClick={handleLogout}>Logout</button>
                </div>
              </details>
            </div>
          </div>
        </div>
      )}
      {/* Login Page */}
      {page === PAGES.LOGIN && (
        <div className="page-container login-page">
          <div className="content-box">
            <LoginView onLogin={handleLogin} onRegister={handleRegister} />
          </div>
        </div>
      )}

      {/* Welcome Page */}
      {page === PAGES.WELCOME && auth && (
        <div className="page-container welcome-page">
          <div className="content-box">
            <div>
              <h1>Learning Quiz</h1>
              <p>Welcome! This quiz will assess your knowledge of Python and AI concepts, then provide you with a personalized learning roadmap.</p>
            </div>
            <div>
              <label>Your Name</label>
              <input value={auth?.name || userName} readOnly placeholder="Your name" />
              {auth.role !== 'admin' && (
                <button className="btn primary" onClick={handleStartQuiz}>Start Quiz</button>
              )}
            </div>
          </div>
        </div>
      )}

      {/* Quiz Page */}
      {page === PAGES.QUIZ && quiz && (
        <div className="page-container quiz-page">
          <div className="content-box">
            <h3>Answer the Questions</h3>
            {Object.entries(quiz).map(([qNo, q]) => (
              <div key={qNo} className="question-container">
                <div style={{ marginBottom: '12px' }}>
                  <strong>Question {qNo}:</strong> {q.text}
                </div>
                <div className="options-list">
                  {Object.keys(q.options).map((opt) => (
                    <label key={opt} className="option-row">
                      <input
                        type="radio"
                        name={`q_${qNo}`}
                        checked={answers[qNo] === opt}
                        onChange={() => setAnswers((prev) => ({ ...prev, [qNo]: opt }))}
                      />
                      <span className="option-letter">{opt})</span>
                      <span className="option-text">{q.options[opt]}</span>
                    </label>
                  ))}
                </div>
              </div>
            ))}
            <button className="btn primary" onClick={handleSubmitQuiz}>Submit Quiz</button>
          </div>
        </div>
      )}

      {/* Results Page */}
      {page === PAGES.RESULTS && results && (
        <div className="page-container results-page">
          <div className="content-box">
            <div>
              <h2>Quiz Results for {userName}</h2>
              <p><strong>Score:</strong> {results.score}/10</p>
              <p><strong>Level:</strong> {results.level}</p>
              <hr />
              <h3>Your Personalized Learning Roadmap</h3>
              <RoadmapView lines={results.roadmap} />
            </div>
            <div className="row" style={{ marginTop: 16 }}>
              <button className="btn secondary" onClick={() => setPage(PAGES.WELCOME)}>Take Quiz Again</button>
              <button className="btn primary" onClick={handleAssignTask}>Assign Task</button>
            </div>
          </div>
        </div>
      )}

      {/* Loading Page */}
      {page === PAGES.LOADING && (
        <div className="page-container loading-page">
          <div className="content-box" style={{ alignItems: 'center', textAlign: 'center' }}>
            <div className="spinner" />
            <div style={{ marginTop: 8, color: '#555' }}>{loadingText}</div>
          </div>
        </div>
      )}

      {/* Task Assignment Page */}
      {page === PAGES.TASK_ASSIGN && auth && (
        <div className="page-container task-page">
          <div className="content-box">
            <h3>Assign Learning Task</h3>
            <p>Enter your email to receive personalized learning tasks based on your quiz performance.</p>
            <div>
              <label>Your Name</label>
              <input value={taskUserName} onChange={(e) => setTaskUserName(e.target.value)} placeholder="Enter your name..." readOnly={auth.role !== 'admin'} />
              <label>Your Email</label>
              <input value={taskEmail} onChange={(e) => setTaskEmail(e.target.value)} placeholder="Enter your email address..." readOnly={auth.role !== 'admin'} />
              <button className="btn primary" onClick={submitAssignTask}>Assign Task</button>
            </div>
            {taskMessage && <TaskDisplay taskMessage={taskMessage} />}
             {auth.role === 'admin' && (
               <button className="btn sm secondary" style={{ marginTop: 12 }} onClick={() => setPage(PAGES.ADMIN_DASHBOARD)}>Open Admin Dashboard</button>
             )}
            <button className="btn sm" style={{ marginTop: 12 }} onClick={openMyTasksPage}>Open My Tasks</button>
          </div>
        </div>
      )}

      {/* Admin Users List */}
      {page === PAGES.ADMIN_USERS && auth?.role === 'admin' && (
        <div className="page-container admin-users-page">
          <div className="content-box">
            <h3>All Users</h3>
            {!adminUsers?.length && <p>{adminUsersMsg || 'No users found.'}</p>}
            {!!adminUsers?.length && (
              <ul className="user-list">
                {adminUsers.map((u, i) => (
                  <li key={u.email}>
                    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 12 }}>
                      <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                        <span style={{ fontWeight: 600, color: '#666' }}>{i + 1}.</span>
                        <div style={{ display: 'flex', flexDirection: 'column' }}>
                          <span style={{ fontWeight: 600 }}>{u.name}</span>
                          <span style={{ color: '#6b7280', fontSize: 12 }}>{u.email}</span>
                        </div>
                      </div>
                      <button className="btn sm primary" onClick={() => openAdminDashboardForEmail(u.email)}>Open Dashboard</button>
                    </div>
                  </li>
                ))}
              </ul>
            )}
          </div>
        </div>
      )}

      {/* Admin Dashboard (per user) */}
      {page === PAGES.ADMIN_DASHBOARD && auth?.role === 'admin' && (
        <div className="page-container admin-dashboard-page">
          <div className="content-box">
            <h3>User Dashboard (Admin)</h3>
            <label>User Email</label>
            <input value={dashboardEmail} onChange={(e) => setDashboardEmail(e.target.value)} placeholder="user@example.com" />
            <div className="row">
              <button
                className="btn primary"
                onClick={async () => {
                  if (!dashboardEmail.trim()) { setDashboardMsg('Enter an email first.'); return }
                  setDashboardMsg('')
                  try {
                    const data = await getUserSummary(dashboardEmail.trim())
                    setDashboardData(data)
                    if (!data?.tasks?.length) setDashboardMsg('No tasks for this user yet.')
                  } catch (e) {
                    setDashboardData(null)
                    setDashboardMsg('Could not load user dashboard.')
                  }
                }}
              >Load Dashboard</button>
              <button className="btn" onClick={async () => { await loadAdminUsers(); setPage(PAGES.ADMIN_USERS) }}>Back to Users</button>
            </div>

            {dashboardData && (
              <div style={{ marginTop: 16, display: 'flex', flexDirection: 'column', gap: 16 }}>
                <div className="question-container" style={{ background: '#fff' }}>
                  <div style={{ fontWeight: 600, marginBottom: 8 }}>{dashboardData.name || 'Unknown User'} ({dashboardData.email})</div>
                  <div className="row">
                    <div><strong>Quiz Score:</strong> {dashboardData.quiz?.score ?? '—'}/10</div>
                    <div><strong>Level:</strong> {dashboardData.quiz?.level ?? '—'}</div>
                  </div>
                  <div className="row" style={{ marginTop: 8 }}>
                    <div><strong>Tasks Assigned:</strong> {dashboardData.tasks_assigned}</div>
                    <div><strong>Tasks Completed:</strong> {dashboardData.tasks_completed}</div>
                  </div>
                </div>

                {!!dashboardData.tasks?.length && dashboardData.tasks.map((t) => (
                  <div key={t.id} className="question-container" style={{ background: '#fff' }}>
                    <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', alignItems: 'center' }}>
                      <strong>Task #{t.task_number}</strong>
                      <span style={{ color: '#6b7280' }}>Due: {t.due_date}</span>
                      <span style={{ color: t.status === 'completed' ? '#16a34a' : '#6b7280' }}>Status: {t.status}</span>
                      <span style={{ color: '#6b7280' }}>Submitted: {t.status === 'completed' ? 'Yes' : 'No'}</span>
                    </div>
                    <div className="task-description" style={{ marginTop: 8 }}>{t.description}</div>
                    {t.file_url ? (
                      <div style={{ marginTop: 8 }}>
                        <a href={t.file_url} target="_blank" rel="noreferrer">View Uploaded File</a>
                      </div>
                    ) : (
                      <div style={{ marginTop: 8, color: '#6b7280' }}>No file uploaded.</div>
                    )}
                    {t.status !== 'completed' && (
                      <div style={{ marginTop: 8, color: '#6b7280' }}>User has not marked this task as completed yet.</div>
                    )}
                  </div>
                ))}
              </div>
            )}
            {dashboardMsg && <div style={{ marginTop: 12 }}><pre>{dashboardMsg}</pre></div>}
          </div>
        </div>
      )}

      {/* My Tasks (User Profiling) */}
      {page === PAGES.MY_TASKS && auth && (
        <div className="page-container my-tasks-page">
          <div className="content-box">
            <h3>My Tasks</h3>
            {!myTasks?.length && <p>{myTasksMsg || 'No tasks assigned yet.'}</p>}
            {!!myTasks?.length && (
              <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
                {myTasks.map((t) => (
                  <div key={t.id} className="question-container" style={{ background: '#fff' }}>
                    <div style={{ marginBottom: 8, display: 'flex', flexWrap: 'wrap', gap: 8, alignItems: 'center' }}>
                      <strong>Task #{t.task_number}</strong>
                      <span style={{ color: '#6b7280' }}>Due: {t.due_date}</span>
                      <span style={{ color: t.status === 'completed' ? '#16a34a' : '#6b7280' }}>Status: {t.status}</span>
                    </div>
                    <div className="task-description" style={{ marginTop: 8 }}>{t.description}</div>
                    <div className="row" style={{ marginTop: 12, alignItems: 'center' }}>
                      <div>
                        <label>Upload Task File</label>
                        <input type="file" onChange={(e) => uploadMyTaskFile(t.task_number, e.target.files?.[0])} />
                      </div>
                    </div>
                    <div style={{ marginTop: 8 }}>
                      <label>Task completed?</label>
                      <div className="row">
                        <button className="btn sm primary" onClick={() => markTaskCompleted(t.id)} disabled={t.status === 'completed'}>Yes</button>
                        <button className="btn sm" onClick={() => setMyTasksMsg('Kept as not completed.')}>No</button>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            )}
            {myTasksMsg && <div style={{ marginTop: 12 }}><pre>{myTasksMsg}</pre></div>}
          </div>
        </div>
      )}
    </div>
  )
}


