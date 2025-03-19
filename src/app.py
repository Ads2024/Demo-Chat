import streamlit as st
import streamlit.components.v1 as components
import logging
import yaml
import random
import os
import base64
from datetime import datetime
import time
import re 
import tempfile
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from PIL import Image
from dotenv import load_dotenv
from openai import OpenAI
from service.services import AIAssistantManager
from service.run import StreamlitEventHandler
from styles import get_page_styling,get_particles_js,get_matrix_background, AVATAR_URLS

SETUP = 'interface'

# Welcome messages list
WELCOME_MESSAGES = [
    "Welcome to this Demo Performance Hub! Please add your openai API key in the settings as well as the assistant id to get started.",
    "Greetings! Please add your openai API key in the settings as well as the assistant id to get started.",
    "Welcome aboard! Please add your openai API key in the settings as well as the assistant id to get started."
]

def show_welcome_message():
    """Display a welcome message."""
    st.markdown(f"### {random.choice(WELCOME_MESSAGES)}")

def show_welcome_animation():
    """Display a welcome animation."""
    with st.spinner("Initializing..."):
        time.sleep(2)
    st.balloons()


def display_welcome_banner():
    """Display time-based welcome banner"""
    current_hour = datetime.now().hour
    greeting = "Good Morning" if current_hour < 12 else "Good Afternoon" if current_hour < 17 else "Good Evening"
        
    st.markdown(f"""
        <div style='padding: 1.5rem; border-radius: 10px; background-color: rgba(46, 134, 193, 0.1); 
                    border: 1px solid rgba(46, 134, 193, 0.2); margin-bottom: 1rem;'>
            <h2 style='color: #2E86C1; margin: 0;'>{greeting}! 👋</h2>
            <p style='margin: 0.5rem 0 0 0;'>Welcome to Demo Performance Hub. How can I assist you today?</p>
        </div>
    """, unsafe_allow_html=True)

