import streamlit as st
import random

TIPS = [
    "🤖 Did you know? Neural networks were inspired by biological neurons!",
    "📚 You've processed thousands of words – keep learning! 💪",
    "🎓 AI Lecture Recorder – built for smarter learning. 🚀",
    "🔥 Use the Chat page to ask questions about any lecture. 💬",
    "📊 Your performance dashboard tracks your progress. 📈",
    "🧠 Learning is like gradient descent – small steps lead to big results! 🎯",
    "🔬 The human brain has ~86 billion neurons – all working together! 🤯",
    "🧪 The first neural network was created in 1958 – the Perceptron. 📅",
    "📖 Your brain processes images in milliseconds – faster than any AI. ⚡",
    "🎯 Repetition is key to learning – spaced repetition helps retention. 📝",
    "💡 Imagination is more important than knowledge. – Einstein ✨",
    "🛌 Sleep is essential for memory consolidation – don't skip it! 🌙",
    "⚡ Your brain generates enough electricity to power a small lightbulb. 💡",
    "🔄 Neural networks 'learn' by adjusting weights – just like you adjust your thinking! 🧩",
]

def show_loading_overlay(message: str = "Processing...", spinner_size: int = 40):
    """Show a full‑screen loading overlay with a random tip (changes each time you show it)."""
    tip = random.choice(TIPS)
    placeholder = st.empty()
    
    size = spinner_size
    border_width = max(4, size // 10)
    
    html = f"""
    <div id="loading-overlay" style="position: fixed; top: 0; left: 0; width: 100%; height: 100%; 
                background: rgba(0,0,0,0.75); display: flex; flex-direction: column; 
                align-items: center; justify-content: center; z-index: 9999; 
                color: white; font-family: sans-serif; padding: 20px;">
        <div style="border: {border_width}px solid #f3f3f3; border-top: {border_width}px solid #4CAF50; 
                    border-radius: 50%; width: {size}px; height: {size}px; 
                    animation: spin 1s linear infinite;"></div>
        <div style="font-size: 22px; margin-top: 20px; font-weight: 500;">{message}</div>
        <div id="tip-text" style="font-size: 18px; margin-top: 15px; max-width: 550px; text-align: center; opacity: 0.9; line-height: 1.6;">
            💡 Fact: {tip}
        </div>
        <style>
        @keyframes spin {{
            0% {{ transform: rotate(0deg); }}
            100% {{ transform: rotate(360deg); }}
        }}
        </style>
    </div>
    """
    placeholder.markdown(html, unsafe_allow_html=True)
    return placeholder

def clear_loading(placeholder):
    placeholder.empty()