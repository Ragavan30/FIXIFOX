import os
from groq import Groq
import google.generativeai as genai
import streamlit as st
from dotenv import load_dotenv
import google.generativeai as genai
import sqlite3
import hashlib
import re
from datetime import datetime
import os

# Load environment variables
load_dotenv()

# Database setup
def init_db():
    conn = sqlite3.connect("fixifox_users.db")
    c = conn.cursor()
    c.execute('''
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE NOT NULL,
        password_hash TEXT NOT NULL,
        email TEXT UNIQUE NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        last_login TIMESTAMP
    )
    ''')
    conn.commit()
    conn.close()

# Password hashing function
def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

# User registration function
def register_user(username, email, password):
    conn = sqlite3.connect('fixifox_users.db')
    c = conn.cursor()
    try:
        hashed_password = hash_password(password)
        c.execute("INSERT INTO users (username, email, password_hash) VALUES (?, ?, ?)", 
                  (username, email, hashed_password))
        conn.commit()
        success = True
        message = "Registration successful! Please log in."
    except sqlite3.IntegrityError:
        success = False
        message = "Username or email already exists!"
    finally:
        conn.close()
    return success, message

# User login function
def login_user(username, password):
    conn = sqlite3.connect('fixifox_users.db')
    c = conn.cursor()
    hashed_password = hash_password(password)
    c.execute("SELECT id FROM users WHERE username = ? AND password_hash = ?", (username, hashed_password))
    user = c.fetchone()
    
    if user:
        # Update last login time
        c.execute("UPDATE users SET last_login = ? WHERE id = ?", 
                 (datetime.now().strftime("%Y-%m-%d %H:%M:%S"), user[0]))
        conn.commit()
        success = True
        message = "Login successful!"
    else:
        success = False
        message = "Invalid username or password!"
    
    conn.close()
    return success, message

# Email validation
def is_valid_email(email):
    pattern = r'^[\w\.-]+@[\w\.-]+\.\w+$'
    return bool(re.match(pattern, email))

# Password validation
def is_strong_password(password):
    # At least 8 characters, 1 uppercase, 1 lowercase, 1 number
    if len(password) < 8:
        return False, "Password must be at least 8 characters long"
    if not any(c.isupper() for c in password):
        return False, "Password must include at least one uppercase letter"
    if not any(c.islower() for c in password):
        return False, "Password must include at least one lowercase letter"
    if not any(c.isdigit() for c in password):
        return False, "Password must include at least one number"
    return True, "Password is strong"

def explain_code_with_gemini(
    code: str, 
    is_error: bool = False,
    programming_language: str = None,
    detail_level: str = "beginner",
    highlight_important_parts: bool = True,
    include_examples: bool = True,
    include_diagrams: bool = False,
    model_name: str = 'gemini-2.0-flash'
) -> str:
    """
    Explains code or error messages in a beginner-friendly way using Google's Gemini model.
    
    Args:
        code (str): The code or error message to explain.
        is_error (bool, optional): Whether the input is an error message. Defaults to False.
        programming_language (str, optional): The programming language of the code. 
            This helps the model provide more accurate explanations. Defaults to None (auto-detect).
        detail_level (str, optional): Level of explanation detail - "beginner", "intermediate", or "advanced".
            Defaults to "beginner".
        highlight_important_parts (bool, optional): Whether to highlight important parts of the code.
            Defaults to True.
        include_examples (bool, optional): Whether to include simple examples. Defaults to True.
        include_diagrams (bool, optional): Whether to request ascii/markdown diagrams for visual learners.
            Defaults to False.
        model_name (str, optional): The Gemini model to use. Defaults to 'gemini-2.0-flash'.
    
    Returns:
        str: Beginner-friendly explanation or error message.
    """
    # Configure the model
    try:
        model = genai.GenerativeModel(model_name)
    except Exception as model_error:
        return f"Error initializing Gemini model: {model_error}. Please check your API key and model name."
    
    # Set language detection part
    language_part = ""
    if programming_language:
        language_part = f"This is {programming_language} code."
    else:
        language_part = "Please identify what programming language this is before explaining it."
    
    # Configure detail level
    detail_configs = {
        "beginner": {
            "style": "Use simple language as if explaining to someone with no programming experience. Define all technical terms.",
            "format": "Break down the explanation into small, easy-to-understand sections.",
            "depth": "Focus on the basic purpose of each line, avoiding complex concepts unless necessary."
        },
        "intermediate": {
            "style": "Use straightforward explanations assuming basic programming knowledge.",
            "format": "Organize the explanation by logical components or functions.",
            "depth": "Include explanations of common patterns and programming concepts."
        },
        "advanced": {
            "style": "Use technical language assuming substantial programming experience.",
            "format": "Focus on non-obvious aspects and design decisions.",
            "depth": "Include performance considerations and alternative approaches."
        }
    }
    
    detail_config = detail_configs.get(detail_level, detail_configs["beginner"])
    
    # Configure highlighting
    highlight_part = ""
    if highlight_important_parts:
        highlight_part = """
        Highlight important parts of the code by:
        1. **Bolding key variables, functions, and control structures**
        2. Explaining critical lines with 💡 emoji at the start
        3. Flagging potential issues with ⚠️ emoji
        4. Using bullet points for step-by-step explanations
        """
    
    # Configure examples
    examples_part = ""
    if include_examples:
        examples_part = """
        Include 1-2 simple, concrete examples showing how the code works with specific inputs and outputs.
        For errors, show a corrected version of the code.
        """
    
    # Configure diagrams
    diagram_part = ""
    if include_diagrams:
        diagram_part = """
        Include a simple ASCII or markdown diagram to visually explain the code flow or data structures
        when it would help understanding.
        """
    
    # Create prompt based on whether it's code or an error
    if is_error:
        prompt = f"""Explain the following error message in a very beginner-friendly way:
        
        ERROR:
        ```
        {code}
        ```
        
        {language_part}
        
        EXPLANATION GUIDELINES:
        - Start with a simple explanation of what went wrong in plain English
        - Explain exactly which part of the code caused the error
        - Suggest 2-3 specific ways to fix the error
        - {detail_config['style']}
        - {detail_config['format']}
        - {detail_config['depth']}
        {highlight_part}
        {examples_part}
        {diagram_part}
        
        Conclude with a one-sentence summary of what the programmer should remember to avoid this error in the future.
        """
    else:
        prompt = f"""Explain the following code in a very beginner-friendly way:
        
        CODE:
        ```
        {code}
        ```
        
        {language_part}
        
        EXPLANATION GUIDELINES:
        - Start with a simple overview of what this code does in 1-2 sentences
        - Then walk through the code step-by-step
        - Explain the purpose of each major section
        - {detail_config['style']}
        - {detail_config['format']}
        - {detail_config['depth']}
        {highlight_part}
        {examples_part}
        {diagram_part}
        
        Conclude with a bullet list summary of key concepts demonstrated in this code.
        """
    
    # Safety timeout and retry mechanism
    import time
    start_time = time.time()
    max_retries = 2
    retries = 0
    
    while retries <= max_retries:
        try:
            # Configure model parameters
            safety_settings = [
                {
                    "category": "HARM_CATEGORY_HARASSMENT",
                    "threshold": "BLOCK_MEDIUM_AND_ABOVE"
                },
                {
                    "category": "HARM_CATEGORY_HATE_SPEECH",
                    "threshold": "BLOCK_MEDIUM_AND_ABOVE"
                },
                {
                    "category": "HARM_CATEGORY_SEXUALLY_EXPLICIT",
                    "threshold": "BLOCK_MEDIUM_AND_ABOVE"
                },
                {
                    "category": "HARM_CATEGORY_DANGEROUS_CONTENT",
                    "threshold": "BLOCK_MEDIUM_AND_ABOVE"
                }
            ]
            
            generation_config = {
                "temperature": 0.2,  # Lower for more accurate explanations
                "top_p": 0.95,
                "top_k": 40,
                "max_output_tokens": 2048,
            }
            
            # Generate response with enhanced parameters
            response = model.generate_content(
                prompt,
                generation_config=generation_config,
                safety_settings=safety_settings
            )
            
            # Check if we have content
            if hasattr(response, 'text') and response.text:
                # Process the response to enhance formatting
                explanation = response.text
                
                # Add syntax highlighting markers if not present but requested
                if highlight_important_parts and "**" not in explanation:
                    import re
                    # Find code-like patterns and add bold formatting
                    code_pattern = r'\b([a-zA-Z_][a-zA-Z0-9_]*\(|\bif\b|\bfor\b|\bwhile\b|\bdef\b|\bclass\b|\breturn\b|\bimport\b)'
                    explanation = re.sub(code_pattern, r'**\1**', explanation)
                
                return explanation
            else:
                raise Exception("Empty response received")
                
        except Exception as retry_error:
            error_message = str(retry_error).lower()
            retries += 1
            
            # Handle specific error types
            if "rate" in error_message and retries <= max_retries:
                time.sleep(2)  # Wait before retry
            elif "timeout" in error_message and retries <= max_retries:
                time.sleep(1)  # Wait before retry
            else:
                # If we've exhausted retries or hit a different error
                if time.time() - start_time > 30:
                    return "The explanation is taking too long to generate. Your code might be very complex. Try sharing a smaller portion of the code."
                elif "token" in error_message:
                    return "The code is too large to explain in one go. Please share a smaller snippet or break it into logical parts."
                elif "model" in error_message:
                    return f"The Gemini model '{model_name}' is currently unavailable. Try again later or try using 'gemini-1.5-pro' instead."
                else:
                    return f"Could not generate an explanation: {str(retry_error)}. Please try again with a simpler code snippet."
    
    # Fallback for exhausted retries
    return "Unable to generate explanation after multiple attempts. Please try again later or with a different code sample."

