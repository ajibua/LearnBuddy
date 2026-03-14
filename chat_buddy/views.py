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
from .ai_service import generate_session_title as _generate_title
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
def get_current_user(request):
    """API endpoint to get current logged-in user's information"""
    if not request.user.is_authenticated:
        return JsonResponse({'error': 'Not authenticated'}, status=401)
    
    return JsonResponse({
        'user_id': request.user.pk,
        'username': request.user.username,
        'first_name': request.user.first_name or request.user.username,
        'email': request.user.email,
        'is_authenticated': True
    })


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
                'title': session.title or '',
                'created_at': session.created_at.isoformat(),
                'material': session.study_material.file.name if session.study_material else None,
                'material_url': session.study_material.file.url if session.study_material else None,
                'material_type': session.study_material.file_type if session.study_material else None,
                'messages': [
                    {
                        'id': msg.id,
                        'type': msg.role,
                        'text': msg.content,
                        'feedback': msg.feedback,
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

0. GREETINGS & CASUAL MESSAGES: Always respond warmly to greetings like "hi", "hey", "hello", "heyy", "hii", "sup", "yo", etc.
   - Reply with a friendly greeting and briefly introduce yourself as LearnBuddy.
   - Invite the user to ask a question or share what they'd like to learn.
   - Example: "Hey there! 👋 I'm LearnBuddy, your AI study companion. What would you like to learn or explore today?"

1. RELIGIOUS TOPICS: Warm, knowledgeable, and encouraging for any faith tradition.
   - Provide Scripture references for Christian topics
   - Be respectful and thoughtful across all religions
   - Quote relevant texts to support explanations

2. EDUCATIONAL CONTENT: Help students understand study materials deeply.
   - Break down complex topics into simple explanations
   - Provide examples and analogies
   - Be patient and supportive

3. MATHEMATICS & STEM: You are a GENIUS across ALL STEM fields. General rules:
   - Always reason step-by-step before giving the final answer.
   - If a SYMPY / SCIPY / CHEMPY VERIFIED RESULT is provided, use that exact value.

   MATHEMATICS (Algebra, Calculus, ODEs, Linear Algebra, etc.):
   - Use LaTeX notation exclusively — never write math in plain words.
   - Inline expressions: wrap with $...$ e.g. $x^2 + 5x + 6$
   - Display / block equations: wrap with $$...$$ on its own line.
   - Use full LaTeX: \\frac{a}{b}, \\int_{a}^{b} f(x)\\,dx, \\sum_{n=0}^{\\infty}, \\sqrt{x}, \\lim_{x \\to 0}
   - Greek letters: \\alpha, \\beta, \\pi, \\theta, \\Delta, \\Sigma, etc.
   - NEVER write "integral from a to b" — write $$\\int_a^b f(x)\\,dx$$ instead.
   - Show step-by-step solutions with each step clearly labelled and wrapped in LaTeX.

   PHYSICS & ENGINEERING (Mechanics, Thermodynamics, Electromagnetism, Circuits, etc.):
   - Always state the formula used before substituting values.
   - Include units in every step and the final answer.
   - Use LaTeX for equations, e.g. $F = ma$, $V = IR$.
   - Show clearly: Given → Formula → Substitution → Answer with units.

   CHEMISTRY (Stoichiometry, Equilibrium, Thermochemistry, Organic, etc.):
   - Balance chemical equations before solving.
   - Show molar masses, mole calculations, and conversions step by step.
   - For equilibrium: write the ICE table explicitly.
   - For pH: show Ka/Kb expressions and the quadratic/approximation approach.
   - Use standard chemical notation (subscripts, arrows → and ⇌).

   BIOLOGY (Genetics, Ecology, Physiology, Bioinformatics, etc.):
   - Use Punnett squares for genetics problems.
   - Show Hardy-Weinberg calculations step by step.
   - Use standard biological notation (alleles, gene symbols).

4. INAPPROPRIATE CONTENT: Politely redirect to educational topics.

5. GENERAL TONE: Friendly, encouraging, and helpful. ALWAYS produce a non-empty reply."""

        if is_inappropriate:
            response_text = "I'm designed to be a study assistant focused on educational content. I'd be happy to help you with academic materials, study questions, or discussions about faith and biblical principles. What can I help you learn about today?"
        else:
            # Build conversation history from database
            conversation_history = []
            db_messages = session.messages.order_by('created_at')[:30]  # Last 30 messages
            
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
                    is_religion_topic=is_christian_topic
                )
                # Guard against empty/None responses from the AI
                if not response_text or not response_text.strip():
                    response_text = "Hey there! 👋 I'm LearnBuddy, your AI study companion. Feel free to ask me anything — a subject, a problem, or just say what's on your mind!"
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
        
        assistant_msg = ChatMessage.objects.create(
            session=session,
            role='assistant',
            content=response_text
        )

        # Generate title after the very first exchange
        session_title = session.title or ''
        if not session_title:
            msg_count = session.messages.count()  # now includes the two we just saved
            if msg_count <= 2:
                generated = _generate_title(user_message, response_text)
                if generated:
                    session.title = generated
                    session.save(update_fields=['title'])
                    session_title = generated
        
        return JsonResponse({
            'response': response_text,
            'message_id': assistant_msg.id,
            'session_id': session.id,
            'session_title': session_title,
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
            elif filename.endswith(('.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp')):
                file_type = 'image'
            elif filename.endswith(('.docx', '.txt')):
                file_type = 'document'
            else:
                return Response({'error': 'File type not supported. Please use PDF, images (JPG, PNG, GIF, BMP, WebP), DOCX, or TXT.'}, 
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
                user_message = request.data.get('user_message', '').strip()
                if file_type == 'pdf':
                    summary = summarize_pdf(temp_path, user_instruction=user_message)
                elif file_type == 'image':
                    summary = summarize_image(temp_path, user_instruction=user_message)
                else:  # document (Word documents)
                    summary = summarize_document(temp_path, user_instruction=user_message)
                
                # Save to database (associate with current user)
                study_material = StudyMaterial.objects.create(
                    user=request.user,
                    file=uploaded_file,
                    file_type=file_type,
                    summary=summary
                )

                # Link material to the current chat session so follow-up questions
                # can reference it.  Accept an optional session_id from the frontend.
                session_id = request.data.get('session_id')
                session = None
                if session_id:
                    try:
                        session = ChatSession.objects.get(id=session_id, user=request.user)
                        session.study_material = study_material
                        session.save()
                    except (ChatSession.DoesNotExist, ValueError):
                        session = None

                # No active session yet - create one bound to this material
                if not session:
                    session = ChatSession.objects.create(
                        user=request.user,
                        study_material=study_material
                    )

                # Store the user's upload message so it appears in conversation history.
                user_bubble = f"Attached: {uploaded_file.name}"
                if user_message:
                    user_bubble += f"\n\n{user_message}"
                ChatMessage.objects.create(
                    session=session,
                    role='user',
                    content=user_bubble
                )

                # Store the upload event as an assistant message so it appears in
                # conversation history for future turns.
                ChatMessage.objects.create(
                    session=session,
                    role='assistant',
                    content=f"[Uploaded file: {uploaded_file.name}]\n\nSummary:\n{summary}"
                )

                return Response({
                    'id': study_material.id,
                    'filename': uploaded_file.name,
                    'file_type': file_type,
                    'file_url': study_material.file.url,
                    'summary': summary,
                    'uploaded_at': study_material.uploaded_at,
                    'session_id': session.id,
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


@api_view(['POST'])
def feedback_api(request, message_id):
    """Save thumbs-up / thumbs-down feedback on an assistant message."""
    if not request.user.is_authenticated:
        return JsonResponse({'error': 'Not authenticated'}, status=401)

    value = request.data.get('feedback')  # 'up' or 'down'
    if value not in ('up', 'down'):
        return JsonResponse({'error': 'Invalid feedback value'}, status=400)

    try:
        msg = ChatMessage.objects.get(id=message_id, session__user=request.user, role='assistant')
        msg.feedback = value
        msg.save(update_fields=['feedback'])
        return JsonResponse({'status': 'ok', 'feedback': value})
    except ChatMessage.DoesNotExist:
        return JsonResponse({'error': 'Message not found'}, status=404)


@api_view(['POST'])
def regenerate_api(request):
    """Delete the last assistant message and re-generate a fresh response."""
    if not request.user.is_authenticated:
        return JsonResponse({'error': 'Not authenticated'}, status=401)

    session_id = request.data.get('session_id')
    if not session_id:
        return JsonResponse({'error': 'session_id required'}, status=400)

    try:
        session = ChatSession.objects.get(id=session_id, user=request.user)
    except ChatSession.DoesNotExist:
        return JsonResponse({'error': 'Session not found'}, status=404)

    # Find and delete the last assistant message
    last_assistant = session.messages.filter(role='assistant').last()
    if last_assistant:
        last_assistant.delete()

    # Find the last user message to replay
    last_user = session.messages.filter(role='user').last()
    if not last_user:
        return JsonResponse({'error': 'No user message to regenerate from'}, status=400)

    user_message = last_user.content

    # Rebuild context (same logic as chat_api)
    material_context = None
    if session.study_material:
        material = session.study_material
        material_context = f"Document Context ({material.file.name}):\n{material.summary}"

    christian_keywords = ['god', 'jesus', 'christ', 'bible', 'scripture', 'prayer',
                          'faith', 'christian', 'church', 'lord', 'salvation',
                          'gospel', 'holy spirit', 'worship']
    is_christian_topic = any(kw in user_message.lower() for kw in christian_keywords)

    conversation_history = []
    for msg in session.messages.order_by('created_at')[:30]:
        conversation_history.append({
            'role': msg.role if msg.role in ['user', 'assistant'] else 'user',
            'parts': [msg.content],
            'text': msg.content,
        })

    try:
        response_text = ask_buddy(
            user_message,
            conversation_history=conversation_history,
            material_context=material_context,
            is_religion_topic=is_christian_topic,
        )
    except Exception as e:
        response_text = f"Sorry, I couldn't regenerate a response. (Error: {str(e)})"

    new_msg = ChatMessage.objects.create(
        session=session,
        role='assistant',
        content=response_text,
    )

    return JsonResponse({
        'response': response_text,
        'message_id': new_msg.id,
        'session_id': session.id,
    })