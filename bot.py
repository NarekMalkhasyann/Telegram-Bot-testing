import os
import time
import asyncio
import logging
import json
from google import genai
from google.genai import types
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from API_key import api_key, telegram_api_key


# Suppress noisy terminal output from HTTP libraries
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.WARNING
)
logging.getLogger("httpx").setLevel(logging.WARNING)

# Initialize the Gemini Client
client = genai.Client(api_key)

# Load the AI Persona
try:
    with open("persona.txt", "r", encoding="utf-8") as file:
        persona_prompt = file.read()
except FileNotFoundError:
    persona_prompt = ""

# Dictionary to store chat sessions per user ID for conversational context
chat_sessions = {}

# Dictionary to store the last request time per user to enforce 12-second delay
user_last_request_time = {}

def save_history(user_id, chat):
    history_data = []
    # get_history() returns a list of types.Content
    for content in chat.get_history():
        parts = [{"text": part.text} for part in content.parts if part.text]
        history_data.append({"role": content.role, "parts": parts})
    
    with open(f"history_{user_id}.json", "w", encoding="utf-8") as f:
        json.dump(history_data, f, ensure_ascii=False, indent=2)

def load_history(user_id):
    try:
        with open(f"history_{user_id}.json", "r", encoding="utf-8") as f:
            data = json.load(f)
            history = []
            for item in data:
                parts = [types.Part.from_text(text=p["text"]) for p in item["parts"]]
                history.append(types.Content(role=item["role"], parts=parts))
            return history
    except FileNotFoundError:
        return None

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # context.args captures everything after "/start" as a list of strings
    args = context.args 
    
    if args:
        payload = args[0]  # This is your custom parameter
        
        # 1. Check the payload to see what environment to create
        if payload == "test-env":
            await update.message.reply_text("🛠️ Spinning up your Test Environment...")
            # Run your custom app logic for the test environment here
            
        elif payload.startswith("user_"):
            user_id = payload.split("_")[1]
            await update.message.reply_text(f"👤 Loading workspace for User {user_id}...")
            # Load custom database records for this user
            
        else:
            await update.message.reply_text(f"Received custom setup code: {payload}")
            
    else:
        # Standard start without any special link parameters
        await update.message.reply_text("👋 Hello! Welcome to the main menu.")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    text = update.message.text
    
    # Enforce 12-second delay to prevent Gemini API free-tier rate limits
    current_time = time.time()
    last_time = user_last_request_time.get(user_id, 0)
    time_since_last = current_time - last_time
    
    if time_since_last < 12:
        await asyncio.sleep(12 - time_since_last)
        
    # Update last request time before hitting the API
    user_last_request_time[user_id] = time.time()
    
    # Initialize a new chat session for the user if it doesn't exist
    if user_id not in chat_sessions:
        # Disable safety settings for an uncensored experience

        
        safety_settings = [
            types.SafetySetting(category="HARM_CATEGORY_HATE_SPEECH", threshold="BLOCK_NONE"),
            # types.SafetySetting(category="HARM_CATEGORY_DANGEROUS_CONTENT", threshold="BLOCK_NONE"),
            # types.SafetySetting(category="HARM_CATEGORY_SEXUALLY_EXPLICIT", threshold="BLOCK_NONE"),
            # types.SafetySetting(category="HARM_CATEGORY_HARASSMENT", threshold="BLOCK_NONE"),
            # types.SafetySetting(category="HARM_CATEGORY_CIVIC_INTEGRITY", threshold="BLOCK_NONE")
        ]

        # Create a chat session with the newer google-genai library
        config = types.GenerateContentConfig(
            system_instruction=persona_prompt,
            safety_settings=safety_settings
        )
        
        loaded_history = load_history(user_id)
        
        chat_sessions[user_id] = client.chats.create(
            model="gemini-3.1-flash-lite-preview",
            config=config,
            history=loaded_history
        )
    
    # Retrieve the user's specific chat session
    chat = chat_sessions[user_id]
    
    try:
        # Send the user's message to the AI and get the response
        response = chat.send_message(text)
        await update.message.reply_text(response.text)
        
        # Save the updated conversation history to a file
        save_history(user_id, chat)
    except Exception as e:
        await update.message.reply_text("Sorry, I encountered an error while thinking. 😔")
        print(f"AI ERROR: {e}")

async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    print(f"BOT ERROR: {context.error}")

def main():
    # Replace with your actual BotFather token
    app = Application.builder().token(telegram_api_key).build()
    
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.add_error_handler(error_handler)
    
    print("Bot is listening for environments...")
    app.run_polling()

if __name__ == '__main__':
    main()