# Set API keys from environment variable
GROQ_API_KEY = os.environ.get("GROQ_API_KEY")
GOOGLE_API_KEY = os.environ.get("GOOGLE_API_KEY")

if not GROQ_API_KEY or not GOOGLE_API_KEY:
    st.error("⚠️ API keys for Groq and Gemini are required. Please set them as Streamlit secrets.")
    st.stop()

# Initialize clients
try:
    groq_client = Groq(api_key=GROQ_API_KEY)
    genai.configure(api_key=GOOGLE_API_KEY)
except Exception as e:
    st.error(f"Error initializing API clients: {e}")
    st.stop()

# Initialize database
init_db()

st.markdown("""
<style>
/* Modern Navigation */
.nav-container {
    display: flex;
    justify-content: center;
    margin: 20px 0;
    background: rgba(255,255,255,0.1);
    border-radius: 50px;
    padding: 10px;
    backdrop-filter: blur(10px);
}

.nav-item {
    padding: 12px 25px;
    margin: 0 5px;
    border-radius: 30px;
    cursor: pointer;
    font-weight: 600;
    transition: all 0.3s ease;
    position: relative;
    overflow: hidden;
    color: rgba(255,255,255,0.7);
}

.nav-item.active {
    background: linear-gradient(90deg, #6c5ce7, #ff00cc);
    color: white;
    box-shadow: 0 5px 15px rgba(108, 92, 231, 0.4);
}

.nav-item:hover:not(.active) {
    background: rgba(255,255,255,0.1);
    color: white;
}

/* Interactive Cards */
.feature-card {
    background: rgba(255,255,255,0.08);
    border-radius: 20px;
    padding: 25px;
    margin: 15px 0;
    transition: all 0.3s ease;
    border: 1px solid rgba(255,255,255,0.1);
    cursor: pointer;
}

.feature-card:hover {
    transform: translateY(-5px);
    box-shadow: 0 15px 30px rgba(0,0,0,0.3);
    border-color: rgba(108, 92, 231, 0.5);
}

.feature-card h3 {
    margin-top: 0;
    color: #6c5ce7;
}

/* Ripple Buttons */
.ripple-button {
    position: relative;
    overflow: hidden;
    transform: translate3d(0, 0, 0);
}

.ripple-button:after {
    content: "";
    display: block;
    position: absolute;
    width: 100%;
    height: 100%;
    top: 0;
    left: 0;
    pointer-events: none;
    background-image: radial-gradient(circle, #fff 10%, transparent 10.01%);
    background-repeat: no-repeat;
    background-position: 50%;
    transform: scale(10, 10);
    opacity: 0;
    transition: transform .5s, opacity 1s;
}

.ripple-button:active:after {
    transform: scale(0, 0);
    opacity: .3;
    transition: 0s;
}

/* Tooltips */
.tooltip-box {
    position: relative;
    display: inline-block;
}

.tooltip-box .tooltip-text {
    visibility: hidden;
    width: 200px;
    background-color: #333;
    color: #fff;
    text-align: center;
    border-radius: 6px;
    padding: 10px;
    position: absolute;
    z-index: 1;
    bottom: 125%;
    left: 50%;
    transform: translateX(-50%);
    opacity: 0;
    transition: opacity 0.3s;
    font-size: 14px;
}

.tooltip-box:hover .tooltip-text {
    visibility: visible;
    opacity: 1;
}

/* Loading Spinner */
.spinner {
    width: 40px;
    height: 40px;
    margin: 20px auto;
    border: 4px solid rgba(108, 92, 231, 0.2);
    border-radius: 50%;
    border-top: 4px solid #6c5ce7;
    animation: spin 1s linear infinite;
}

@keyframes spin {
    0% { transform: rotate(0deg); }
    100% { transform: rotate(360deg); }
}

/* Notifications */
.notification {
    position: fixed;
    bottom: 20px;
    right: 20px;
    background: rgba(0,0,0,0.8);
    color: white;
    padding: 15px 25px;
    border-radius: 10px;
    box-shadow: 0 5px 15px rgba(0,0,0,0.3);
    transform: translateY(100px);
    opacity: 0;
    transition: all 0.3s ease;
    z-index: 1000;
}

.notification.show {
    transform: translateY(0);
    opacity: 1;
}
</style>
""", unsafe_allow_html=True)

