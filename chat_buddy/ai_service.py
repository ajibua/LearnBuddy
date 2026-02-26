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

# Configure Tesseract path for Windows (optional - only if available)
# Tesseract is no longer required - Gemini vision API is the primary method
try:
    # Try to find tesseract on system PATH first
    pytesseract.pytesseract.pytesseract_cmd = 'tesseract'
except:
    # If not in PATH, try the common Windows installation location
    try:
        pytesseract.pytesseract.pytesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'
    except:
        # Tesseract is optional - Gemini vision will be used instead
        print("Note: Tesseract not found. Gemini Vision API will be used for image/image-PDF processing.")

# Initialize Google Generative AI with proper error handling
google_api_key = getattr(settings, 'GOOGLE_API_KEY', None) or os.getenv('GOOGLE_API_KEY')
if not google_api_key:
    raise ValueError("GOOGLE_API_KEY is not set. Please add it to your .env file or Django settings.")

genai.configure(api_key=google_api_key)
model = genai.GenerativeModel('gemini-2.5-flash')

def extract_text_from_pdf(pdf_path):
    """Extract text content from PDF file with fallback to Gemini vision for image-based PDFs"""
    text = ""
    try:
        # First try normal PDF text extraction (fast, for text-based PDFs)
        with open(pdf_path, 'rb') as file:
            pdf_reader = PyPDF2.PdfReader(file)
            for page in pdf_reader.pages:
                extracted = page.extract_text()
                if extracted:
                    text += extracted + "\n"
        
        # If text extracted successfully, return it
        if text.strip():
            return text
        
        # If no text was extracted, it's likely an image-based PDF - use Gemini vision
        print("Text-based extraction failed, attempting Gemini vision analysis on PDF pages...")
        text = extract_text_from_pdf_with_gemini_vision(pdf_path)
            
    except Exception as e:
        # If normal extraction fails, try Gemini vision
        print(f"PyPDF2 extraction error, falling back to Gemini vision: {str(e)}")
        try:
            text = extract_text_from_pdf_with_gemini_vision(pdf_path)
        except Exception as e2:
            raise Exception(f"Failed to extract PDF text: {str(e2)}")
    
    return text if text.strip() else "Unable to extract text from this PDF."


def extract_text_from_pdf_with_gemini_vision(pdf_path):
    """
    Extract text from image-based PDFs (including scanned / handwritten pages)
    using Gemini's vision API.
    Speed optimisations:
    - 200 DPI (sharp enough for Gemini, ~44% smaller than 300 DPI)
    - Images resized to max 1 600 px wide before encoding
    - JPEG encoding (5-10× smaller than PNG)
    - All pages processed IN PARALLEL via ThreadPoolExecutor
    Quality:
    - PIL contrast + sharpness enhancement before sending
    - Gemini prompt explicitly ignores scanner watermarks (CamScanner, etc.)
    """
    import base64
    from PIL import ImageEnhance
    from concurrent.futures import ThreadPoolExecutor, as_completed

    poppler_path = r'C:\Users\HomePC\Downloads\poppler\poppler-25.12.0\Library\bin'

    try:
        try:
            if os.path.exists(poppler_path):
                images = convert_from_path(
                    pdf_path, first_page=1, last_page=20,
                    dpi=200, poppler_path=poppler_path
                )
            else:
                images = convert_from_path(pdf_path, first_page=1, last_page=20, dpi=200)
        except Exception as e:
            print(f"Poppler path failed, trying system poppler: {e}")
            images = convert_from_path(pdf_path, first_page=1, last_page=20, dpi=200)

    except Exception as e:
        raise Exception(f"Failed to convert PDF pages to images: {str(e)}")

    PAGE_PROMPT = (
        "You are reading a scanned document page.\n"
        "Your task: extract ONLY the actual document content — "
        "handwritten notes, printed text, diagrams, tables, equations, "
        "and any legible writing made by the document author.\n\n"
        "IMPORTANT RULES:\n"
        "1. IGNORE all scanner / app watermarks, logos, and branding. "
        "This includes 'CamScanner', 'Adobe Scan', 'Microsoft Lens', "
        "'Genius Scan', any app name, website URL, or promotional text "
        "added by a scanning app — do NOT transcribe these.\n"
        "2. If the page contains handwriting, transcribe it faithfully, "
        "preserving line breaks, numbering, and structure.\n"
        "3. If text is partially illegible, give your best reading and "
        "mark uncertain words with [?].\n"
        "4. Preserve the original layout: headings, bullet points, "
        "numbered lists, tables, and paragraph breaks.\n"
        "5. Return ONLY the transcribed text — no commentary or explanations."
    )

    def process_page(args):
        """Preprocess one page image and call Gemini. Returns (idx, text)."""
        idx, img = args
        tmp_path = None
        try:
            # Preprocess
            img = img.convert('RGB')
            img = ImageEnhance.Contrast(img).enhance(1.8)
            img = ImageEnhance.Sharpness(img).enhance(2.0)

            # Resize to max 1600px wide to reduce payload size
            max_width = 1600
            if img.width > max_width:
                ratio = max_width / img.width
                img = img.resize(
                    (max_width, int(img.height * ratio)),
                    resample=Image.LANCZOS
                )

            # Save as JPEG (much smaller than PNG)
            with tempfile.NamedTemporaryFile(delete=False, suffix='.jpg') as tmp:
                img.save(tmp, format='JPEG', quality=90, optimize=True)
                tmp_path = tmp.name

            with open(tmp_path, 'rb') as f:
                img_data = base64.standard_b64encode(f.read()).decode('utf-8')

            response = model.generate_content([
                PAGE_PROMPT,
                {"mime_type": "image/jpeg", "data": img_data}
            ])

            page_text = response.text.strip() if response.text else ""
            return (idx, page_text)

        except Exception as e:
            print(f"Error processing page {idx + 1} with Gemini: {e}")
            return (idx, "")
        finally:
            if tmp_path and os.path.exists(tmp_path):
                os.unlink(tmp_path)

    # Process all pages IN PARALLEL (up to 5 concurrent Gemini calls)
    results = {}
    with ThreadPoolExecutor(max_workers=5) as executor:
        futures = {executor.submit(process_page, (idx, img)): idx
                   for idx, img in enumerate(images)}
        for future in as_completed(futures):
            idx, page_text = future.result()
            if page_text:
                results[idx] = page_text

    # Reassemble in original page order
    full_text = "\n\n".join(results[i] for i in sorted(results))
    return full_text if full_text.strip() else "No readable text found in this PDF."


