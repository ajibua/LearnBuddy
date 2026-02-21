import google.generativeai as genai
from django.conf import settings
import PyPDF2
from PIL import Image
import pytesseract
from pdf2image import convert_from_path
from docx import Document
import tempfile
import os

# Try to import web search functionality, but don't fail if it's not available
try:
    from .web_service import search_web, format_search_results_for_ai, is_current_event_question
    WEB_SEARCH_AVAILABLE = True
except ImportError as e:
    print(f"Warning: Web search not available: {e}")
    WEB_SEARCH_AVAILABLE = False
    
    # Dummy fallback functions
    def search_web(query, max_results=3):
        return None
    
    def format_search_results_for_ai(results):
        return ""
    
    def is_current_event_question(message):
        return False

# Configure Tesseract path for Windows
pytesseract.pytesseract.pytesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'
poppler_path = r'C:\Users\HomePC\Downloads\poppler\poppler-25.12.0\Library\bin'

if os.path.exists(poppler_path):
    os.environ['PATH'] += os.pathsep + poppler_path

# Initialize Google Generative AI with proper error handling
google_api_key = getattr(settings, 'GOOGLE_API_KEY', None) or os.getenv('GOOGLE_API_KEY')
if not google_api_key:
    raise ValueError("GOOGLE_API_KEY is not set. Please add it to your .env file or Django settings.")

genai.configure(api_key=google_api_key)
model = genai.GenerativeModel('gemini-2.5-flash')

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
        
        # If no text was extracted and tesseract is available, try OCR on PDF pages
        if not text.strip() and is_tesseract_available():
            try:
                text = extract_text_from_pdf_with_ocr(pdf_path)
            except:
                pass  # If OCR fails, just keep the empty text
            
    except Exception as e:
        # If normal extraction fails, try OCR if available
        if is_tesseract_available():
            try:
                text = extract_text_from_pdf_with_ocr(pdf_path)
            except:
                pass
        if not text.strip():
            raise Exception(f"Failed to extract PDF text: {str(e)}")
    
    return text if text.strip() else "Unable to extract text from this PDF."


def is_tesseract_available():
    """Check if tesseract is installed and available"""
    try:
        pytesseract.get_tesseract_version()
        return True
    except:
        return False


def extract_text_from_pdf_with_ocr(pdf_path):
    """Extract text from PDF by converting pages to images and using OCR or Gemini vision"""
    text = ""
    try:
        # Convert PDF pages to images with Poppler path
        try:
            images = convert_from_path(pdf_path, first_page=1, last_page=10, poppler_path=poppler_path if os.path.exists(poppler_path) else None)
        except:
            # Fallback: try without explicit poppler_path
            images = convert_from_path(pdf_path, first_page=1, last_page=10)
        
        # Try tesseract OCR first if available
        if is_tesseract_available():
            for img in images:
                img_text = pytesseract.image_to_string(img)
                if img_text.strip():
                    text += img_text + "\n"
        else:
            # Fallback: Use Gemini's vision API to analyze PDF images
            for idx, img in enumerate(images):
                try:
                    # Save image to temporary file for Gemini API
                    with tempfile.NamedTemporaryFile(delete=False, suffix='.png') as tmp_img:
                        img.save(tmp_img.name)
                        
                        # Upload to Gemini
                        with open(tmp_img.name, 'rb') as f:
                            img_data = f.read()
                        
                        # Use Gemini to extract text from image
                        response = model.generate_content([
                            f"Extract and transcribe ALL text from this PDF page image. Be precise and complete. Page {idx + 1}:",
                            {
                                "mime_type": "image/png",
                                "data": img_data,
                            }
                        ])
                        
                        if response.text.strip():
                            text += response.text + "\n"
                        
                        # Clean up
                        os.unlink(tmp_img.name)
                except Exception as e:
                    print(f"Error processing page {idx + 1} with Gemini: {e}")
                    continue
        
        return text if text.strip() else "No readable text found in this PDF."
    except Exception as e:
        raise Exception(f"Failed to extract text from PDF using OCR: {str(e)}")


def extract_text_from_image(image_path):
    """Extract text from image using OCR (Optical Character Recognition)"""
    try:
        if not is_tesseract_available():
            return "📷 Image uploaded. Please ask me questions about it and I'll help analyze it!"
        
        image = Image.open(image_path)
        text = pytesseract.image_to_string(image)
        if not text.strip():
            return "No readable text found in this image."
        return text
    except Exception as e:
        return "📷 Image uploaded. Please ask me questions about it and I'll help analyze it!"


def extract_text_from_word(doc_path):
    """Extract text from Word document (.docx or .doc)"""
    try:
        doc = Document(doc_path)
        text = ""
        
        # Extract text from paragraphs
        for paragraph in doc.paragraphs:
            if paragraph.text.strip():
                text += paragraph.text + "\n"
        
        # Extract text from tables if present
        for table in doc.tables:
            for row in table.rows:
                row_text = []
                for cell in row.cells:
                    row_text.append(cell.text.strip())
                text += " | ".join(row_text) + "\n"
        
        if not text.strip():
            return "No readable text found in this Word document."
        
        return text
    except Exception as e:
        return f"Failed to extract text from Word document: {str(e)}"


