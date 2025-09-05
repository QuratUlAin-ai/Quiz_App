# Email Setup for PLP Task Manager

This document explains how to set up and use the email functionality in the PLP (Personalized Learning Platform) Task Manager.

## Features

- **Automatic Task Assignment Emails**: Users receive formatted emails when tasks are assigned
- **Task Submission Confirmation Emails**: Users receive confirmation emails when they submit tasks
- **Structured Email Content**: Roadmaps and tasks are formatted with minimal, clean styling
- **HTML Email Support**: Rich, responsive email templates

## Setup

### 1. Environment Variables

Create a `.env` file in the root directory with the following variables:

```bash
# Email Configuration
EMAIL_ADDRESS=your-email@gmail.com
EMAIL_PASSWORD=your-app-password
```

### 2. Gmail App Password

For Gmail, you need to use an "App Password" instead of your regular password:

1. Enable 2-Factor Authentication on your Google account
2. Go to Google Account settings → Security → App passwords
3. Generate a new app password for "Mail"
4. Use this 16-character password in your `.env` file

### 3. SMTP Configuration

The system is configured to use Gmail's SMTP server:
- Server: `smtp.gmail.com`
- Port: `587`
- Security: TLS

## Email Templates

### Task Assignment Email

When a task is assigned, users receive an email containing:

- **Header**: Personalized greeting with user's name
- **Task Section**: Formatted task description with clear structure
- **Due Date**: Highlighted due date information
- **Roadmap Section**: User's personalized learning roadmap
- **Instructions**: How to submit the task

### Task Submission Confirmation Email

When a task is submitted, users receive:

- **Confirmation**: Task submission status
- **Next Steps**: What happens after submission
- **Encouragement**: Motivational message

## Email Formatting

### Roadmap Formatting

The system automatically formats roadmap text with:

- **Section Headers**: "Weak Areas" and "Strong Areas" with blue borders
- **Numbered Items**: Main topics with proper hierarchy
- **Bullet Points**: Sub-items with consistent styling
- **Clean Spacing**: Minimal, readable layout

### Task Formatting

Task descriptions are formatted with:

- **Learning Objectives**: Clear goals section
- **Instructions**: Step-by-step guidance
- **Resources**: Suggested materials and tools
- **Time Estimates**: Expected completion time

## Testing

### 1. Run the Test Script

```bash
python test_email.py
```

This will test:
- Email configuration
- Roadmap formatting
- Task formatting
- Email sending (optional)

### 2. Test in the Application

1. Start the backend server
2. Take a quiz and get assigned a task
3. Check if the email is received
4. Verify the formatting is correct

## Troubleshooting

### Common Issues

1. **Authentication Failed**
   - Verify your email and app password
   - Ensure 2FA is enabled on your Google account

2. **Email Not Sent**
   - Check the console for error messages
   - Verify environment variables are loaded
   - Check if the email address is valid

3. **Poor Formatting**
   - Ensure the roadmap text follows the expected format
   - Check if the task description is properly structured

### Debug Mode

Enable debug logging by checking the console output when emails are sent. The system will show:
- Email configuration status
- SMTP connection details
- Success/failure messages

## Security Notes

- Never commit your `.env` file to version control
- Use app passwords instead of regular passwords
- Regularly rotate your app passwords
- Monitor email sending logs for unusual activity

## Customization

### Email Styling

You can customize email appearance by modifying the CSS in the `format_roadmap_for_email()` and `format_task_for_email()` methods in `task_manager.py`.

### Email Content

Modify the email templates in the `assign_task()` and `submit_task()` methods to change the content and structure of emails.

## Support

If you encounter issues:

1. Check the console output for error messages
2. Verify your email configuration
3. Test with the provided test script
4. Check the email formatting methods for syntax errors
