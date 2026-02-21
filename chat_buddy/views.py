from django.shortcuts import render, redirect
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth import authenticate, login as auth_login, logout as auth_logout
from django.contrib.auth.models import User
from rest_framework import status
from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework.parsers import MultiPartParser, FormParser
from rest_framework.views import APIView
from .models import StudyMaterial, ChatSession, ChatMessage
from .ai_service import summarize_pdf, summarize_image, summarize_document, ask_buddy
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.authtoken.models import Token
import os
import json
import PyPDF2

def landing_view(request):
    """Render the landing page with user context"""
    context = {
        'user': request.user,
        'is_authenticated': request.user.is_authenticated
    }
    return render(request, 'landing.html', context)

@login_required(login_url='login')
def chat_view(request):
    """Render chat page with user context"""
    context = {
        'user': request.user,
        'is_authenticated': request.user.is_authenticated
    }
    return render(request, 'chat.html', context)

def login_view(request):
    """Handle login page - GET to display form, POST to authenticate"""
    if request.user.is_authenticated:
        return redirect('chat')
    
    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')
        
        # Try to authenticate with username first
        user = authenticate(request, username=username, password=password)
        
        # If that fails, try with email as username
        if not user:
            try:
                user_obj = User.objects.get(email=username)
                user = authenticate(request, username=user_obj.username, password=password)
            except User.DoesNotExist:
                user = None
        
        if user is not None:
            auth_login(request, user)
            messages.success(request, f'Welcome back, {user.first_name or user.username}!')
            return redirect('chat')
        else:
            messages.error(request, 'Invalid username/email or password.')
    
    return render(request, 'login.html')

def signup_view(request):
    """Handle signup page - GET to display form, POST to create user"""
    if request.user.is_authenticated:
        return redirect('chat')
    
    if request.method == 'POST':
        username = request.POST.get('username')
        email = request.POST.get('email')
        password = request.POST.get('password')
        password_confirm = request.POST.get('password_confirm')
        
        # Validation
        if not all([username, email, password, password_confirm]):
            messages.error(request, 'Please fill in all fields.')
        elif password != password_confirm:
            messages.error(request, 'Passwords do not match.')
        elif len(password) < 6:
            messages.error(request, 'Password must be at least 6 characters long.')
        elif User.objects.filter(username=username).exists():
            messages.error(request, 'Username already exists.')
        elif User.objects.filter(email=email).exists():
            messages.error(request, 'Email already registered.')
        else:
            # Create user
            user = User.objects.create_user(username=username, email=email, password=password)
            auth_login(request, user)
            messages.success(request, 'Account created successfully! Welcome to LearnBuddy.')
            return redirect('chat')
    
    return render(request, 'signup.html')

def logout_view(request):
    """Handle logout"""
    auth_logout(request)
    messages.success(request, 'You have been logged out.')
    return redirect('landing')

# API Endpoints for token-based authentication (for mobile/external clients)
@api_view(['POST'])
@permission_classes([AllowAny])
def register_api(request):
    """API endpoint to register a user and get authentication token"""
    username = request.data.get('username')
    email = request.data.get('email')
    password = request.data.get('password')

    if not username or not password or not email:
        return Response({'error': 'Please provide all fields'}, status=status.HTTP_400_BAD_REQUEST)

    if User.objects.filter(username=username).exists():
        return Response({'error': 'Username already exists'}, status=status.HTTP_400_BAD_REQUEST)

    if User.objects.filter(email=email).exists():
        return Response({'error': 'Email already registered'}, status=status.HTTP_400_BAD_REQUEST)

    user = User.objects.create_user(username=username, email=email, password=password)
    token, created = Token.objects.get_or_create(user=user)
    
    return Response({
        'token': token.key,
        'user_id': user.pk,
        'username': user.username
    }, status=status.HTTP_201_CREATED)