st.set_page_config(
    page_title="Demo Performance Hub",
    page_icon="✨",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Apply styling immediately after page config
st.markdown(get_particles_js(), unsafe_allow_html=True)



# Initialize session states
if "show_animation" not in st.session_state:
    st.session_state.show_animation = True
if "welcome_shown" not in st.session_state:
    st.session_state.welcome_shown = False
if "conversation_history" not in st.session_state:
    welcome_message = random.choice(WELCOME_MESSAGES)
    st.session_state.conversation_history = [{"role": "assistant", "content": welcome_message}]
if "thread_id" not in st.session_state:
    st.session_state.thread_id = None

if st.session_state.show_animation:
    components.html(get_matrix_background(), height=800, scrolling=False)


def load_data(file_path, key):
    with open(file_path, "r") as file:
        data = yaml.safe_load(file)
        return data[key]

def read_gif(file_path):
    with open(file_path, "rb") as file:
        contents = file.read()
    gif = base64.b64encode(contents).decode("utf-8")
    return gif

def set_env_vars(assistant_id, api_key,vector_store_id=None):
    """Set environment variables for the OpenAI API."""
    if vector_store_id:
        os.environ["VECTOR_STORE_ID"] = vector_store_id
        os.environ["OPENAI_API_KEY"] = api_key
        os.environ["ASSISTANT_ID"] = assistant_id
    else:
        os.environ["OPENAI_API_KEY"] = api_key
        os.environ["ASSISTANT_ID"] = assistant_id

def send_email(from_email,to_email,content,password=None):
    """Send email with specified content."""
    subject = "Demo Performance Hub - Conversation Transcript"

    #Create the MIMEText object
    message = MIMEMultipart()
    message["From"] = from_email   
    message["To"] = to_email
    message["Subject"] = subject

    #Add the message body
    message.attach(MIMEText(content, "plain"))

    #Create the SMTP server

    try:
        with smtplib.SMTP("smtp.gmail.com",587) as server:
            server.starttls()
            server.login(from_email,password)
            if not password:
                raise ValueError("Password must be provided.")
            server.sendmail(from_email,to_email,message.as_string())
            logging.info("Email sent successfully.")
            st.success("Email sent successfully.")
    except Exception as e:
        logging.error(f"Error sending email: {e}")
        st.error("Error sending email. Please check your email settings.")

def wait_for_run_completion(client,thread_id, run_id, timeout=60):
    """Wait for assistant's run to complete"""
    start_time = time.time()
    while True:
        run = client.beta.threads.runs.retrieve(thread_id=thread_id, run_id=run_id)
        if run.status == "completed":
            return run
        elif run.status == "failed":
            st.error("Run failed. Please try again.")
            return False
        elif time.time() - start_time > timeout:
            st.error("Run timed out. Please try again.")
            return False
        time.sleep(1)

def process_email_query(email, query):
    """Process user query and send response via email"""
    try:
        thread_id = get_thread_id()
        if not thread_id:
            st.sidebar.error("Failed to create thread.")
            return False

        client = AIAssistantManager.init_client()
        if not client:
            st.sidebar.error("Failed to initialize client.")
            return False

            # Create message in thread
        message = client.beta.threads.messages.create(
            thread_id=thread_id,
            role="user",
            content=query,
            timeout=30
        )

        # Wait for run to complete
        if not wait_for_run_completion(client, thread_id, message.run_id):
            return False

        # Retrieve assistant's response

        messages  = client.beta.threads.messages.list(thread_id=thread_id)
        latest_response = None

        # Get messages after run completion
        for msg in messages:
            if msg.role =="assistant":
                latest_response = msg.content[0].text.value
                break
        if not latest_response:
            st.sidebar.error("Failed to retrieve assistant's response.")
            return False

        # Send email with response

        if send_email(email, latest_response):
            st.sidebar.success("✔ Email sent successfully!")
            return True
        else:
            st.sidebar.error("❌ Failed to send email.")
            return False
    except Exception as e:
        st.sidebar.error(f"An error occurred: {e}")
        return False
    

def get_thread_id():
    """Get or create thread ID"""
    if st.session_state.thread_id is None:
        st.session_state.thread_id = AIAssistantManager.create_thread()
    return st.session_state.thread_id   

def process_query(assistant_id,query, output_area):
    """Process a user query and generate response"""
    thread_id = get_thread_id()
    if not thread_id:
        st.error("Failed to create thread.")
        return

    client = AIAssistantManager.init_client()

    # Log request for verbose mode

    if st.session_state.verbose_logging:
        st.sidebar.markdown(f"**User Query:** {query}")
        st.sidebar.markdown(f"**Thread ID:** {thread_id}")
        start_time = time.time()
    
    # Add message to thread
    client.beta.threads.messages.create(
        thread_id=thread_id,
        role="user",
        content=query,
        timeout=30
    )
    
    # Stream response
    event_handler = StreamlitEventHandler(output_area)
    try:
        with client.beta.threads.runs.stream(
            thread_id=thread_id,
            assistant_id=assistant_id,
            instructions="",
            event_handler=event_handler,
            timeout=30
        ) as stream:
            current_response = ""
            for delta in stream:
                if hasattr(delta, 'data') and hasattr(delta.data, 'delta'):
                    # Process content blocks
                    content_blocks = getattr(delta.data.delta, 'content', [])
                    if not content_blocks:
                        continue  # Skip if no content blocks
                    
                    for block in content_blocks:
                        # Handle text content
                        if hasattr(block, 'text') and hasattr(block.text, 'value'):
                            text_chunk = block.text.value
                            current_response += text_chunk
                            output_area.markdown(current_response)
                        
                        # Handle image content
                        elif hasattr(block, 'image_file') and block.image_file:
                            try:
                                image_file = block.image_file.file_id
                                if not image_file:
                                    st.error("Image file ID is missing.")
                                    continue
                                
                                # Fetch and process image
                                image_data = client.files.content(image_file).read()
                                temp_file = tempfile.NamedTemporaryFile(delete=False)
                                temp_file.write(image_data)
                                temp_file.close()
                                
                                # Open and display image
                                image = Image.open(temp_file.name)
                                st.image(image, use_column_width=True)
                            except Exception as e:
                                st.error(f"Error processing image: {e}")
                            finally:
                                # Clean up temporary file
                                if temp_file:
                                    os.unlink(temp_file.name)
                        
                        # Handle unknown content types
                        else:
                            st.warning(f"Unexpected content type: {block.type}")

            # Log response time for verbose mode
            if st.session_state.verbose_logging:
                end_time = time.time()
                response_time = round(end_time - start_time, 2)
                st.sidebar.markdown(f"⏱️ **Response Time:** {response_time} seconds")
                st.sidebar.markdown(f"**Response:** {content_blocks}")
            
            # Add complete response to conversation history
            if current_response.strip():
                st.session_state.conversation_history.append({
                    "role": "assistant",
                    "content": current_response.strip()
                })
    except Exception as e:
        st.error(f"An error occurred: {e}")
        if st.session_state.verbose_logging:
            st.sidebar.error(f"An error occurred: {e}")

def render_sidebar():
    """Render the sidebar with settings and options."""
    st.sidebar.title("Settings")
    st.sidebar.markdown("---")

    # Display settings
    st.sidebar.subheader("OpenAI Settings")
    api_key = st.sidebar.text_input("API Key")
    assistant_id = st.sidebar.text_input("Assistant ID")
    vector_store_id = st.sidebar.text_input("Vector Store ID")
    st.sidebar.markdown("---")

    # Display options
    st.sidebar.subheader("Options")
    verbose_logging = st.sidebar.checkbox("Verbose Logging")
    show_animation = st.sidebar.checkbox("Show Animation")
    st.sidebar.markdown("---")

    # Display email options
    st.sidebar.subheader("Email Settings")
    email = st.sidebar.text_input("Email Address")
    query = st.sidebar.text_area("Query")
    password = st.sidebar.text_input("Password", type="password")
    st.sidebar.markdown("---")

    # Display action buttons
    if st.sidebar.button("Send Email"):
        if not email:
            st.sidebar.error("Email address is required.")
        elif not query:
            st.sidebar.error("Query is required.")
        else:
            process_email_query(email, query)

    # Save settings to session state
    st.session_state.api_key = api_key
    st.session_state.assistant_id = assistant_id
    st.session_state.vector_store_id = vector_store_id
    st.session_state.verbose_logging = verbose_logging
    st.session_state.show_animation = show_animation


def main():
    """Main function for the Demo Performance Hub."""
# Show welcome animation only once per session
    if not st.session_state.welcome_shown:
        show_welcome_animation()
        st.session_state.welcome_shown = True
    
    # Render sidebar and get any quick action query
    quick_action_query = render_sidebar()
    
    # Apply styling
    st.markdown(get_page_styling(), unsafe_allow_html=True)
    
    # Add particles.js background
    if st.session_state.show_animation:
        components.html(get_matrix_background(), height=0)

    # Display welcome banner
    display_welcome_banner()

    for message in st.session_state.conversation_history:
        with st.chat_message(
            message["role"],
            avatar=AVATAR_URLS.get(message["role"])
        ):
            st.write(message["content"])


    if quick_action_query:
        with st.chat_message("user", avatar=AVATAR_URLS["user"]):
            st.write(quick_action_query)
        
        st.session_state.conversation_history.append({
            "role": "user",
            "content": quick_action_query
        })
        
        with st.chat_message("assistant", avatar=AVATAR_URLS["assistant"]):
            output_area = st.empty()
            process_query(st.session_state.assistant_id, quick_action_query, output_area)

    # User input
    if user_query := st.chat_input("Enter your query..."):
        with st.chat_message("user", avatar=AVATAR_URLS["user"]):
            st.write(user_query)
            
        st.session_state.conversation_history.append({
            "role": "user",
            "content": user_query
        })

        with st.chat_message("assistant", avatar=AVATAR_URLS["assistant"]):
            output_area = st.empty()
            process_query(st.session_state.assistant_id, user_query, output_area)


if __name__ == "__main__":
    main()