st.markdown(
    """
    <style>
    /* Main theme with vibrant gradient background */
    body, .main {
        background: linear-gradient(-45deg, #0f0c29, #302b63, #24243e, #4b0082, #800080);
        background-size: 400% 400%;
        animation: gradient-shift 15s ease infinite;
        color: #fff;
        font-family: 'Inter', 'Poppins', sans-serif;
    }
    
    @keyframes gradient-shift {
        0% {background-position: 0% 50%}
        50% {background-position: 100% 50%}
        100% {background-position: 0% 50%}
    }
    
    /* Auth card styling */
    .auth-card {
        background: rgba(255, 255, 255, 0.1);
        backdrop-filter: blur(10px);
        border-radius: 20px;
        padding: 30px;
        border: 1px solid rgba(255, 255, 255, 0.2);
        box-shadow: 0 15px 35px rgba(0,0,0,0.3);
        margin: 50px auto;
        max-width: 450px;
        transition: all 0.3s ease;
    }
    
    .auth-card:hover {
        transform: translateY(-5px);
        box-shadow: 0 20px 40px rgba(0,0,0,0.4);
    }
    
    /* Auth form fields */
    .auth-input {
        background: rgba(0, 0, 0, 0.2) !important;
        border: 2px solid rgba(108, 92, 231, 0.3) !important;
        color: white !important;
        border-radius: 12px !important;
        padding: 12px 15px !important;
        margin-bottom: 15px !important;
        transition: all 0.3s ease !important;
    }
    
    .auth-input:focus {
        border-color: #6c5ce7 !important;
        box-shadow: 0 0 0 3px rgba(108, 92, 231, 0.25), 0 0 15px rgba(108, 92, 231, 0.3) !important;
    }
    
    /* Auth buttons */
    .auth-button {
        background: linear-gradient(90deg, #6c5ce7, #ff00cc) !important;
        color: white !important;
        border: none !important;
        border-radius: 12px !important;
        padding: 12px 25px !important;
        font-weight: 600 !important;
        margin-top: 10px !important;
        transition: all 0.3s ease !important;
        width: 100% !important;
    }
    
    .auth-button:hover {
        transform: translateY(-3px) !important;
        box-shadow: 0 10px 20px rgba(0,0,0,0.2) !important;
    }
    
    /* Tab styling */
    .auth-tabs .stTabs [data-baseweb="tab-list"] {
        gap: 10px;
        background-color: rgba(0,0,0,0.2);
        padding: 8px;
        border-radius: 16px;
    }
    
    .auth-tabs .stTabs [data-baseweb="tab"] {
        background-color: transparent;
        border-radius: 12px;
        padding: 12px 24px;
        border: none;
        color: rgba(255,255,255,0.7);
    }
    
    .auth-tabs .stTabs [aria-selected="true"] {
        color: white;
        font-weight: 600;
        background: linear-gradient(90deg, #6c5ce7, #ff00cc);
    }
    
    /* Logo and title styling */
    .auth-logo {
        text-align: center;
        margin-bottom: 25px;
    }
    
    .auth-title {
        font-family: 'Orbitron', sans-serif;
        color: white;
        text-align: center;
        font-size: 28px;
        margin-bottom: 20px;
        text-shadow: 0 0 10px rgba(108, 92, 231, 0.5);
    }
    
    .auth-subtitle {
        color: rgba(255, 255, 255, 0.7);
        text-align: center;
        margin-bottom: 30px;
    }
    
    /* Message styling */
    .success-message {
        background: rgba(46, 213, 115, 0.2);
        color: #2ed573;
        border: 1px solid #2ed573;
        border-radius: 8px;
        padding: 10px;
        margin: 15px 0;
        text-align: center;
    }
    
    .error-message {
        background: rgba(255, 71, 87, 0.2);
        color: #ff4757;
        border: 1px solid #ff4757;
        border-radius: 8px;
        padding: 10px;
        margin: 15px 0;
        text-align: center;
    }
    
    /* Form field labels */
    .auth-label {
        color: rgba(255, 255, 255, 0.9);
        font-size: 14px;
        font-weight: 500;
        margin-bottom: 5px;
    }
    
    /* Password strength indicator */
    .password-strength {
        height: 5px;
        border-radius: 5px;
        margin-top: 5px;
        margin-bottom: 15px;
        background: #333;
        overflow: hidden;
    }
    
    .password-strength-bar {
        height: 100%;
        transition: width 0.3s ease, background 0.3s ease;
    }
    
    .password-strength-text {
        font-size: 12px;
        margin-top: 5px;
    }
    
    /* Switch account link */
    .auth-switch {
        text-align: center;
        margin-top: 20px;
        color: rgba(255, 255, 255, 0.7);
    }
    
    .auth-switch a {
        color: #6c5ce7;
        text-decoration: none;
        font-weight: 600;
    }
    
    .auth-switch a:hover {
        text-decoration: underline;
    }
    </style>
    """,
    unsafe_allow_html=True
)
st.markdown(
    """
    <style>
    /* Main theme with vibrant gradient background */
    body, .main {
        background: linear-gradient(-45deg, #0f0c29, #302b63, #24243e, #4b0082, #800080);
        background-size: 400% 400%;
        animation: gradient-shift 15s ease infinite;
        color: #fff;
        font-family: 'Inter', 'Poppins', sans-serif;
    }
    
    @keyframes gradient-shift {
        0% {background-position: 0% 50%}
        50% {background-position: 100% 50%}
        100% {background-position: 0% 50%}
    }
    
    /* Vibrant title container with multi-layered gradients */
    .title-container {
        background: linear-gradient(90deg, #FF00CC, #3333ff, #FF00CC);
        background-size: 200% auto;
        padding: 30px;
        border-radius: 20px;
        margin-bottom: 30px;
        text-align: center;
        box-shadow: 0 15px 30px rgba(0,0,0,0.4), 0 0 30px rgba(102, 16, 242, 0.4);
        animation: shimmer 6s linear infinite;
        position: relative;
        overflow: hidden;
    }
    
    .title-container::before {
        content: "";
        position: absolute;
        top: -50%;
        left: -50%;
        width: 200%;
        height: 200%;
        background: linear-gradient(45deg, rgba(255,255,255,0) 0%, rgba(255,255,255,0.1) 50%, rgba(255,255,255,0) 100%);
        transform: rotate(30deg);
        animation: shine 6s linear infinite;
    }
    
    @keyframes shimmer {
        0% {background-position: 0% 50%}
        100% {background-position: 200% 50%}
    }
    
    @keyframes shine {
        0% {transform: translateX(-100%) rotate(30deg)}
        100% {transform: translateX(100%) rotate(30deg)}
    }
    
    /* Title text with glow effect */
    .title-container h1 {
        font-weight: 800;
        letter-spacing: 2px;
        text-shadow: 0 0 10px rgba(255,255,255,0.5), 0 0 20px rgba(102, 16, 242, 0.3);
        animation: pulse 2s infinite;
    }
    
    @keyframes pulse {
        0% {text-shadow: 0 0 10px rgba(255,255,255,0.5), 0 0 20px rgba(102, 16, 242,.3)}
        50% {text-shadow: 0 0 20px rgba(255,255,255,0.8), 0 0 30px rgba(102, 16, 242, 0.6)}
        100% {text-shadow: 0 0 10px rgba(255,255,255,0.5), 0 0 20px rgba(102, 16, 242, 0.3)}
    }
    
    /* Futuristic buttons with advanced hover effects */
    .button-container {
        display: flex;
        gap: 18px;
        flex-wrap: wrap;
        margin: 25px 0;
    }
    
    .custom-button {
        background: linear-gradient(90deg, #6c5ce7, #ff00cc);
        background-size: 200% auto;
        color: white;
        border: none;
        border-radius: 12px;
        padding: 16px 30px;
        font-weight: 600;
        cursor: pointer;
        transition: all 0.4s cubic-bezier(0.17, 0.67, 0.83, 0.67);
        width: 100%;
        margin: 5px 0;
        box-shadow: 0 8px 20px rgba(0,0,0,0.3), 0 0 15px rgba(108, 92, 231, 0.3);
        position: relative;
        overflow: hidden;
        z-index: 1;
        letter-spacing: 1px;
    }
    
    .custom-button::before {
        content: '';
        position: absolute;
        top: 0;
        left: 0;
        width: 100%;
        height: 100%;
        background: linear-gradient(90deg, #ff00cc, #3333ff);
        background-size: 200% auto;
        z-index: -1;
        transition: opacity 0.5s ease-out;
        opacity: 0;
    }
    
    .custom-button:hover {
        transform: translateY(-5px) scale(1.03);
        box-shadow: 0 15px 30px rgba(0,0,0,0.4), 0 0 30px rgba(108, 92, 231, 0.4);
        letter-spacing: 1.5px;
    }
    
    .custom-button:hover::before {
        opacity: 1;
        animation: slide-bg 1.5s linear infinite;
    }
    
    @keyframes slide-bg {
        0% {background-position: 0% 50%}
        100% {background-position: 200% 50%}
    }
    
    .custom-button::after {
        content: '';
        position: absolute;
        top: 50%;
        left: 50%;
        width: 10px;
        height: 10px;
        background: rgba(255, 255, 255, 0.8);
        border-radius: 50%;
        z-index: -1;
        opacity: 0;
        transform: translate(-50%, -50%);
        transition: all 0.6s cubic-bezier(0.17, 0.67, 0.83, 0.67);
    }
    
    .custom-button:active::after {
        width: 300px;
        height: 300px;
        opacity: 0;
        transition: 0s;
    }
    
    /* Neo-morphic code input area */
    .stTextArea textarea {
        background: linear-gradient(145deg, #1a1a2e, #2d2b42);
        color: #e0e0e0;
        border: 1px solid #6c5ce7;
        border-radius: 16px;
        font-family: 'JetBrains Mono', 'Fira Code', 'Courier New', monospace;
        padding: 20px;
        box-shadow: 20px 20px 60px rgba(0,0,0,0.5), 
                   -20px -20px 60px rgba(108, 92, 231, 0.1);
        transition: all 0.4s ease;
        line-height: 1.6;
    }
    
    .stTextArea textarea:focus {
        border: 1px solid #a29bfe;
        transform: translateY(-3px);
        box-shadow: 0 10px 25px rgba(108, 92, 231, 0.4), 
                    0 0 5px rgba(108, 92, 231, 0.4), 
                    inset 0 2px 10px rgba(0,0,0,0.3);
    }
    
    /* Advanced glassmorphism results container */
    .result-container {
        background: rgba(255, 255, 255, 0.08);
        backdrop-filter: blur(12px);
        -webkit-backdrop-filter: blur(12px);
        border-radius: 24px;
        padding: 30px;
        margin: 30px 0;
        border-left: 5px solid transparent;
        border-image: linear-gradient(to bottom, #6c5ce7, #ff00cc) 1;
        box-shadow: 0 8px 32px rgba(0,0,0,0.3);
        transition: all 0.5s cubic-bezier(0.17, 0.67, 0.83, 0.67);
        position: relative;
        overflow: hidden;
    }
    
    .result-container::before {
        content: '';
        position: absolute;
        top: 0;
        left: 0;
        right: 0;
        height: 3px;
        background: linear-gradient(90deg, #6c5ce7, #ff00cc, #6c5ce7);
        background-size: 200% auto;
        animation: shine-border 3s linear infinite;
    }
    
    @keyframes shine-border {
        0% {background-position: 0% 50%}
        100% {background-position: 200% 50%}
    }
    
    .result-container:hover {
        box-shadow: 0 15px 35px rgba(0,0,0,0.4), 0 0 15px rgba(108, 92, 231, 0.3);
        transform: translateY(-8px) scale(1.02);
    }
    
    /* 3D flip card effect */
    .card {
        perspective: 1000px;
        background: transparent;
        padding: 0;
        margin: 20px 0;
        height: 200px;
    }
    
    .card-inner {
        position: relative;
        width: 100%;
        height: 100%;
        text-align: center;
        transition: transform 0.8s;
        transform-style: preserve-3d;
    }
    
    .card:hover .card-inner {
        transform: rotateY(180deg);
    }
    
    .card-front, .card-back {
        position: absolute;
        width: 100%;
        height: 100%;
        -webkit-backface-visibility: hidden;
        backface-visibility: hidden;
        border-radius: 16px;
        padding: 20px;
        display: flex;
        flex-direction: column;
        justify-content: center;
        align-items: center;
    }
    
    .card-front {
        background: rgba(108, 92, 231, 0.2);
        backdrop-filter: blur(8px);
        border: 1px solid rgba(108, 92, 231, 0.3);
        box-shadow: 0 8px 20px rgba(0,0,0,0.2);
        color: white;
    }
    
    .card-back {
        background: rgba(255, 0, 204, 0.2);
        backdrop-filter: blur(8px);
        border: 1px solid rgba(255, 0, 204, 0.3);
        box-shadow: 0 8px 20px rgba(0,0,0,0.2);
        color: white;
        transform: rotateY(180deg);
    }
    
    /* Glowing 3D tooltips */
    .tooltip {
        position: relative;
        display: inline-block;
    }
    
    .tooltip .tooltiptext {
        visibility: hidden;
        width: 250px;
        background: rgba(0, 0, 0, 0.7);
        color: #fff;
        text-align: center;
        border-radius: 10px;
        padding: 15px;
        position: absolute;
        z-index: 100;
        bottom: 150%;
        left: 50%;
        margin-left: -125px;
        opacity: 0;
        transition: all 0.5s cubic-bezier(0.17, 0.67, 0.83, 0.67);
        box-shadow: 0 10px 25px rgba(0,0,0,0.3), 0 0 10px rgba(108, 92, 231, 0.4);
        border: 1px solid rgba(108, 92, 231, 0.3);
        transform: translateY(20px) scale(0.9);
    }
    
    .tooltip .tooltiptext::after {
        content: "";
        position: absolute;
        top: 100%;
        left: 50%;
        margin-left: -10px;
        border-width: 10px;
        border-style: solid;
        border-color: rgba(0, 0, 0, 0.7) transparent transparent transparent;
    }
    
    .tooltip:hover .tooltiptext {
        visibility: visible;
        opacity: 1;
        transform: translateY(0) scale(1);
        animation: glow 2s infinite;
    }
    
    @keyframes glow {
        0% {box-shadow: 0 10px 25px rgba(0,0,0,0.3), 0 0 10px rgba(108, 92, 231, 0.4)}
        50% {box-shadow: 0 10px 25px rgba(0,0,0,0.3), 0 0 20px rgba(108, 92, 231, 0.6)}
        100% {box-shadow: 0 10px 25px rgba(0,0,0,0.3), 0 0 10px rgba(108, 92, 231, 0.4)}
    }
    
    /* Animated tab indicators with sliding effect */
    .stTabs [data-baseweb="tab-list"] {
        gap: 10px;
        background-color: rgba(0,0,0,0.2);
        padding: 8px;
        border-radius: 16px;
        position: relative;
    }
    
    .stTabs [data-baseweb="tab"] {
        background-color: transparent;
        border-radius: 12px;
        padding: 12px 24px;
        border: none;
        transition: all 0.3s ease;
        color: rgba(255,255,255,0.7);
        z-index: 1;
    }
    
    .stTabs [aria-selected="true"] {
        color: white;
        font-weight: 600;
        position: relative;
    }
    
    .stTabs [aria-selected="true"]::before {
        content: "";
        position: absolute;
        top: 0;
        left: 0;
        width: 100%;
        height: 100%;
        background: linear-gradient(90deg, #6c5ce7, #ff00cc);
        border-radius: 12px;
        z-index: -1;
        animation: pulse-tab 2s infinite;
    }
    
    @keyframes pulse-tab {
        0% {box-shadow: 0 0 0 0 rgba(108, 92, 231, 0.4)}
        70% {box-shadow: 0 0 0 10px rgba(108, 92, 231, 0)}
        100% {box-shadow: 0 0 0 0 rgba(108, 92, 231, 0)}
    }
    
    /* Futuristic code block with line numbers and syntax highlighting */
    .syntax-highlight {
        background-color: #1e1e2e;
        background-image: linear-gradient(135deg, rgba(108, 92, 231, 0.1), rgba(0, 0, 0, 0));
        border-radius: 16px;
        padding: 25px;
        font-family: 'JetBrains Mono', 'Fira Code', 'Courier New', monospace;
        overflow-x: auto;
        position: relative;
        color: #f8f8f2;
        counter-reset: line;
        box-shadow: 0 15px 35px rgba(0,0,0,0.3);
        line-height: 1.6;
        border: 1px solid rgba(108, 92, 231, 0.3);
    }
    
    .syntax-highlight::before {
        content: attr(data-language);
        position: absolute;
        top: -12px;
        right: 20px;
        background: linear-gradient(90deg, #6c5ce7, #ff00cc);
        color: white;
        padding: 5px 15px;
        font-size: 12px;
        border-radius: 20px;
        font-weight: bold;
        box-shadow: 0 5px 15px rgba(0,0,0,0.2);
    }
    
    .syntax-highlight code {
        display: block;
        position: relative;
        padding-left: 40px;
    }
    
    .syntax-highlight code::before {
        content: counter(line);
        counter-increment: line;
        position: absolute;
        left: 0;
        color: #6272a4;
        text-align: right;
        width: 30px;
    }
    
    /* Animated customized scrollbar */
    ::-webkit-scrollbar {
        width: 12px;
        height: 12px;
    }
    
    ::-webkit-scrollbar-track {
        background: rgba(0,0,0,0.2);
        border-radius: 10px;
    }
    
    ::-webkit-scrollbar-thumb {
        background: linear-gradient(180deg, #6c5ce7, #ff00cc);
        border-radius: 10px;
        border: 3px solid rgba(0,0,0,0.2);
    }
    
    ::-webkit-scrollbar-thumb:hover {
        background: linear-gradient(180deg, #ff00cc, #6c5ce7);
    }
    
    /* Neon glowing input fields */
    .stTextInput input, .stNumberInput input, .stSelectbox select {
        border-radius: 12px;
        border: 2px solid rgba(108, 92, 231, 0.3);
        padding: 14px 18px;
        background: rgba(0,0,0,0.2);
        color: white;
        transition: all 0.3s ease;
        box-shadow: 0 5px 15px rgba(0,0,0,0.2);
    }
    
    .stTextInput input:focus, .stNumberInput input:focus {
        border-color: #6c5ce7;
        box-shadow: 0 0 0 3px rgba(108, 92, 231, 0.25), 0 0 15px rgba(108, 92, 231, 0.3);
        transform: translateY(-2px);
    }
    
    /* Animated progress bars */
    .stProgress > div > div > div {
        background-image: linear-gradient(90deg, #6c5ce7, #ff00cc, #6c5ce7);
        background-size: 200% 100%;
        animation: gradient-move 3s linear infinite;
    }
    
    @keyframes gradient-move {
        0% {background-position: 0% 0%}
        100% {background-position: 200% 0%}
    }
    
    /* Widget labels with subtle animations */
    .stWidgetLabel {
        color: rgba(255,255,255,0.9);
        font-weight: 500;
        margin-bottom: 8px;
        position: relative;
        display: inline-block;
        transition: all 0.3s ease;
    }
    
    .stWidgetLabel:hover {
        color: white;
        text-shadow: 0 0 5px rgba(108, 92, 231, 0.5);
    }
    
    .stWidgetLabel::after {
        content: '';
        position: absolute;
        width: 0;
        height: 2px;
        bottom: -2px;
        left: 0;
        background: linear-gradient(90deg, #6c5ce7, #ff00cc);
        transition: width 0.3s ease;
    }
    
    .stWidgetLabel:hover::after {
        width: 100%;
    }
    
    /* Gradient dividers with shine effect */
    hr {
        border: 0;
        height: 2px;
        background-image: linear-gradient(90deg, transparent, #6c5ce7, #ff00cc, #6c5ce7, transparent);
        margin: 30px 0;
        position: relative;
        overflow: hidden;
    }
    
    hr::after {
        content: "";
        position: absolute;
        top: 0;
        left: -100%;
        width: 100%;
        height: 100%;
        background: linear-gradient(90deg, transparent, rgba(255,255,255,0.4), transparent);
        animation: shine-hr 3s infinite;
    }
    
    @keyframes shine-hr {
        0% {left: -100%}
        100% {left: 100%}
    }
    
    /* Floating elements animation */
    .floating {
        animation: floating 3s ease-in-out infinite;
    }
    
    @keyframes floating {
        0% {transform: translateY(0px)}
        50% {transform: translateY(-15px)}
        100% {transform: translateY(0px)}
    }
    
    /* Interactive chart hover effects */
    .stPlotlyChart {
        transition: all 0.3s ease;
    }
    
    .stPlotlyChart:hover {
        transform: scale(1.02);
        box-shadow: 0 15px 30px rgba(0,0,0,0.3);
    }
    </style>
    """,
    unsafe_allow_html=True
)