@api_view(['POST'])
@permission_classes([AllowAny])
def login_api(request):
    """API endpoint to login a user and get authentication token"""
    username = request.data.get('username')
    password = request.data.get('password')

    user = authenticate(username=username, password=password)

    if user:
        token, created = Token.objects.get_or_create(user=user)
        return Response({
            'token': token.key,
            'username': user.username
        }, status=status.HTTP_200_OK)
    
    return Response({'error': 'Invalid Credentials'}, status=status.HTTP_401_UNAUTHORIZED)


@api_view(['GET'])
def get_chat_history(request):
    """Fetch all chat sessions with their messages for the current user"""
    try:
        # Require authentication
        if not request.user.is_authenticated:
            return JsonResponse({'error': 'Not authenticated'}, status=401)
        
        # Get ONLY current user's chat sessions ordered by creation date (newest first)
        sessions = ChatSession.objects.filter(user=request.user).order_by('-created_at')
        
        chat_data = []
        for session in sessions:
            messages = session.messages.all().order_by('created_at')
            chat_data.append({
                'session_id': session.id,
                'created_at': session.created_at.isoformat(),
                'material': session.study_material.file.name if session.study_material else None,
                'messages': [
                    {
                        'type': msg.role,
                        'text': msg.content
                    }
                    for msg in messages
                ]
            })
        
        return JsonResponse({
            'sessions': chat_data
        })
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


@api_view(['POST'])
@permission_classes([AllowAny])
def register_view(request):
    username = request.data.get('username')
    email = request.data.get('email')
    password = request.data.get('password')

    if not username or not password or not email:
        return Response({'error': 'Please provide all fields'}, status=status.HTTP_400_BAD_REQUEST)

    if User.objects.filter(username=username).exists():
        return Response({'error': 'Username already exists'}, status=status.HTTP_400_BAD_REQUEST)

    user = User.objects.create_user(username=username, email=email, password=password)
    token, created = Token.objects.get_or_create(user=user)
    
    return Response({
        'token': token.key,
        'user_id': user.pk,
        'username': user.username
    }, status=status.HTTP_201_CREATED)

