"""
Chatbot — programmatic session.

Requires: pip install "pdf-autofillr[chatbot]"
"""
from chatbot import chatbotClient

client = chatbotClient.from_env()

# Start a new session
session = client.create_session(
    pdf_path="data/input/blank_form.pdf",
    user_id="user_001",
)

print(f"Session: {session.session_id}")
print(f"First message: {session.greeting}")

# Send messages (simulating user input)
messages = [
    "I'd like to fill out the LP subscription form",
    "Jane Smith",           # name
    "Individual investor",  # type
    "500,000",              # commitment
    "jane@example.com",     # email
    "yes",                  # confirm and fill
]

for msg in messages:
    response = client.send_message(session.session_id, msg)
    print(f"User: {msg}")
    print(f"Bot:  {response.message}")
    if response.pdf_filled:
        print(f"Filled PDF: {response.filled_pdf_path}")
        break