st.markdown("""
<style>
@media screen and (max-width: 768px) {
    .title-container h1 {
        font-size: 24px !important;
    }
    
    .nav-container {
        flex-wrap: wrap;
    }
    
    .nav-item {
        padding: 8px 12px;
        margin: 3px;
        font-size: 14px;
    }
    
    .stTextArea textarea {
        padding: 10px !important;
    }
}
</style>
""", unsafe_allow_html=True)


def generate_code_from_text(
    text: str,
    language: str = None,
    model: str = "llama-3.3-70b-versatile",
    temperature: float = 0.1,
    max_tokens: int = 1024,
    include_comments: bool = False,
    optimize_for: str = "readability",
    context_aware: bool = True,
    fallback_models: list = None,
    stream: bool = False
) -> str:
    """
    Generates production-ready code from natural language descriptions using Groq's AI models.
    Returns only the generated code as a string, or an error message.
    """
    from groq import Groq
    import re

    if not text or not isinstance(text, str):
        return "❌ Invalid input: Text description must be a non-empty string."

    temperature = max(0.0, min(1.0, temperature))
    max_tokens = max(100, min(max_tokens, 8192))

    fallback_models = fallback_models or [
        "gemma2-9b-it",
        "llama-3.1-8b-instant",
    ]
    if model not in fallback_models:
        fallback_models.insert(0, model)

    optimization_presets = {
        "readability": (
            "Prioritize clean, well-documented code with:\n"
            "- Meaningful variable names\n"
            "- Proper indentation\n"
            "- Section comments\n"
            "- Clear structure"
        ),
        "efficiency": (
            "Optimize for performance with:\n"
            "- Efficient algorithms\n"
            "- Minimal computational complexity\n"
            "- Memory optimization\n"
            "- Parallelization where possible"
        ),
        "brevity": (
            "Create concise code with:\n"
            "- Minimal boilerplate\n"
            "- Language idioms\n"
            "- Compact syntax\n"
            "- Removed redundancy"
        )
    }
    optimize_for = optimize_for if optimize_for in optimization_presets else "readability"

    prompt_sections = [
        f"CODE GENERATION TASK: {text}",
        f"TARGET LANGUAGE: {language or 'Auto-select'}",
        f"OPTIMIZATION GOAL: {optimization_presets[optimize_for]}",
        "ADDITIONAL REQUIREMENTS:",
        f"- {'Include' if include_comments else 'Exclude'} detailed comments",
        "- Generate production-ready code",
        "- Use modern best practices",
        "- Include error handling",
        "- Output in markdown code blocks"
    ]
    if context_aware:
        prompt_sections.insert(1, "CONTEXT: Generate robust code that handles edge cases and validates inputs")
    prompt = "\n".join(prompt_sections)

    client = Groq()
    models_tried = []

    for current_model in fallback_models:
        models_tried.append(current_model)
        try:
            completion = client.chat.completions.create(
                model=current_model,
                messages=[{"role": "user", "content": prompt}],
                temperature=temperature,
                max_tokens=max_tokens
            )
            content = completion.choices[0].message.content
            # Extract code block
            code_blocks = re.findall(r"```(?:[a-zA-Z]+)?\n([\s\S]+?)\n```", content, re.MULTILINE)
            if code_blocks:
                return code_blocks[0].strip()
            return content.strip()
        except Exception as e:
            continue

    return f"❌ All model attempts failed. Tried: {models_tried}"