def is_tesseract_available():
    """Check if tesseract is installed and available"""
    try:
        pytesseract.get_tesseract_version()
        return True
    except:
        return False


def extract_text_from_pdf_with_ocr(pdf_path):
    """DEPRECATED: Use extract_text_from_pdf_with_gemini_vision instead"""
    return extract_text_from_pdf_with_gemini_vision(pdf_path)


def extract_text_from_image(image_path):
    """Extract text from image using Gemini's vision API (primary) or OCR fallback"""
    try:
        # Primary method: Use Gemini's vision API for reliable text extraction
        with open(image_path, 'rb') as f:
            import base64
            img_data = base64.standard_b64encode(f.read()).decode("utf-8")
        
        # Determine image type
        image_type = "image/jpeg"
        if image_path.lower().endswith('.png'):
            image_type = "image/png"
        elif image_path.lower().endswith('.gif'):
            image_type = "image/gif"
        elif image_path.lower().endswith('.webp'):
            image_type = "image/webp"
        
        response = model.generate_content([
            (
                "You are reading a scanned or photographed document/image.\n"
                "Your task: extract ONLY the actual content created by the document author — "
                "handwritten text, printed text, diagrams, tables, equations, labels, and captions.\n\n"
                "IMPORTANT RULES:\n"
                "1. IGNORE all scanner / app watermarks, logos, and branding. "
                "This includes 'CamScanner', 'Adobe Scan', 'Microsoft Lens', "
                "any app name, website URL, or promotional overlay added by a scanning app.\n"
                "2. Transcribe handwriting faithfully, preserving the original line breaks and structure.\n"
                "3. If text is partially illegible, give your best reading and mark uncertain words with [?].\n"
                "4. If it contains a diagram or chart, describe its structure and all labelled values.\n"
                "5. Return only the transcribed content — no commentary or explanations."
            ),
            {
                "mime_type": image_type,
                "data": img_data,
            }
        ])
        
        if response.text.strip():
            return response.text
        else:
            return "No readable text found in this image."
            
    except Exception as e:
        print(f"Gemini vision failed: {e}")
        # Fallback to Tesseract if available
        try:
            if is_tesseract_available():
                image = Image.open(image_path)
                text = pytesseract.image_to_string(image)
                if text.strip():
                    return text
        except Exception as ocr_error:
            print(f"OCR fallback also failed: {ocr_error}")
        
        return "Unable to extract text from this image. Try asking questions about it and I'll help analyze it!"


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


def summarize_pdf(pdf_path, user_instruction=None):
    """
    Summarize PDF content with structured formatting using Google Gemini
    """
    try:
        pdf_text = extract_text_from_pdf(pdf_path)
        
        if not pdf_text.strip():
            return "Unable to extract text from this PDF. The document may be image-based or encrypted."
        
        # Limit text length for API context window
        pdf_text = pdf_text[:15000]
        
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

        if user_instruction:
            prompt += f"\n\n**User's specific request:** {user_instruction}\nMake sure to address this specific request directly in your response."

        response = model.generate_content(prompt)
        result = response.text
        print(f"Successfully summarized PDF using Google Gemini 2.5 Flash")
        return result
        
    except Exception as e:
        return f"I processed the PDF, but encountered an issue generating a detailed summary. Error: {str(e)}"


def summarize_image(image_path, user_instruction=None):
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

        if user_instruction:
            prompt += f"\n\n**User's specific request:** {user_instruction}\nMake sure to address this specific request directly in your response."

        response = model.generate_content(prompt)
        result = response.text
        print(f"Successfully analyzed image using Google Gemini 2.5 Flash")
        return result
        
    except Exception as e:
        return f"I processed the image, but encountered an issue generating a summary. Error: {str(e)}"


def summarize_document(doc_path, user_instruction=None):
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

        if user_instruction:
            prompt += f"\n\n**User's specific request:** {user_instruction}\nMake sure to address this specific request directly in your response."

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
                # Try to get reference information (Wikipedia for general knowledge)
                search_results = search_web(user_message, max_results=3)
                if search_results and search_results.get('knowledge'):
                    current_event_info = format_search_results_for_ai(search_results)
                    print(f"Found reference information for: {user_message}")
            except Exception as e:
                # Don't break the chat if search fails - just continue without it
                print(f"Web search error (non-blocking): {e}")
        
        # Build conversation context
        conversation_text = ""
        if conversation_history:
            for msg in conversation_history[-12:]:  # Last 12 messages for rich context
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
                    conversation_text += f"{role}: {str(content)[:1000]}\n\n"
        
        # Build full prompt
        full_prompt = system_message + "\n\n"
        
        if conversation_text:
            full_prompt += "Previous conversation:\n" + conversation_text + "\n"
        
        if material_context:
            full_prompt += f"STUDY MATERIAL CONTEXT:\n{material_context[:4000]}\n\n"
        
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