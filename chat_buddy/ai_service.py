from openai import OpenAI
from django.conf import settings
import PyPDF2
from PIL import Image
import pytesseract
from pdf2image import convert_from_path
import tempfile
import os

# Configure Tesseract path for Windows
pytesseract.pytesseract.pytesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'
poppler_path = r'C:\Users\HomePC\Downloads\poppler\poppler-25.12.0\Library\bin'

if os.path.exists(poppler_path):
    os.environ['PATH'] += os.pathsep + poppler_path

# Initialize OpenAI client
client = OpenAI(api_key=settings.OPENAI_API_KEY)

def extract_text_from_pdf(pdf_path):
    """Extract text content from PDF file with fallback to OCR for image-based PDFs"""
    text = ""
    try:
        # First try normal PDF text extraction
        with open(pdf_path, 'rb') as file:
            pdf_reader = PyPDF2.PdfReader(file)
            for page in pdf_reader.pages:
                extracted = page.extract_text()
                if extracted:
                    text += extracted + "\n"
        
        # If no text was extracted, try OCR on PDF pages
        if not text.strip():
            text = extract_text_from_pdf_with_ocr(pdf_path)
            
    except Exception as e:
        # If normal extraction fails, try OCR
        try:
            text = extract_text_from_pdf_with_ocr(pdf_path)
        except:
            raise Exception(f"Failed to extract PDF text: {str(e)}")
    
    return text if text.strip() else "Unable to extract text from this PDF."


def extract_text_from_pdf_with_ocr(pdf_path):
    """Extract text from PDF by converting pages to images and using OCR"""
    text = ""
    try:
        # Convert PDF pages to images with Poppler path
        try:
            images = convert_from_path(pdf_path, first_page=1, last_page=10, poppler_path=poppler_path if os.path.exists(poppler_path) else None)
        except:
            # Fallback: try without explicit poppler_path
            images = convert_from_path(pdf_path, first_page=1, last_page=10)
        
        # Extract text from each image using OCR
        for img in images:
            img_text = pytesseract.image_to_string(img)
            if img_text.strip():
                text += img_text + "\n"
        
        return text if text.strip() else "No readable text found in this PDF."
    except Exception as e:
        raise Exception(f"Failed to extract text from PDF using OCR: {str(e)}")


def extract_text_from_image(image_path):
    """Extract text from image using OCR (Optical Character Recognition)"""
    try:
        image = Image.open(image_path)
        text = pytesseract.image_to_string(image)
        if not text.strip():
            return "No readable text found in this image."
        return text
    except Exception as e:
        raise Exception(f"Failed to extract text from image: {str(e)}")


def summarize_pdf(pdf_path):
    """
    Summarize PDF content with structured formatting
    """
    try:
        pdf_text = extract_text_from_pdf(pdf_path)
        
        if not pdf_text.strip():
            return "Unable to extract text from this PDF. The document may be image-based or encrypted."
        
        # Limit text length for API context window
        pdf_text = pdf_text[:8000] 
        
        # UPDATED PROMPT: Added strict Markdown formatting rules for readability
        prompt = f"""You are LearnBuddy. Analyze this material and provide a STYLED summary.

### FORMATTING RULES:
1. Use ## for Section Headers.
2. Use * for Bullet Points.
3. Use --- to separate sections.
4. Always put a double line break between paragraphs.

Document Content:
{pdf_text}

Please provide:
## Overview
(2-3 sentences about the main topic)

---
## Key Concepts
* (Concept 1)
* (Concept 2)

---
## Learning Objectives
* (Goal 1)

---
## Notable Facts
* (Fact 1)

If this contains religious content, highlight it warmly. Format in a friendly, helpful tone.

in the course of summarizing documents, do not give the same response as the general response. give a more clear, precise and conscise explanation. kind of giving a more detailed explanation about the document's content.
"""

        system_message = "You are LearnBuddy, a helpful assistant. You always process markdown headers from the code and you give the readable response with the processed styled headers and bullet points to keep your responses organized and readable."

        messages = [
            {"role": "system", "content": system_message},
            {"role": "user", "content": prompt}
        ]
        
        response = client.chat.completions.create(
            model="gpt-4o-mini",  # Using GPT-4o mini for cost efficiency. Change to "gpt-4" if needed
            messages=messages,
            max_tokens=2000,
            temperature=0.7,
            stream=False,
        )
        
        result = response.choices[0].message.content
        print(f"Successfully summarized PDF using OpenAI (GPT-4o mini)")
        return result
        
    except Exception as e:
        return f"I processed the PDF, but encountered an issue generating a detailed summary. Error: {str(e)}"