def generate_code_flow(code: str) -> str:
    """
    Generate a beginner-friendly Mermaid flow diagram from code.

    Args:
        code (str): Source code as input

    Returns:
        str: Mermaid flow diagram (no extra text)
    """
    # Initialize the Groq client
    groq_client = Groq()

    # Craft the prompt
    prompt = f"""
    You are an expert programmer who specializes in creating BEGINNER-FRIENDLY explanations.

    Please generate a simple, easy-to-understand flow diagram for this Python code:

    ```python
    {code}
    ```

    Important requirements:
    1. Make the diagram EXTREMELY beginner-friendly with clear labels
    2. Include comments explaining what each step does
    3. Use simple language - avoid technical jargon
    4. Break complex operations into smaller steps
    5. Provide the diagram ONLY in Mermaid syntax
    6. Do not include any explanatory text outside the Mermaid code

    Return ONLY the Mermaid diagram code.
    """

    try:
        # Call Groq model
        response = groq_client.chat.completions.create(
            model="deepseek-r1-distill-llama-70b",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.4,
            max_completion_tokens=4096,
            top_p=0.95,
            stream=False
        )

        # Extract and clean Mermaid diagram
        content = response.choices[0].message.content.strip()
        mermaid_code = re.findall(r'```(?:mermaid)?\s*(.*?)```', content, re.DOTALL)

        return mermaid_code[0].strip() if mermaid_code else content

    except Exception as e:
        return f"Error generating flow diagram: {str(e)}"


def run_security_scan(code):
    """
    Run a comprehensive security scan on the provided code using AI.
    
    Args:
        code (str): The source code to scan
        
    Returns:
        dict: A structured security scan report containing:
            - status: "secure" or "vulnerable"
            - issues: List of identified vulnerabilities (empty if none found)
            - fixes: Suggested code fixes for each vulnerability
            - explanation: Detailed explanation of each issue
    """
    from groq import Groq
    client = Groq()
    
    model = "qwen-qwq-32b"  # Using Alibaba's QwQ 32B model
    
    prompt = f"""
    You are an expert in code security and vulnerability analysis specializing in Python.
    
    Analyze the following code for security vulnerabilities, including but not limited to:
    - Injection vulnerabilities (SQL, command, etc.)
    - Insecure cryptography
    - Authentication issues
    - Authorization flaws
    - Data validation problems
    - Hardcoded credentials
    - Insecure file operations
    - Race conditions
    - Memory management issues
    - Input validation
    
    ```python
    {code}
    ```
    
    For each vulnerability found:
    1. Provide a clear description of the vulnerability
    2. Explain why it's a security concern
    3. Rate its severity (Critical, High, Medium, Low)
    4. Provide a complete code example that fixes the issue
    
    If no security issues are found, explicitly state "NO SECURITY ISSUES DETECTED" and explain why the code appears secure.
    
    Format your response as JSON with the following structure:
    {{
        "status": "secure" or "vulnerable",
        "issues": [
            {{
                "type": "vulnerability type",
                "severity": "Critical/High/Medium/Low",
                "description": "detailed description",
                "explanation": "why this is a security concern",
                "fix": "complete code fix"
            }}
        ]
    }}
    
    If the code is secure, return an empty issues array.
    """
    
    try:
        # Make API call to the model using the setup provided
        response = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.2,
            max_tokens=4000,
            response_format={"type": "json_object"}  # Request JSON response
        )
        
        # Extract and parse the security report
        security_report = response.choices[0].message.content.strip()
        
        # Process the report
        try:
            import json
            report_data = json.loads(security_report)
            
            # Format the report for human readability
            if report_data.get("status") == "secure":
                return "✅ NO SECURITY ISSUES DETECTED\n\nThe code appears to be secure. No vulnerabilities were identified in the analysis."
            else:
                issues = report_data.get("issues", [])
                if not issues:
                    return "✅ NO SECURITY ISSUES DETECTED\n\nThe code appears to be secure. No vulnerabilities were identified in the analysis."
                
                # Format the issues into a readable report
                formatted_report = "🔴 SECURITY VULNERABILITIES DETECTED\n\n"
                for i, issue in enumerate(issues, 1):
                    formatted_report += f"ISSUE #{i}: {issue.get('type')} (Severity: {issue.get('severity')})\n"
                    formatted_report += f"Description: {issue.get('description')}\n"
                    formatted_report += f"Explanation: {issue.get('explanation')}\n\n"
                    formatted_report += "Recommended Fix:\n```python\n{}\n```\n\n".format(issue.get('fix'))
                
                return formatted_report
                
        except json.JSONDecodeError:
            # Fallback for non-JSON responses
            if "NO SECURITY ISSUES DETECTED" in security_report:
                return "✅ NO SECURITY ISSUES DETECTED\n\nThe code appears to be secure. No vulnerabilities were identified in the analysis."
            else:
                return security_report
        
    except Exception as e:
        return f"❌ ERROR DURING SECURITY SCAN: {str(e)}\n\nPlease check your code format and try again."
    
    
def get_fixed_code_with_groq(code):
    """
    Get fixed and secure code using Groq API.
    
    Args:
        code (str): The source code to fix
        
    Returns:
        str: The fixed and secure code or error message
    """
    model = "meta-llama/llama-4-scout-17b-16e-instruct"  # Changed from qwen-2.5-coder-32b
    
    prompt = f"""
    You are an expert programmer proficient in multiple programming languages.
    
    I need you to fix and secure the following code:
    
    ```python
    {code}
    ```
    
    Please provide only the fixed and secure code without any explanations or comments.
    Make sure to preserve the functionality and logic of the original code.
    Use idiomatic Python patterns and best practices.
    """
    
    try:
        response = groq_client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.2,
            max_tokens=4000
        )
        
        fixed_code = response.choices[0].message.content.strip()
        
        # Clean up the response to extract just the code if it contains markdown
        if "```" in fixed_code:
            # Extract code between markdown code blocks
            import re
            code_blocks = re.findall(r'```(?:\w+)?\n(.*?)```', fixed_code, re.DOTALL)
            if code_blocks:
                fixed_code = code_blocks[0].strip()
        
        return fixed_code
    
    except Exception as e:
        return f"Error during code fixing: {e}"

def convert_code_language(code, source_language, target_language):
    """
    Convert code from one programming language to another using Groq API.
    
    Args:
        code (str): The source code to convert
        source_language (str): The language of the source code
        target_language (str): The target language to convert to
        
    Returns:
        str: The converted code or error message
    """
    # Import the Groq client
    try:
        from groq import Groq
    except ImportError:
        return "Error: Groq package not installed. Install with 'pip install groq'"
    
    # Use the specifically requested models
    models = [
        "qwen-qwq-32b",  # Primary model as requested
        "gemma2-9b-it"   # Secondary model as requested
    ]
    
    prompt = f"""
    You are an expert programmer proficient in multiple programming languages.
    
    I need you to convert the following {source_language} code to {target_language}.
    
    ```{source_language.lower()}
    {code}
    ```
    
    Please provide only the converted {target_language} code without any explanations or comments.
    Make sure to preserve the functionality and logic of the original code.
    Use idiomatic {target_language} patterns and best practices.
    
    IMPORTANT: Return ONLY the code, no markdown code blocks, no explanations.
    """
    
    # Try each model in sequence until one works
    for model in models:
        try:
            # Initialize the Groq client
            groq_client = Groq()
            
            # Attempt to use the current model
            response = groq_client.chat.completions.create(
                model=model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.2,
                max_tokens=4000,
                stream=False  # Using non-streaming for simplicity
            )
            
            converted_code = response.choices[0].message.content.strip()
            
            # Clean up the response to extract just the code if it contains markdown
            if "```" in converted_code:
                # Extract code between markdown code blocks
                import re
                code_blocks = re.findall(r'```(?:\w+)?\n(.*?)```', converted_code, re.DOTALL)
                if code_blocks:
                    converted_code = code_blocks[0].strip()
                else:
                    # If we can't find code blocks with language specification, try without it
                    code_blocks = re.findall(r'```\n?(.*?)```', converted_code, re.DOTALL)
                    if code_blocks:
                        converted_code = code_blocks[0].strip()
            
            # Further cleanup: remove any remaining tags or headers
            converted_code = re.sub(r'^#.*\n?', '', converted_code, flags=re.MULTILINE)
            
            # If the code still starts with language name or comments about the language, remove them
            if converted_code.lower().startswith(target_language.lower()):
                converted_code = re.sub(f'^{target_language.lower()}.*\n', '', converted_code, flags=re.IGNORECASE)
            
            # Log which model was successfully used
            print(f"Code conversion successful using model: {model}")
            
            return converted_code
            
        except Exception as e:
            print(f"Model {model} failed with error: {e}")
            # If we're on the last model, return the error
            if model == models[-1]:
                return f"Error during code conversion: {e}"
            # Otherwise continue to the next model
            continue
    
    return "Error: All conversion attempts failed."

# Main app function 
def main():
    # Check if user is logged in
    if 'logged_in' not in st.session_state:
        st.session_state.logged_in = False
        st.session_state.username = None
    
    # Display login/register page if not logged in
    if not st.session_state.logged_in:
        render_auth_page()
    else:
        # If logged in, show the main app
        render_main_app()