def summarize_pdf(pdf_path):
    """
    Summarize PDF content with structured formatting using Google Gemini
    """
    try:
        pdf_text = extract_text_from_pdf(pdf_path)
        
        if not pdf_text.strip():
            return "Unable to extract text from this PDF. The document may be image-based or encrypted."
        
        # Limit text length for API context window
        pdf_text = pdf_text[:8000] 
        
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
In the course of summarizing documents, do not give the same response as the general response. Give a more clear, precise and concise explanation with more detailed explanation about the document's content."""

        response = model.generate_content(prompt)
        result = response.text
        print(f"Successfully summarized PDF using Google Gemini 2.5 Flash")
        return result
        
    except Exception as e:
        return f"I processed the PDF, but encountered an issue generating a detailed summary. Error: {str(e)}"


def summarize_image(image_path):
    """
    Extract and analyze text from image with structured formatting using Google Gemini
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

        response = model.generate_content(prompt)
        result = response.text
        print(f"Successfully analyzed image using Google Gemini 2.5 Flash")
        return result
        
    except Exception as e:
        return f"I processed the image, but encountered an issue generating a summary. Error: {str(e)}"


def summarize_document(doc_path):
    """
    Extract and summarize text from Word documents (.docx) with structured formatting
    """
    try:
        doc_text = extract_text_from_word(doc_path)
        
        if not doc_text.strip() or "Failed to extract" in doc_text:
            return doc_text if doc_text else "Unable to extract text from this document."
        
        # Limit text length for API context window
        doc_text = doc_text[:8000]
        
        prompt = f"""You are LearnBuddy. Analyze this text extracted from a Word document and provide a STYLED summary.

### FORMATTING RULES:
1. Use ## for Section Headers.
2. Use * for Bullet Points.
3. Use --- to separate sections.
4. Always put a double line break between paragraphs.

Document Content:
{doc_text}

Please provide:
## Overview
(2-3 sentences about the document)

---
## Key Concepts
* (Concept 1)
* (Concept 2)

---
## Important Topics
* (Topic 1)

---
## Key Takeaways
* (Takeaway 1)

Format in a friendly, helpful tone. Be clear and precise in your explanation."""

        response = model.generate_content(prompt)
        result = response.text
        print(f"Successfully summarized document using Google Gemini 2.5 Flash")
        return result
        
    except Exception as e:
        return f"I processed the document, but encountered an issue generating a summary. Error: {str(e)}"
def ask_buddy(user_message, conversation_history=None, material_context=None, 
              system_context=None, is_christian_topic=False, file=None):
    """
    Get AI response with improved layout using Google Gemini
    Includes real-time web search for current events/news questions
    """
    try:
        system_message = """You are LearnBuddy. Your personality:
1. CHRISTIAN TOPICS: Use Scripture references and be warm and encouraging (not necessarily emojis).
2. EDUCATIONAL CONTENT: Break down complex topics using bullet points and headers.
3. GENERAL TONE: Friendly and organized. Always use double line breaks between ideas.
4. MATHEMATICS GENIUS: For mathematical content:
   - ALWAYS use Unicode superscript/subscript characters directly in your output:
     * Superscripts: Use ⁰¹²³⁴⁵⁶⁷⁸⁹ instead of writing ^2, ^3, etc.
     * Subscripts: Use ₀₁₂₃₄₅₆₇₈₉ instead of writing _1, _2, etc.
     * Examples: x² instead of x^2, a₁ instead of a_1, E=mc² instead of E=mc^2
   - Use proper mathematical symbols: × or · for multiplication, ÷ for division
   - Never spell out mathematical operations (not "x times y", not "x squared")
   - Use mathematical symbols for operators (not words)
   - For Greek letters use: π, α, β, γ, δ, ε, ζ, η, θ, λ, μ, ν, ξ, ρ, σ, τ, φ, χ, ψ, ω
   - Break down complex problems with clear steps
   - Keep output clean and readable with proper mathematical formatting"""

        if system_context:
            system_message = system_context
        
        # Check if user is asking about current events
        current_event_info = ""
        if is_current_event_question(user_message):
            try:
                search_results = search_web(user_message, max_results=3)
                if search_results and (search_results.get('news') or search_results.get('knowledge')):
                    current_event_info = format_search_results_for_ai(search_results)
            except Exception as e:
                # Silently fail - don't break the chat if search fails
                print(f"Web search error: {e}")
        
        # Build conversation context
        conversation_text = ""
        if conversation_history:
            for msg in conversation_history[-4:]:  # Last 4 messages for context
                role = msg.get('role', 'user')
                if 'parts' in msg:
                    content = msg['parts'][0] if msg['parts'] else ""
                elif 'text' in msg:
                    content = msg['text']
                elif 'content' in msg:
                    content = msg['content']
                else:
                    content = str(msg)
                
                if role == 'model':
                    role = 'Assistant'
                elif role == 'assistant':
                    role = 'Assistant'
                else:
                    role = 'User'
                
                if content:
                    conversation_text += f"{role}: {str(content)[:500]}\n\n"
        
        # Build full prompt
        full_prompt = system_message + "\n\n"
        
        if conversation_text:
            full_prompt += "Previous conversation:\n" + conversation_text + "\n"
        
        if material_context:
            full_prompt += f"STUDY MATERIAL CONTEXT:\n{material_context[:2000]}\n\n"
        
        if current_event_info:
            full_prompt += current_event_info + "\n"
        
        if is_christian_topic:
            full_prompt += "The user is asking about Christian/Biblical topics. Respond with warmth and Scripture references using clear headers.\n\n"
        
        full_prompt += f"User: {user_message}\nAssistant:"
        
        response = model.generate_content(full_prompt)
        result = response.text
        return result
        
    except Exception as e:
        if is_christian_topic:
            return "I'm experiencing a technical issue. Please share a specific verse you'd like to discuss, or feel free to rephrase your question."
        return f"I'm here to help, but I encountered a technical issue. (Error: {str(e)})"