@method_decorator(csrf_exempt, name='dispatch')
class PDFUploadView(APIView):
    parser_classes = (MultiPartParser, FormParser)
    
    def post(self, request, *args, **kwargs):
        try:
            pdf_file = request.FILES.get('pdf')
            
            if not pdf_file:
                return Response({'error': 'No PDF file provided'}, 
                              status=status.HTTP_400_BAD_REQUEST)
            
            if not pdf_file.name.lower().endswith('.pdf'):
                return Response({'error': 'File must be a PDF'}, 
                              status=status.HTTP_400_BAD_REQUEST)
            
            # Handle both in-memory and temporary files
            if hasattr(pdf_file, 'temporary_file_path'):
                pdf_path = pdf_file.temporary_file_path()
            else:
                # For in-memory files, save temporarily
                import tempfile
                with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as tmp:
                    for chunk in pdf_file.chunks():
                        tmp.write(chunk)
                    pdf_path = tmp.name
            
            try:
                # Extract page count
                page_count = 0
                try:
                    with open(pdf_path, 'rb') as f:
                        pdf_reader = PyPDF2.PdfReader(f)
                        page_count = len(pdf_reader.pages)
                except:
                    page_count = "Unknown"
                
                # Get AI summary using Gemini
                summary_response = summarize_pdf(pdf_path)
                
                # Parse the summary to extract key topics
                key_topics = []
                try:
                    # Try to extract topics from summary
                    if "topics:" in summary_response.lower():
                        topics_section = summary_response.lower().split("topics:")[1].split("\n")[0]
                        key_topics = [t.strip() for t in topics_section.split(",")][:5]
                    else:
                        # Generate basic topics from first few words
                        words = summary_response.split()[:10]
                        key_topics = [w for w in words if len(w) > 5][:3]
                except:
                    key_topics = ["Study Material", "Educational Content"]
                
                # Save to database
                study_material = StudyMaterial.objects.create(
                    file=pdf_file,
                    file_type='pdf',
                    summary=summary_response
                )
                
                return Response({
                    'id': study_material.id,
                    'filename': pdf_file.name,
                    'pages': page_count,
                    'summary': summary_response,
                    'key_topics': key_topics,
                    'uploaded_at': study_material.uploaded_at.isoformat()
                }, status=status.HTTP_201_CREATED)
                
            finally:
                # Clean up temp file if we created one
                if not hasattr(pdf_file, 'temporary_file_path'):
                    try:
                        os.unlink(pdf_path)
                    except:
                        pass
            
        except Exception as e:
            return Response({
                'error': f'Failed to process PDF: {str(e)}',
                'details': 'Please ensure the PDF is not corrupted and try again.'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@method_decorator(csrf_exempt, name='dispatch')
class ImageUploadView(APIView):
    parser_classes = (MultiPartParser, FormParser)
    
    def post(self, request, *args, **kwargs):
        try:
            image_file = request.FILES.get('image')
            
            if not image_file:
                return Response({'error': 'No image file provided'}, 
                              status=status.HTTP_400_BAD_REQUEST)
            
            # Check if file is an image
            allowed_extensions = ['.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp']
            if not any(image_file.name.lower().endswith(ext) for ext in allowed_extensions):
                return Response({'error': 'File must be an image (JPG, PNG, GIF, BMP, WebP)'}, 
                              status=status.HTTP_400_BAD_REQUEST)
            
            # Handle both in-memory and temporary files
            if hasattr(image_file, 'temporary_file_path'):
                image_path = image_file.temporary_file_path()
            else:
                # For in-memory files, save temporarily
                import tempfile
                with tempfile.NamedTemporaryFile(delete=False, suffix='.png') as tmp:
                    for chunk in image_file.chunks():
                        tmp.write(chunk)
                    image_path = tmp.name
            
            try:
                # Get AI summary using image OCR
                summary_response = summarize_image(image_path)
                
                # Parse the summary to extract key topics
                key_topics = []
                try:
                    words = summary_response.split()[:10]
                    key_topics = [w for w in words if len(w) > 5][:3]
                except:
                    key_topics = ["Image Content", "Extracted Text"]
                
                # Save to database
                study_material = StudyMaterial.objects.create(
                    file=image_file,
                    file_type='image',
                    summary=summary_response
                )
                
                return Response({
                    'id': study_material.id,
                    'filename': image_file.name,
                    'summary': summary_response,
                    'key_topics': key_topics,
                    'uploaded_at': study_material.uploaded_at.isoformat()
                }, status=status.HTTP_201_CREATED)
                
            finally:
                # Clean up temp file if we created one
                if not hasattr(image_file, 'temporary_file_path'):
                    try:
                        os.unlink(image_path)
                    except:
                        pass
            
        except Exception as e:
            return Response({
                'error': f'Failed to process image: {str(e)}',
                'details': 'Please ensure the image is valid and try again.'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
def chat_api(request):
    try:
        # SECURITY: Require authentication
        if not request.user.is_authenticated:
            return JsonResponse({'error': 'Not authenticated'}, status=401)
        
        # Get data from request
        user_message = request.data.get('message', '').strip()
        session_id = request.data.get('session_id')
        
        if not user_message:
            return JsonResponse({'error': 'Message is required'}, status=400)
        
        # Check for Christian/Biblical content
        christian_keywords = ['god', 'jesus', 'christ', 'bible', 'scripture', 'prayer', 
                            'faith', 'christian', 'church', 'lord', 'salvation', 
                            'gospel', 'holy spirit', 'worship']
        is_christian_topic = any(keyword in user_message.lower() for keyword in christian_keywords)
        
        # Check for inappropriate content
        inappropriate_keywords = ['sex', 'porn', 'explicit', 'nsfw', 'nude']
        is_inappropriate = any(keyword in user_message.lower() for keyword in inappropriate_keywords)
        
        # Get or create chat session
        session = None
        material = None
        material_context = None
        
        if session_id:
            try:
                session = ChatSession.objects.get(id=session_id, user=request.user)
                if session.study_material:
                    material = session.study_material
                    material_context = f"Document Context ({material.file.name}):\n{material.summary}"
            except ChatSession.DoesNotExist:
                # Create new session if not found (only for current user)
                session = ChatSession.objects.create(user=request.user)
        else:
            # Create new session associated with current user
            session = ChatSession.objects.create(user=request.user)
        
        # Build system context for AI
        system_context = """You are LearnBuddy, a friendly and helpful AI study assistant with EXPERT-LEVEL mathematics expertise. Your personality:

1. CHRISTIAN TOPICS: You are VERY engaged, encouraging, and knowledgeable about Biblical topics. 
   - Provide Scripture references when relevant
   - Encourage spiritual growth and Bible study
   - Be warm and uplifting in discussing faith matters
   - Quote relevant Bible verses to support your explanations
   
2. EDUCATIONAL CONTENT: You help students understand study materials deeply
   - Break down complex topics into simple explanations
   - Provide examples and analogies
   - Ask clarifying questions to ensure understanding
   - Be patient and supportive
   
3. MATHEMATICAL TOPICS: You are a MATHEMATICS GENIUS who helps students master math.
   
   CORE MATHEMATICS INSTRUCTIONS:
   - Solve problems step-by-step with crystal clear explanations
   - Use proper mathematical terminology (not LaTeX symbols)
   - Never use raw symbols like $ or fractions like \frac{}{} - convert to readable formats
   - Example: Instead of "x = \frac{12}{3}" write "x = 12 divided by 3 = 4"
   - Example: Instead of "$x^2 + 5x + 6$" write "x squared plus 5x plus 6"
   
   FORMATTING FOR MATH:
   - Use words for mathematical operations: "divided by", "times", "plus", "minus", "equals"
   - Use "^" for exponents: "x^2 means x squared"
   - Use "/" for fractions: "12/3 = 4" (read as "12 divided by 3 equals 4")
   - Use special symbols when available: ≈ (approximately), ≠ (not equal), ≤ (less than or equal)
   - Break equations into digestible parts with explanations between steps
   
   SOLVING PROBLEMS:
   - Always show work step-by-step
   - Label each step clearly: "Step 1:", "Step 2:", etc.
   - Explain WHY you're doing each operation
   - Highlight the final answer clearly
   - Simplify to lowest terms and simplest form
   - Show alternative methods when useful
   
   TONE FOR MATH:
   - Make the student feel confident and capable
   - Celebrate small victories in the problem
   - Use encouraging language: "Great question!", "Let's break this down!", "You've got this!"
   - Make complex math feel simple and achievable
   - Help user feel like a mathematics genius when solving with you
   
4. INAPPROPRIATE CONTENT: Politely redirect to educational topics
   - Stay professional and respectful
   - Guide conversation back to learning
   
5. GENERAL TONE: Friendly, encouraging, and helpful with emojis for warmth"""

        if is_inappropriate:
            response_text = "I'm designed to be a study assistant focused on educational content. I'd be happy to help you with academic materials, study questions, or discussions about faith and biblical principles. What can I help you learn about today?"
        else:
            # Build conversation history from database
            conversation_history = []
            db_messages = session.messages.order_by('created_at')[:20]  # Last 20 messages
            
            for msg in db_messages:
                conversation_history.append({
                    "role": msg.role if msg.role in ['user', 'assistant'] else 'user',
                    "parts": [msg.content],
                    "text": msg.content
                })
            
            # Add enhanced context for Christian topics
            if is_christian_topic:
                system_context += "\n\nNOTE: This is a question about Christian faith. Provide a warm, biblically-grounded response with Scripture references."
            
            # Get AI response
            try:
                response_text = ask_buddy(
                    user_message,
                    conversation_history=conversation_history,
                    material_context=material_context,
                    system_context=system_context,
                    is_christian_topic=is_christian_topic
                )
            except Exception as e:
                # Fallback response if AI service fails
                if is_christian_topic:
                    response_text = "That's a wonderful question about faith! While I'm having trouble accessing my full knowledge right now, I'd encourage you to explore the Scriptures directly. The Bible says in James 1:5, 'If any of you lacks wisdom, you should ask God, who gives generously to all without finding fault, and it will be given to you.' Could you rephrase your question, or would you like to discuss a specific Bible passage?"
                elif material_context:
                    response_text = "I understand you're asking about the material you uploaded. I'm having a brief technical issue, but I'm here to help! Could you please rephrase your question or be more specific about which section you'd like me to explain?"
                else:
                    response_text = "I'm experiencing a brief technical difficulty. Please try rephrasing your question, or if you have study materials, upload them so I can provide more specific help!"
        
        # Save messages to database
        ChatMessage.objects.create(
            session=session,
            role='user',
            content=user_message
        )
        
        ChatMessage.objects.create(
            session=session,
            role='assistant',
            content=response_text
        )
        
        return JsonResponse({
            'response': response_text,
            'session_id': session.id,  # Send back to frontend
            'timestamp': str(session.created_at)
        })
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        return JsonResponse({
            'error': 'An error occurred processing your message',
            'details': str(e)
        }, status=500)


# Unified file upload and summarization endpoint
@method_decorator(csrf_exempt, name='dispatch')
class FileUploadView(APIView):
    parser_classes = (MultiPartParser, FormParser)
    
    def post(self, request, *args, **kwargs):
        try:
            # SECURITY: Require authentication
            if not request.user.is_authenticated:
                return Response({'error': 'Not authenticated'}, status=status.HTTP_401_UNAUTHORIZED)
            
            uploaded_file = request.FILES.get('file')
            
            if not uploaded_file:
                return Response({'error': 'No file provided'}, 
                              status=status.HTTP_400_BAD_REQUEST)
            
            filename = uploaded_file.name.lower()
            file_type = 'unknown'
            summary = ""
            
            # Determine file type
            if filename.endswith('.pdf'):
                file_type = 'pdf'
            elif filename.endswith(('.jpg', '.jpeg')):
                file_type = 'image'
            elif filename.endswith('.png'):
                file_type = 'image'
            elif filename.endswith('.gif'):
                file_type = 'image'
            elif filename.endswith(('.doc', '.docx')):
                file_type = 'document'
            else:
                return Response({'error': 'File type not supported. Please use PDF, images (JPG, JPEG, PNG, GIF), or documents (DOC, DOCX)'}, 
                              status=status.HTTP_400_BAD_REQUEST)
            
            # Save file temporarily and process
            import tempfile
            temp_path = None
            
            try:
                # Create temp file
                if file_type == 'pdf':
                    suffix = '.pdf'
                elif file_type == 'image':
                    suffix = filename[filename.rfind('.'):]
                elif file_type == 'document':
                    suffix = filename[filename.rfind('.'):]
                else:
                    suffix = ''
                
                with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
                    for chunk in uploaded_file.chunks():
                        tmp.write(chunk)
                    temp_path = tmp.name
                
                # Process based on file type
                if file_type == 'pdf':
                    summary = summarize_pdf(temp_path)
                elif file_type == 'image':
                    summary = summarize_image(temp_path)
                else:  # document (Word documents)
                    summary = summarize_document(temp_path)
                
                # Save to database (associate with current user)
                study_material = StudyMaterial.objects.create(
                    user=request.user,
                    file=uploaded_file,
                    file_type=file_type,
                    summary=summary
                )
                
                return Response({
                    'id': study_material.id,
                    'filename': uploaded_file.name,
                    'file_type': file_type,
                    'summary': summary,
                    'uploaded_at': study_material.uploaded_at
                }, status=status.HTTP_201_CREATED)
                
            finally:
                # Clean up temp file
                if temp_path and os.path.exists(temp_path):
                    try:
                        os.unlink(temp_path)
                    except:
                        pass
            
        except Exception as e:
            import traceback
            traceback.print_exc()
            return Response({'error': f'Failed to process file: {str(e)}'}, 
                          status=status.HTTP_500_INTERNAL_SERVER_ERROR)