def render_auth_page():
    # Title and logo
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        # Add logo without name
        st.image("logo.png", width=1500, caption="")

    # Auth tabs
    st.markdown('<div class="auth-tabs">', unsafe_allow_html=True)
    auth_tab1, auth_tab2 = st.tabs(["Login", "Register"])
    
    with auth_tab1:
        st.markdown('<div class="auth-title">Welcome Back</div>', unsafe_allow_html=True)
    
        login_username = st.text_input("Username", key="login_username", 
                                       help="Enter your username")
        login_password = st.text_input("Password", type="password", key="login_password",
                                      help="Enter your password")
        
        login_button = st.button("Sign In", key="login_button", 
                                 help="Click to sign in", use_container_width=True)
        
        if login_button:
            if not login_username or not login_password:
                st.markdown('<div class="error-message">Please fill in all fields!</div>', unsafe_allow_html=True)
            else:
                success, message = login_user(login_username, login_password)
                if success:
                    st.session_state.logged_in = True
                    st.session_state.username = login_username
                    st.markdown(f'<div class="success-message">{message}</div>', unsafe_allow_html=True)
                    # Force a rerun to show the main app
                    st.rerun()

                else:
                    st.markdown(f'<div class="error-message">{message}</div>', unsafe_allow_html=True)
    
    with auth_tab2:
        st.markdown('<div class="auth-title">Create Account</div>', unsafe_allow_html=True)
        st.markdown('<div class="auth-subtitle">Sign up to join FixiFox</div>', unsafe_allow_html=True)
        
        reg_username = st.text_input("Username", key="reg_username",
                                    help="Choose a unique username (at least 4 characters)")
        reg_email = st.text_input("Email", key="reg_email",
                                 help="Enter a valid email address")
        reg_password = st.text_input("Password", type="password", key="reg_password",
                                    help="Create a strong password (min 8 chars, include uppercase, lowercase & numbers)")
        reg_confirm_password = st.text_input("Confirm Password", type="password", key="reg_confirm_password",
                                           help="Re-enter your password")
        
        # Password strength indicator
        if reg_password:
            is_strong, strength_message = is_strong_password(reg_password)
            strength_percentage = 0
            
            if len(reg_password) >= 8:
                strength_percentage += 25
            if any(c.isupper() for c in reg_password):
                strength_percentage += 25
            if any(c.islower() for c in reg_password):
                strength_percentage += 25
            if any(c.isdigit() for c in reg_password):
                strength_percentage += 25
                
            color = "#ff4757"  # Red
            if strength_percentage > 75:
                color = "#2ed573"  # Green
            elif strength_percentage > 50:
                color = "#ffa502"  # Orange
            elif strength_percentage > 25:
                color = "#ff6348"  # Light Red
            
            st.markdown(f"""
            <div class="password-strength">
                <div class="password-strength-bar" style="width: {strength_percentage}%; background: {color};"></div>
            </div>
            <div class="password-strength-text" style="color: {color};">{strength_message}</div>
            """, unsafe_allow_html=True)
        
        register_button = st.button("Create Account", key="register_button", 
                                   help="Click to create your account", use_container_width=True)
        
        if register_button:
            # Validate inputs
            if not reg_username or not reg_email or not reg_password or not reg_confirm_password:
                st.markdown('<div class="error-message">Please fill in all fields!</div>', unsafe_allow_html=True)
            elif len(reg_username) < 4:
                st.markdown('<div class="error-message">Username must be at least 4 characters long!</div>', unsafe_allow_html=True)
            elif not is_valid_email(reg_email):
                st.markdown('<div class="error-message">Please enter a valid email address!</div>', unsafe_allow_html=True)
            elif reg_password != reg_confirm_password:
                st.markdown('<div class="error-message">Passwords do not match!</div>', unsafe_allow_html=True)
            else:
                is_strong, msg = is_strong_password(reg_password)
                if not is_strong:
                    st.markdown(f'<div class="error-message">{msg}</div>', unsafe_allow_html=True)
                else:
                    success, message = register_user(reg_username, reg_email, reg_password)
                    if success:
                        st.markdown(f'<div class="success-message">{message}</div>', unsafe_allow_html=True)
                        # Auto-switch to login tab
                        auth_tab1.selectbox = True
                    else:
                        st.markdown(f'<div class="error-message">{message}</div>', unsafe_allow_html=True)
    
    st.markdown('</div>', unsafe_allow_html=True)  # Close auth-tabs
    st.markdown('</div>', unsafe_allow_html=True)  # Close auth-card

def render_main_app():
    # Set API keys from environment variable
    if not GROQ_API_KEY or not GOOGLE_API_KEY:
        st.error("⚠️ API keys for Groq and Gemini are required. Please set them as Streamlit secrets.")
        st.stop()

    # Initialize clients
    try:
        groq_client = Groq(api_key=GROQ_API_KEY)
        genai.configure(api_key=GOOGLE_API_KEY)
    except Exception as e:
        st.error(f"Error initializing API clients: {e}")
        st.stop()
        
        # Custom title with HTML
        
    st.markdown(
        """
        <div class="title-container">
            <h1 style="font-family: 'Arial Black', sans-serif; font-size: 48px; color: #FFD700; text-shadow: 3px 3px 6px rgba(0, 0, 0, 0.3); letter-spacing: 2px;">
                🦊 FIXIFOX 🦊
            </h1>
            <p style="color: #ffff; font-size: 22px; font-weight: bold;">FROM THE LAST ROW, FIXING THE FIRST ERRORS !!!</p>
        </div>
        """,
        unsafe_allow_html=True
    )

    # Sidebar without animations
    with st.sidebar:
        st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Orbitron:wght@700&display=swap');