def summarize_image(image_path):
    """
    Extract and analyze text from image with structured formatting
    """
    try:
        image_text = extract_text_from_image(image_path)
        
        if not image_text.strip():
            return "Unable to extract text from this image. The image may be too blurry or contain no readable text."
        
        # Limit text length for API context window
        image_text = image_text[:8000]
        
        prompt = f"""You are LearnBuddy. Analyze this text extracted from an image and provide a STYLED summary.

### FORMATTING RULES:
1. Use ## for Section Headers.
2. Use * for Bullet Points.
3. Use --- to separate sections.
4. Always put a double line break between paragraphs.

Extracted Text from Image:
{image_text}

Please provide:
## Overview
(2-3 sentences about the main content)

---
## Key Points
* (Point 1)
* (Point 2)

---
## Notable Information
* (Info 1)

Format in a friendly, helpful tone. Be clear and precise in your explanation."""

        system_message = "You are LearnBuddy, a helpful assistant. You always process markdown headers and provide organized, readable responses with styled headers and bullet points."

        messages = [
            {"role": "system", "content": system_message},
            {"role": "user", "content": prompt}
        ]
        
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=messages,
            max_tokens=2000,
            temperature=0.7,
            stream=False,
        )
        
        result = response.choices[0].message.content
        print(f"Successfully analyzed image using OpenAI (GPT-4o mini)")
        return result
        
    except Exception as e:
        return f"I processed the image, but encountered an issue generating a summary. Error: {str(e)}"


def ask_buddy(user_message, conversation_history=None, material_context=None, 
              system_context=None, is_christian_topic=False, file=None):
    """
    Get AI response with improved layout
    """
    try:
        system_message = """You are LearnBuddy. Your personality:
1. CHRISTIAN TOPICS: Use Scripture and emojis (not essentially necessary).
2. EDUCATIONAL CONTENT: Break down complex topics using bullet points and headers.
3. GENERAL TONE: Friendly and organized. Always use double line breaks between ideas.
4. MATHEMATICS GENIUS: Break down complex mathematical problems and give readable and understandable results depending on the age range of the user."""

        if system_context:
            system_message = system_context
        
        messages = [{"role": "system", "content": system_message}]
        
        if conversation_history:
            for msg in conversation_history[-4:]: 
                role = msg.get('role', 'user')
                if 'parts' in msg:
                    content = msg['parts'][0] if msg['parts'] else ""
                elif 'text' in msg:
                    content = msg['text']
                elif 'content' in msg:
                    content = msg['content']
                else:
                    content = str(msg)
                
                if role == 'model': role = 'assistant'
                
                if content:
                    messages.append({
                        "role": role if role in ['user', 'assistant'] else 'user',
                        "content": str(content)[:500]
                    })
        
        current_message = ""
        if material_context:
            current_message += f"STUDY MATERIAL CONTEXT:\n{material_context[:2000]}\n\n"
        
        if is_christian_topic:
            current_message += "Respond with warmth and Scripture using clear headers.\n\n"
        
        current_message += f"{user_message}"
        messages.append({"role": "user", "content": current_message})
        
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=messages,
            max_tokens=1000,
            temperature=0.8,
            stream=False,
        )
        
        result = response.choices[0].message.content
        return result
        
    except Exception as e:
        if is_christian_topic:
            return "I'm experiencing a technical issue. Please share a specific verse you'd like to discuss."
        return f"I'm here to help, but I encountered a technical issue. (Error: {str(e)})"