h1 {
    font-family: 'Orbitron', sans-serif;
    text-align: center;
    font-size: 3em;
    background: linear-gradient(45deg, #FF5733, #FFBD33, #FF5733);
    -webkit-background-clip: text;
    color: transparent;
    text-shadow: 0 0 20px rgba(255, 87, 51, 0.8), 0 0 30px rgba(255, 189, 51, 0.6);
}
</style>
""", unsafe_allow_html=True)

        # About FixiFox section
        # About FixiFox section with logo
        st.image("logo2.png", width=300)  # Adjust width as needed 
        st.markdown("""
## 🦊 About FixiFox

FixiFox is a premium AI-powered code assistant designed to revolutionize how developers write, debug, and understand code. Built with cutting-edge AI models (Gemini, Groq, and more), FixiFox offers an all-in-one toolkit for programmers of all skill levels—from beginners to experts.

### Why FixiFox?
- 🚀 **AI-Powered Efficiency**: Automate debugging, code generation, and optimization with AI
- 🔍 **Deep Code Understanding**: Get beginner-friendly explanations, flow diagrams, and security scans
- 🛠️ **Multi-Language Support**: Works with Python, JavaScript, Java, C++, and more
- 🔒 **Secure Coding**: Detect vulnerabilities and get fixes in real time
- 🎯 **Learning Focused**: Designed to help you learn while you code, not just fix errors

### Key Features
✅ **AI Code Explanation** – Understand complex code in simple terms  
✅ **Auto-Fix & Secure Code** – Get optimized, production-ready fixes  
✅ **Visual Flow Diagrams** – See your code's logic with Mermaid.js diagrams  
✅ **Security Vulnerability Scans** – Catch risks before they become bugs  
✅ **Interactive Debugging** – Step-by-step debugging with AI guidance  
✅ **Code Conversion** – Translate code between languages effortlessly  
✅ **Online Compiler** – Test and run code without leaving the app  

### Who Is It For?
- 👩‍💻 **Developers** – Debug faster and write cleaner code
- 🎓 **Students** – Learn programming concepts with AI explanations
- 🧑‍🏫 **Educators** – Simplify code demonstrations for students
- 🔧 **Open-Source Contributors** – Quickly understand and contribute to projects

Built with **Python, Streamlit, and Groq/Gemini APIs**, FixiFox combines power with simplicity. Whether you're fixing a syntax error or designing a new feature, FixiFox is your AI co-pilot.

### 🔗 Connect & Contribute
[GitHub](https://github.com/RAGAV132/AI-CODE-DEBUGER) | 
[LinkedIn](https://www.linkedin.com/in/ragavan-r-aa8a032b3/)

*From the last row, fixing the first errors!*
""")

    # Navigation bar
    page = st.selectbox("Select a feature:", ["Code Debugger", "Interactive Debugging Tool", "Code Generation", "Code Conversion", "Code Compiler"])
    
    if page == "Interactive Debugging Tool":
        st.markdown("### 🛠️ Code Analysis & Debugging Studio")
        st.markdown("Analyze, debug, and optimize your code with AI-powered assistance")
        
        # Import the Monaco editor package
        from streamlit_monaco import st_monaco
        
        # Create two columns for better layout
        col1, col2 = st.columns([2, 1])
        
        with col1:
            # Code editor with language selection
            language = st.selectbox(
                "Select language:", 
                ["Python", "JavaScript", "Java", "C++", "C", "Ruby", "PHP", "Go"]
            )
            
            # Map language selection to Monaco editor language options
            language_map = {
                "Python": "python",
                "JavaScript": "javascript",
                "Java": "java",
                "C++": "cpp",
                "C": "c",
                "Ruby": "ruby",
                "PHP": "php",
                "Go": "go"
            }
            
            # Use Monaco editor instead of text area
            debug_code = st_monaco(
                language=language_map.get(language, "python"),
                height=500,
                theme="vs-dark"  # Optional: use dark theme
            )
            
            # Input for the program (stdin)
            program_input = st.text_area(
                "Program Input (stdin):", 
                height=160, 
                placeholder="Enter any input your program needs...",
                key="program_input"
            )
        
        with col2:
            # Mode selection
            mode = st.radio(
                "Mode:", 
                ["Run", "Debug", "Analyze", "Optimize", "Explain"]
            )
            
            # Difficulty level
            difficulty = st.select_slider(
                "Explanation Level:",
                options=["Beginner", "Intermediate", "Advanced"],
                value="Beginner"
            )
            
            # Issue description (optional)
            issue_description = st.text_area(
                "Issue Description (optional):", 
                height=160,
                placeholder="Describe any issues you're facing with your code...",
                key="issue_description"
            )
            
            # Debugging configuration (shown only when Debug mode is selected)
            if mode == "Debug":
                st.markdown("##### Debugging Configuration")
                debug_options = {
                    "step_by_step": "Step-by-Step Execution",
                    "breakpoints": "Set Breakpoints",
                    "watch_variables": "Watch Variables",
                    "memory_view": "Memory View",
                    "call_stack": "Call Stack Visualization"
                }
                
                selected_debug_options = []
                for key, label in debug_options.items():
                    if st.checkbox(label, True):
                        selected_debug_options.append(key)
                        
                # Breakpoints setup (only if breakpoints are enabled)
                if "breakpoints" in selected_debug_options and debug_code.strip():
                    st.markdown("##### Set Breakpoints")
                    code_lines = debug_code.strip().split("\n")
                    if len(code_lines) > 0:
                        breakpoint_lines = st.multiselect(
                            "Select line numbers:",
                            options=list(range(1, len(code_lines) + 1)),
                            format_func=lambda x: f"Line {x}: {code_lines[x-1][:30]}{'...' if len(code_lines[x-1]) > 30 else ''}"
                        )
        
        # Action buttons based on mode
        action_label = f"{mode} Code"
        if st.button(action_label, type="primary"):
            if debug_code.strip():
                st.markdown('<div class="result-container">', unsafe_allow_html=True)
                st.markdown(f"### Results ({mode} Mode)")
                
                with st.spinner(f"Processing your code ({mode} mode)..."):
                    try:
                        client = Groq()
                        models = ["llama-3.1-8b-instant", "meta-llama/llama-4-scout-17b-16e-instruct"]
                        response = None
                        
                        # Prepare prompt based on mode
                        if mode == "Run":
                            prompt = f"Language: {language}\nCode:\n{debug_code}\n\nInput:\n{program_input}\n\nPlease execute this code and show the output."
                        elif mode == "Debug":
                            debug_features = ", ".join(selected_debug_options)
                            prompt = f"Language: {language}\nCode:\n{debug_code}\n\nInput:\n{program_input}\nIssue:\n{issue_description}\n\nPerform detailed debugging with: {debug_features}. Explanation level: {difficulty}."
                        elif mode == "Analyze":
                            prompt = f"Language: {language}\nCode:\n{debug_code}\n\nPerform code analysis focusing on correctness, potential bugs, edge cases, and efficiency. Provide feedback at {difficulty} level."
                        elif mode == "Optimize":
                            prompt = f"Language: {language}\nCode:\n{debug_code}\n\nOptimize this code for better performance and readability. Explain optimizations at {difficulty} level."
                        elif mode == "Explain":
                            prompt = f"Language: {language}\nCode:\n{debug_code}\n\nExplain this code line-by-line in detail. Break down core concepts and logic at {difficulty} level."
                        
                        # Try models in sequence
                        for model in models:
                            try:
                                completion = client.chat.completions.create(
                                    model=model,
                                    messages=[{"role": "user", "content": prompt}],
                                    temperature=0.6,
                                    max_completion_tokens=4096,
                                    top_p=0.95,
                                    stream=True,
                                    stop=None,
                                )
                                
                                response = ""
                                response_placeholder = st.empty()
                                for chunk in completion:
                                    chunk_content = chunk.choices[0].delta.content or ""
                                    response += chunk_content
                                    response_placeholder.markdown(response)
                                break  # Exit loop if successful
                            except Exception as e:
                                st.warning(f"⚠️ Model {model} failed: {e}")
                        
                        if not response:
                            st.error("⚠️ All models failed. Please try again later.")
                    except Exception as e:
                        st.error(f"⚠️ An error occurred: {e}")
                
               
        # Educational resources section
        with st.expander("📚 Learning Resources"):
            st.markdown("""
            ### Learning Resources
            
            #### Debugging Tips
            - **Print Debugging**: Insert print statements to track variable values
            - **Rubber Duck Debugging**: Explain your code line by line to identify issues
            - **Divide & Conquer**: Comment out sections of code to isolate problems
            
            #### Common Errors
            - **Syntax Errors**: Missing parentheses, brackets, or semicolons
            - **Logic Errors**: Code runs but produces incorrect results
            - **Runtime Errors**: Code crashes during execution
            
            #### Recommended Practices
            - Add comments to explain complex logic
            - Use meaningful variable names
            - Break down complex functions into smaller ones
            - Test your code with different inputs
            """)
            
    if page == "Code Debugger":
        # Main content area with tabs
        tabs = st.tabs(["💻 Debug Code", "🤖 AI Assistant", "⚙️ Settings"])
        diagram_clicked = False
        security_clicked = False

        with tabs[0]:
            st.markdown("### 🔮 Paste your code below")
            code_input = st.text_area("", height=358, placeholder="Paste your code here...", key="code_input")

            # Action buttons with enhanced UI
            st.markdown('<div class="button-container">', unsafe_allow_html=True)
            col1, col2 = st.columns(2)

            with col1:
                st.markdown(
                    '<button class="custom-button" id="explain-btn" onclick="document.querySelector(\'#explain-btn-hidden\').click()">🔍 Explain Code </button>',
                    unsafe_allow_html=True
                )
                explain_clicked = st.button("🔍 Explain Code", key="explain-btn-hidden", help="Get a beginner-friendly explanation of your code")

                st.markdown(
                    '<button class="custom-button" id="diagram-btn" onclick="document.querySelector(\'#diagram-btn-hidden\').click()">📊 Generate Flow Diagram</button>',
                    unsafe_allow_html=True
                )
                diagram_clicked = st.button("📊 Generate Flow Diagram", key="diagram-btn-hidden", help="Create a visual diagram of your code flow")

            with col2:
                st.markdown(
                    '<button class="custom-button" id="fix-btn" onclick="document.querySelector(\'#fix-btn-hidden\').click()">🔧 Fix </button>',
                    unsafe_allow_html=True
                )
                fix_clicked = st.button("🔧 Fix the code ", key="fix-btn-hidden", help="Get an improved version of your code with fixes")

                st.markdown(
                    '<button class="custom-button" id="security-btn" onclick="document.querySelector(\'#security-btn-hidden\').click()">🔐 Security Scan</button>',
                    unsafe_allow_html=True
                )
                security_clicked = st.button("🔐 Security Scan", key="security-btn-hidden", help="Check your code for vulnerabilities and quality issues")

            st.markdown('</div>', unsafe_allow_html=True)

            # Process actions
            if explain_clicked:
                if code_input.strip():
                    st.markdown('<div class="result-container">', unsafe_allow_html=True)
                    st.markdown("### 🔍 Code Explanation")

                    with st.spinner("Generating explanation..."):
                        explanation = explain_code_with_gemini(code_input)

                    st.markdown(explanation)
                    st.markdown('</div>', unsafe_allow_html=True)
                else:
                    st.error("⚠️ Please enter some code to explain!")

            if fix_clicked:
                if code_input.strip():
                    st.markdown('<div class="result-container">', unsafe_allow_html=True)
                    st.markdown("### 🔧 Fixed & Secure Code")

                    with st.spinner("Fixing and securing code..."):
                        fixed_code = get_fixed_code_with_groq(code_input)

                    if fixed_code:
                        st.code(fixed_code, language='python')

                        # Copy button
                        if st.button("📋 Copy Fixed Code"):
                            st.code(fixed_code)
                            st.success("✅ Code copied to clipboard!")
                    else:
                        st.warning("⚠️ No fixes found or generated. Double-check your code!")

                    st.markdown('</div>', unsafe_allow_html=True)
                else:
                    st.error("⚠️ Please enter some code to fix!")

            if diagram_clicked:
                if code_input.strip():
                    st.markdown('<div class="result-container">', unsafe_allow_html=True)
                    st.markdown("### 📊 Code Flow Diagram")

                    with st.spinner("Generating flow diagram..."):
                        flow_diagram = generate_code_flow(code_input)

                    st.markdown(f"```mermaid\n{flow_diagram}\n```")
                    st.markdown('</div>', unsafe_allow_html=True)
                else:
                    st.error("⚠️ Please enter some code to generate a diagram!")

            if security_clicked:
                if code_input.strip():
                    st.markdown('<div class="result-container">', unsafe_allow_html=True)
                    st.markdown("### 🔐 Security & Vulnerability Report")

                    with st.spinner("Scanning for vulnerabilities..."):
                        security_report = run_security_scan(code_input)

                    st.markdown(security_report)
                    st.markdown('</div>', unsafe_allow_html=True)
                else:
                    st.error("⚠️ Please enter some code to scan for vulnerabilities!")
                    
        with tabs[1]:  # AI Assistant tab
            st.markdown("### 🤖 AI Debugging Assistant")
            st.markdown("Ask the AI for help with your debugging issues.")

            assistant_code = st.text_area("Your code:", height=300, key="assistant_code")
            assistant_question = st.text_area("Ask your question:", height=150, key="assistant_question")

            if st.button("Ask AI", key="assistant_button"):
                if assistant_code.strip() and assistant_question.strip():
                    st.markdown('<div class="result-container">', unsafe_allow_html=True)
                    st.markdown("### 🤖 AI Response")

                    with st.spinner("Asking AI..."):
                        assistant_response = get_ai_assistant_response(assistant_code, assistant_question)

                    st.markdown(assistant_response)
                    st.markdown('</div>', unsafe_allow_html=True)
                else:
                    st.error("⚠️ Please provide both code and a question!")

        with tabs[2]:
            st.markdown("### ⚙️ FIXIFOX Settings")

            st.markdown("#### 🎨 UI Theme")
            theme = st.selectbox("Select theme:",
                                                 ["Dark Premium (Default)", "Neon Fox", "Midnight Coder", "Forest Green"],
                                                 index=0)
            
                        # Apply the selected theme
            def apply_theme(theme):
                if theme == "Dark Premium (Default)":
                    st.markdown(
                        """
                        <style>
                        body, .main {
                            background: linear-gradient(-45deg, #0f0c29, #302b63, #24243e, #4b0082, #800080);
                            background-size: 400% 400%;
                            animation: gradient-shift 15s ease infinite;
                            color: #fff;
                            font-family: 'Inter', 'Poppins', sans-serif;
                        }
                        </style>
                        """,
                        unsafe_allow_html=True
                    )
                elif theme == "Neon Fox":
                    st.markdown(
                        """
                        <style>
                        body, .main {
                            background: linear-gradient(-45deg, #ff00cc, #3333ff, #ff00cc);
                            background-size: 400% 400%;
                            animation: gradient-shift 15s ease infinite;
                            color: #fff;
                            font-family: 'Inter', 'Poppins', sans-serif;
                        }
                        </style>
                        """,
                        unsafe_allow_html=True
                    )
                elif theme == "Midnight Coder":
                    st.markdown(
                        """
                        <style>
                        body, .main {
                            background: linear-gradient(-45deg, #1a1a2e, #16213e, #0f3460, #1a1a2e);
                            background-size: 400% 400%;
                            animation: gradient-shift 15s ease infinite;
                            color: #fff;
                            font-family: 'Inter', 'Poppins', sans-serif;
                        }
                        </style>
                        """,
                        unsafe_allow_html=True
                    )
                elif theme == "Forest Green":
                    st.markdown(
                        """
                        <style>
                        body, .main {
                            background: linear-gradient(-45deg, #004d00, #006600, #009900, #00cc00);
                            background-size: 400% 400%;
                            animation: gradient-shift 15s ease infinite;
                            color: #fff;
                            font-family: 'Inter', 'Poppins', sans-serif;
                        }
                        </style>
                        """,
                        unsafe_allow_html=True
                    )

            apply_theme(theme)

            st.markdown("#### 🤖 AI Models")
            explanation_model = st.selectbox("Explanation model:",
                             ["Gemini 2.0 Flash (Default)", "Gemini 2.0 Pro"],
                             index=0)

            code_fix_model = st.selectbox("Code fixing model:",
                          ["Qwen 2.5 Coder 32B (Default)", "Qwen 2.5 Coder 7B", "Llama 3 70B"],
                          index=0)

            st.markdown("#### ⚡ Performance")
            response_detail_level = st.slider("Response detail level:", min_value=1, max_value=10, value=7)

            if st.button("💾 Save Settings"):
             st.session_state.theme = theme
             st.session_state.explanation_model = explanation_model
             st.session_state.code_fix_model = code_fix_model
             st.session_state.response_detail_level = response_detail_level
             st.success("✅ Settings saved successfully!")

    elif page == "Code Generation":
        st.markdown("### ✍️ Code Generation from Text")
        st.markdown("Generate code by describing your requirements in text.")

        text_input = st.text_area("Describe your requirements:", height=370, placeholder="Enter your requirements here...")

        if st.button("Generate Code"):
            if text_input.strip():
                st.markdown('<div class="result-container">', unsafe_allow_html=True)
                st.markdown("### 💻 Generated Code")
                with st.spinner("Generating code..."):
                    generated_code = generate_code_from_text(text_input)
                    if generated_code:
                        st.code(generated_code, language='python')
                    else:
                        st.error("⚠️ Failed to generate code.")
                st.markdown('</div>', unsafe_allow_html=True)
            else:
                st.error("⚠️ Please enter some text to generate code.")

    elif page == "Code Conversion":
        st.markdown("### 🔄 Code Language Conversion")
        st.markdown("Convert code from one language to another.")
        code_to_convert = st.text_area("Enter code to convert:", height=350)
        
        # Supported languages based on your requirements
        languages = [
            "Python", "JavaScript", "Java", "C", "C++", "C#",
            "Dart", "Kotlin", "PHP", "Swift", "Go", "Rust"
        ]
        
        col1, col2 = st.columns(2)
        with col1:
            source_language = st.selectbox("Source language:", languages)
        with col2:
            # Filter target language to exclude the selected source language
            target_language = st.selectbox("Target language:", 
                                         [lang for lang in languages if lang != source_language])
        
        # Optional: Add advanced options
        with st.expander("Advanced Options"):
            explain_conversion = st.checkbox("Explain conversion changes", value=False)
        
        if st.button("Convert Code"):
            if code_to_convert.strip():
                with st.spinner(f"Converting code from {source_language} to {target_language}..."):
                    try:
                        # Calling the function with only the supported parameters
                        converted_code = convert_code_language(
                            code_to_convert, 
                            source_language, 
                            target_language
                        )
                        
                        if converted_code:
                            st.markdown('<div class="result-container">', unsafe_allow_html=True)
                            st.markdown(f"### 🔄 Converted Code ({target_language})")
                            st.code(converted_code, language=target_language.lower())
                            
                            if explain_conversion:
                                st.markdown("### 📝 Conversion Explanation")
                                # Simple explanation if get_conversion_explanation isn't implemented
                                explanation = f"""
                                The code has been converted from {source_language} to {target_language}.
                                Key changes include:
                                - Syntax adaptation from {source_language} to {target_language} conventions
                                - Equivalent language constructs used where direct translation wasn't possible
                                - Maintained core logic and functionality
                                """
                                st.write(explanation)
                                
                            # Add download button for the converted code
                            st.download_button(
                                label="Download Converted Code",
                                data=converted_code,
                                file_name=f"converted_code.{target_language.lower()}",
                                mime="text/plain"
                            )
                        else:
                            st.error("⚠️ Conversion failed. No output was generated.")
                    except Exception as e:
                        st.error(f"⚠️ An error occurred during conversion: {str(e)}")
            else:
                st.error("⚠️ Please enter code to convert.")
                
    if page == "Code Compiler":
        st.markdown("### 💻 Online Code Compiler")
        st.markdown("Practice, compile, and run code in multiple languages")

        # Create an iframe for OneCompiler
        st.markdown(
    """
    <div style="display: flex; justify-content: center; align-items: center; margin-top: 20px;">
        <iframe
            frameBorder="1"
            height="640px"  
            src="https://onecompiler.com/embed/" 
            width="100%"
            style="border: 2px solid #6c5ce7; border-radius: 10px; box-shadow: 0 10px 25px rgba(0,0,0,0.2);"
        ></iframe>
    </div>
    """,
    unsafe_allow_html=True,
)

    st.markdown(
    """
    <style>
        .footer {
            position: fixed;
            left: 0;
            bottom: 0;
            width: 100%;
            background-color: #1e1e1e;
            color: white;
            text-align: center;
            padding: 10px 0;
            font-family: Arial, sans-serif;
            box-shadow: 0 -2px 5px rgba(0, 0, 0, 0.2);
            z-index: 1000;
        }
        .footer p {
            margin: 0;
            font-size: 14px;
        }
        .footer a {
            color: #00aaff;
            text-decoration: none;
            margin: 0 5px;
        }
        .footer a:hover {
            text-decoration: underline;
        }
        .footer .social-icons {
            margin-top: 5px;
        }
        .footer .social-icons img {
            width: 20px;
            height: 20px;
            margin: 0 5px;
            vertical-align: middle;
        }
    </style>
    <div class="footer">
        <p>FIXIFOX © 2025 | Premium AI-Powered Code Assistant</p>
        <div class="social-icons">
            </a>
            <a href="https://github.com/RAGAV132/AI-CODE-DEBUGER.git" target="_blank">
                <img src="https://github.githubassets.com/images/modules/logos_page/GitHub-Mark.png" alt="GitHub">
            </a>
            <a href="https://www.linkedin.com/in/ragavan-r-aa8a032b3?lipi=urn%3Ali%3Apage%3Ad_flagship3_profile_view_base_contact_details%3B1iNbWrOTRAukwLj1XjH%2Fpw%3D%3D" target="_blank">
                <img src="https://content.linkedin.com/content/dam/me/business/en-us/amp/brand-site/v2/bg/LI-Bug.svg.original.svg" alt="LinkedIn">
            </a>
        </div>
    </div>
    """,
    unsafe_allow_html=True
)


def get_ai_assistant_response(
    code: str,
    question: str,
    expertise_level: str = "beginner",
    model: str = "meta-llama/llama-4-scout-17b-16e-instruct",
    include_examples: bool = True,
    language: str = None,
    temperature: float = 0.7,
    max_tokens: int = 1024
) -> str:
    """
    Provides AI-powered code assistance for debugging and explanation.

    Args:
        code (str): The code to analyze.
        question (str): The user's question or issue.
        expertise_level (str): "beginner", "intermediate", or "expert".
        model (str): Model name for Groq API.
        include_examples (bool): Whether to include examples.
        language (str): Programming language (optional).
        temperature (float): Model creativity.
        max_tokens (int): Max tokens for response.

    Returns:
        str: AI assistant's response or error message.
    """
    from groq import Groq

    expertise_instructions = {
        "beginner": (
            "- Use simple explanations and define technical terms.\n"
            "- Break down solutions step by step.\n"
            "- Avoid jargon unless explained.\n"
            "- Encourage and be friendly."
        ),
        "intermediate": (
            "- Balance explanation and practical solutions.\n"
            "- Suggest best practices and patterns."
        ),
        "expert": (
            "- Focus on concise, efficient solutions.\n"
            "- Discuss trade-offs and optimizations."
        )
    }
    instructions = expertise_instructions.get(expertise_level, expertise_instructions["beginner"])
    language_hint = f"The code is written in {language}." if language else "Please identify the programming language."
    example_instruction = "Include 1-2 clear examples." if include_examples else ""

    prompt = (
        f"You are an expert AI code assistant.\n\n"
        f"CODE:\n{code}\n\n"
        f"QUESTION:\n{question}\n\n"
        f"{language_hint}\n\n"
        f"INSTRUCTIONS:\n"
        f"- Tailor your help for a {expertise_level} programmer.\n"
        f"- {example_instruction}\n"
        f"- Identify the issue clearly.\n"
        f"- Explain solutions simply.\n"
        f"- Show corrected code if needed.\n"
        f"{instructions}\n"
    )

    try:
        groq_client = Groq()
        response = groq_client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            temperature=temperature,
            max_tokens=max_tokens,
            stream=False
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        error_msg = str(e).lower()
        if "timeout" in error_msg:
            return "The AI assistant timed out. Try simplifying your code or question."
        elif "token" in error_msg:
            return "Your code is too large. Please provide a smaller snippet."
        elif "model" in error_msg:
            return "The selected AI model is unavailable. Try again later."
        return f"AI assistant error: {e}"

if __name__ == "__main__":
    main()
