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
from .models import StudyMaterial, ChatSession, ChatMessage, FlashcardDeck, Flashcard, Quiz, QuizQuestion, StudySessionRecord
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
import datetime
from django.utils import timezone
from django.db.models import Sum

def landing_view(request):
    if request.user.is_authenticated:
        return redirect('dashboard')
    context = {
        'user': request.user,
        'is_authenticated': request.user.is_authenticated
    }
    return render(request, 'landing.html', context)

@login_required(login_url='login')
def chat_view(request):
    context = {
        'user': request.user,
        'is_authenticated': request.user.is_authenticated
    }
    return render(request, 'chat.html', context)

def login_view(request):
    if request.user.is_authenticated:
        return redirect('dashboard')
    
    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')
        
        user = authenticate(request, username=username, password=password)
        if not user:
            try:
                user_obj = User.objects.get(email=username)
                user = authenticate(request, username=user_obj.username, password=password)
            except User.DoesNotExist:
                user = None
        
        if user is not None:
            auth_login(request, user)
            return redirect('dashboard')
        else:
            messages.error(request, 'Invalid username/email or password.')
    
    return render(request, 'login.html')

def signup_view(request):
    if request.user.is_authenticated:
        return redirect('dashboard')
    
    if request.method == 'POST':
        username = request.POST.get('username')
        email = request.POST.get('email')
        password = request.POST.get('password')
        password_confirm = request.POST.get('password_confirm')
        
        if not all([username, email, password, password_confirm]):
            messages.error(request, 'Please fill in all fields.')
        elif password != password_confirm:
            messages.error(request, 'Passwords do not match.')
        elif User.objects.filter(username=username).exists():
            messages.error(request, 'Username already exists.')
        elif User.objects.filter(email=email).exists():
            messages.error(request, 'Email already registered.')
        else:
            from django.contrib.auth.password_validation import validate_password
            from django.core.exceptions import ValidationError
            try:
                validate_password(password)
                user = User.objects.create_user(username=username, email=email, password=password)
                auth_login(request, user)
                return redirect('dashboard')
            except ValidationError as e:
                for error in e.messages:
                    messages.error(request, error)
    
    return render(request, 'signup.html')

def logout_view(request):
    auth_logout(request)
    messages.success(request, 'You have been logged out.')
    return redirect('landing')

@api_view(['POST'])
@permission_classes([AllowAny])
def register_api(request):
    username = request.data.get('username')
    email = request.data.get('email')
    password = request.data.get('password')

    if not username or not password or not email:
        return Response({'error': 'Please provide all fields'}, status=status.HTTP_400_BAD_REQUEST)

    if User.objects.filter(username=username).exists():
        return Response({'error': 'Username already exists'}, status=status.HTTP_400_BAD_REQUEST)

    if User.objects.filter(email=email).exists():
        return Response({'error': 'Email already registered'}, status=status.HTTP_400_BAD_REQUEST)

    from django.contrib.auth.password_validation import validate_password
    from django.core.exceptions import ValidationError
    try:
        validate_password(password)
    except ValidationError as e:
        return Response({'error': e.messages[0]}, status=status.HTTP_400_BAD_REQUEST)

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
    try:
        if not request.user.is_authenticated:
            return JsonResponse({'error': 'Not authenticated'}, status=401)
        
        sessions = ChatSession.objects.filter(user=request.user).order_by('-created_at')
        
        chat_data = []
        for session in sessions:
            messages = session.messages.all().order_by('created_at')
            chat_data.append({
                'session_id': session.id,
                'title': session.title or '',
                'created_at': session.created_at.isoformat(),
                'material': session.study_material.file.name if session.study_material else None,
                'material_id': session.study_material.id if session.study_material else None,
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

    from django.contrib.auth.password_validation import validate_password
    from django.core.exceptions import ValidationError
    try:
        validate_password(password)
    except ValidationError as e:
        return Response({'error': e.messages[0]}, status=status.HTTP_400_BAD_REQUEST)

    user = User.objects.create_user(username=username, email=email, password=password)
    token, created = Token.objects.get_or_create(user=user)
    
    return Response({
        'token': token.key,
        'user_id': user.pk,
        'username': user.username
    }, status=status.HTTP_201_CREATED)

@api_view(['POST'])
def chat_api(request):
    try:
        if not request.user.is_authenticated:
            return JsonResponse({'error': 'Not authenticated'}, status=401)
        
        user_message = request.data.get('message', '').strip()
        session_id = request.data.get('session_id')
        
        if not user_message:
            return JsonResponse({'error': 'Message is required'}, status=400)
        
        christian_keywords = ['god', 'jesus', 'christ', 'bible', 'scripture', 'prayer', 
                            'faith', 'christian', 'church', 'lord', 'salvation', 
                            'gospel', 'holy spirit', 'worship']
        is_christian_topic = any(keyword in user_message.lower() for keyword in christian_keywords)
        
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
                session = ChatSession.objects.create(user=request.user)
        else:
            session = ChatSession.objects.create(user=request.user)
        
        system_context = """You are LearnBuddy, a friendly and helpful AI study assistant with EXPERT-LEVEL mathematics expertise. Your personality:

0. GREETINGS & CASUAL MESSAGES: Always respond warmly to greetings like "hi", "hey", "hello", "heyy", "hii", "sup", "yo", etc.
   - Reply with a friendly greeting and briefly introduce yourself as LearnBuddy.
   - Invite the user to ask a question or share what they'd like to learn.
   - Example: "Hey there! I'm LearnBuddy, your AI study companion. What would you like to learn or explore today?"

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

        conversation_history = []
        db_messages = session.messages.order_by('created_at')[:30]
        
        for msg in db_messages:
            conversation_history.append({
                "role": msg.role if msg.role in ['user', 'assistant'] else 'user',
                "parts": [msg.content],
                "text": msg.content
            })
        
        if is_christian_topic:
            system_context += "\n\nNOTE: This is a question about Christian faith. Provide a warm, biblically-grounded response with Scripture references."
        
        try:
            response_text = ask_buddy(
                user_message,
                conversation_history=conversation_history,
                material_context=material_context,
                system_context=system_context,
                is_religion_topic=is_christian_topic
            )

            if not response_text or not response_text.strip():
                response_text = "Hey there! I'm LearnBuddy, your AI study companion. Feel free to ask me anything — a subject, a problem, or just say what's on your mind!"
        except Exception as e:

            if is_christian_topic:
                response_text = "That's a wonderful question about faith! While I'm having trouble accessing my full knowledge right now, I'd encourage you to explore the Scriptures directly. The Bible says in James 1:5, 'If any of you lacks wisdom, you should ask God, who gives generously to all without finding fault, and it will be given to you.' Could you rephrase your question, or would you like to discuss a specific Bible passage?"
            elif material_context:
                response_text = "I understand you're asking about the material you uploaded. I'm having a brief technical issue, but I'm here to help! Could you please rephrase your question or be more specific about which section you'd like me to explain?"
            else:
                response_text = "I'm experiencing a brief technical difficulty. Please try rephrasing your question, or if you have study materials, upload them so I can provide more specific help!"
        
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

        session_title = session.title or ''
        if not session_title:
            msg_count = session.messages.count()
            if msg_count <= 4:
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

@method_decorator(csrf_exempt, name='dispatch')
class FileUploadView(APIView):
    parser_classes = (MultiPartParser, FormParser)
    
    def post(self, request, *args, **kwargs):
        try:

            if not request.user.is_authenticated:
                return Response({'error': 'Not authenticated'}, status=status.HTTP_401_UNAUTHORIZED)
            
            uploaded_file = request.FILES.get('file')
            
            if not uploaded_file:
                return Response({'error': 'No file provided'}, 
                              status=status.HTTP_400_BAD_REQUEST)
            
            filename = uploaded_file.name.lower()
            file_type = 'unknown'
            summary = ""
            
            if filename.endswith('.pdf'):
                file_type = 'pdf'
            elif filename.endswith(('.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp')):
                file_type = 'image'
            elif filename.endswith(('.docx', '.txt')):
                file_type = 'document'
            else:
                return Response({'error': 'File type not supported. Please use PDF, images (JPG, PNG, GIF, BMP, WebP), DOCX, or TXT.'}, 
                              status=status.HTTP_400_BAD_REQUEST)
            
            import tempfile
            temp_path = None
            
            try:

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
                
                user_message = request.data.get('user_message', '').strip()
                if file_type == 'pdf':
                    summary = summarize_pdf(temp_path, user_instruction=user_message)
                elif file_type == 'image':
                    summary = summarize_image(temp_path, user_instruction=user_message)
                else:
                    summary = summarize_document(temp_path, user_instruction=user_message)
                
                study_material = StudyMaterial.objects.create(
                    user=request.user,
                    file=uploaded_file,
                    file_type=file_type,
                    summary=summary
                )

                session_id = request.data.get('session_id')
                session = None
                if session_id:
                    try:
                        session = ChatSession.objects.get(id=session_id, user=request.user)
                        session.study_material = study_material
                        session.save()
                    except (ChatSession.DoesNotExist, ValueError):
                        session = None

                if not session:
                    session = ChatSession.objects.create(
                        user=request.user,
                        study_material=study_material
                    )

                user_bubble = f"Attached: {uploaded_file.name}"
                if user_message:
                    user_bubble += f"\n\n{user_message}"
                ChatMessage.objects.create(
                    session=session,
                    role='user',
                    content=user_bubble
                )

                ChatMessage.objects.create(
                    session=session,
                    role='assistant',
                    content=f"[Uploaded file: {uploaded_file.name}]\n\nSummary:\n{summary}"
                )

                session_title = session.title or ''
                if not session_title:
                    generated = _generate_title(user_bubble, summary)
                    if generated:
                        session.title = generated
                        session.save(update_fields=['title'])
                        session_title = generated

                return Response({
                    'id': study_material.id,
                    'filename': uploaded_file.name,
                    'file_type': file_type,
                    'file_url': study_material.file.url,
                    'summary': summary,
                    'uploaded_at': study_material.uploaded_at,
                    'session_id': session.id,
                    'session_title': session_title,
                }, status=status.HTTP_201_CREATED)
                
            finally:

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

    value = request.data.get('feedback')
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

    last_assistant = session.messages.filter(role='assistant').last()
    if last_assistant:
        last_assistant.delete()

    last_user = session.messages.filter(role='user').last()
    if not last_user:
        return JsonResponse({'error': 'No user message to regenerate from'}, status=400)

    user_message = last_user.content

    material_context = None
    if session.study_material:
        material = session.study_material
        material_context = f"Document Context ({material.file.name}):\n{material.summary}"

    christian_keywords = ['god', 'jesus', 'christ', 'bible', 'scripture', 'prayer',
                          'faith', 'christian', 'church', 'lord', 'salvation',
                          'gospel', 'holy spirit', 'worship']
    is_religion_topic = any(kw in user_message.lower() for kw in christian_keywords)

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
            is_religion_topic=is_religion_topic,
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

@login_required(login_url='login')
def dashboard_view(request):
    materials = StudyMaterial.objects.filter(user=request.user)
    sessions = ChatSession.objects.filter(user=request.user)
    decks = FlashcardDeck.objects.filter(user=request.user)
    quizzes = Quiz.objects.filter(user=request.user)
    
    today = timezone.now().date()
    weekly_data = []
    for i in range(6, -1, -1):
        day = today - datetime.timedelta(days=i)
        day_str = day.strftime('%a')
        seconds = StudySessionRecord.objects.filter(
            user=request.user,
            date=day
        ).aggregate(total=Sum('duration_seconds'))['total'] or 0
        minutes = round(seconds / 60.0, 1)
        weekly_data.append({
            'day': day_str,
            'minutes': minutes
        })
        
    max_minutes = max([item['minutes'] for item in weekly_data] + [10])
    for item in weekly_data:
        item['percent'] = round((item['minutes'] / max_minutes) * 100.0)
        
    total_chat_secs = StudySessionRecord.objects.filter(
        user=request.user,
        activity_type='chat'
    ).aggregate(total=Sum('duration_seconds'))['total'] or 0

    total_flashcards_secs = StudySessionRecord.objects.filter(
        user=request.user,
        activity_type='flashcards'
    ).aggregate(total=Sum('duration_seconds'))['total'] or 0

    total_quiz_secs = StudySessionRecord.objects.filter(
        user=request.user,
        activity_type='quiz'
    ).aggregate(total=Sum('duration_seconds'))['total'] or 0

    total_secs = total_chat_secs + total_flashcards_secs + total_quiz_secs
    if total_secs > 0:
        chat_percent = round((total_chat_secs / total_secs) * 100.0)
        flashcards_percent = round((total_flashcards_secs / total_secs) * 100.0)
        quiz_percent = round((total_quiz_secs / total_secs) * 100.0)
    else:
        chat_percent = 0
        flashcards_percent = 0
        quiz_percent = 0
        
    total_study_minutes = round(total_secs / 60.0, 1)
    
    context = {
        'materials_count': materials.count(),
        'sessions_count': sessions.count(),
        'decks_count': decks.count(),
        'quizzes_count': quizzes.filter(score__isnull=False).count(),
        'recent_materials': materials[:5],
        'recent_sessions': sessions[:5],
        'weekly_trend': weekly_data,
        'chat_percent': chat_percent,
        'flashcards_percent': flashcards_percent,
        'quiz_percent': quiz_percent,
        'chat_minutes': round(total_chat_secs / 60.0, 1),
        'flashcards_minutes': round(total_flashcards_secs / 60.0, 1),
        'quiz_minutes': round(total_quiz_secs / 60.0, 1),
        'total_study_minutes': total_study_minutes,
    }
    return render(request, 'dashboard.html', context)

@login_required(login_url='login')
def flashcards_view(request):
    decks = FlashcardDeck.objects.filter(user=request.user)
    materials = StudyMaterial.objects.filter(user=request.user)
    context = {
        'decks': decks,
        'materials': materials,
    }
    return render(request, 'flashcards.html', context)

@login_required(login_url='login')
def quizzes_view(request):
    quizzes = Quiz.objects.filter(user=request.user)
    materials = StudyMaterial.objects.filter(user=request.user)
    context = {
        'quizzes': quizzes,
        'materials': materials,
    }
    return render(request, 'quizzes.html', context)

@api_view(['POST'])
def generate_flashcards_api(request):
    if not request.user.is_authenticated:
        return JsonResponse({'error': 'Not authenticated'}, status=401)
    material_id = request.data.get('material_id')
    count = int(request.data.get('count', 10))
    try:
        material = StudyMaterial.objects.get(id=material_id, user=request.user)
    except StudyMaterial.DoesNotExist:
        return JsonResponse({'error': 'Material not found'}, status=404)
    try:
        from .ai_service import generate_flashcards_ai
        deck_data = generate_flashcards_ai(material.summary, num_cards=count)
        deck = FlashcardDeck.objects.create(
            user=request.user,
            study_material=material,
            title=deck_data.get('title', f"Flashcard Deck for {material.file.name}")
        )
        for item in deck_data.get('cards', []):
            Flashcard.objects.create(
                deck=deck,
                front=item.get('front', ''),
                back=item.get('back', '')
            )
        return JsonResponse({'deck_id': deck.id, 'title': deck.title})
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)

@api_view(['GET'])
def list_flashcard_decks_api(request):
    if not request.user.is_authenticated:
        return JsonResponse({'error': 'Not authenticated'}, status=401)
    decks = FlashcardDeck.objects.filter(user=request.user)
    decks_data = []
    for d in decks:
        decks_data.append({
            'id': d.id,
            'title': d.title,
            'count': d.cards.count(),
            'created_at': d.created_at.isoformat()
        })
    return JsonResponse({'decks': decks_data})

@api_view(['GET'])
def get_flashcard_deck_api(request, deck_id):
    if not request.user.is_authenticated:
        return JsonResponse({'error': 'Not authenticated'}, status=401)
    try:
        deck = FlashcardDeck.objects.get(id=deck_id, user=request.user)
        cards_data = []
        for card in deck.cards.all():
            cards_data.append({
                'front': card.front,
                'back': card.back
            })
        return JsonResponse({
            'id': deck.id,
            'title': deck.title,
            'study_material_id': deck.study_material.id if deck.study_material else None,
            'cards': cards_data
        })
    except FlashcardDeck.DoesNotExist:
        return JsonResponse({'error': 'Deck not found'}, status=404)

@api_view(['POST'])
def generate_quiz_api(request):
    if not request.user.is_authenticated:
        return JsonResponse({'error': 'Not authenticated'}, status=401)
    material_id = request.data.get('material_id')
    count = int(request.data.get('count', 5))
    try:
        material = StudyMaterial.objects.get(id=material_id, user=request.user)
    except StudyMaterial.DoesNotExist:
        return JsonResponse({'error': 'Material not found'}, status=404)
    try:
        from .ai_service import generate_quiz_ai
        quiz_data = generate_quiz_ai(material.summary, num_questions=count)
        quiz = Quiz.objects.create(
            user=request.user,
            study_material=material,
            title=quiz_data.get('title', f"Quiz for {material.file.name}"),
            total_questions=len(quiz_data.get('questions', []))
        )
        for q in quiz_data.get('questions', []):
            QuizQuestion.objects.create(
                quiz=quiz,
                question_text=q.get('question_text', ''),
                option_a=q.get('option_a', ''),
                option_b=q.get('option_b', ''),
                option_c=q.get('option_c', ''),
                option_d=q.get('option_d', ''),
                correct_option=q.get('correct_option', 'A').upper(),
                explanation=q.get('explanation', '')
            )
        return JsonResponse({'quiz_id': quiz.id, 'title': quiz.title})
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)

@api_view(['GET'])
def list_quizzes_api(request):
    if not request.user.is_authenticated:
        return JsonResponse({'error': 'Not authenticated'}, status=401)
    quizzes = Quiz.objects.filter(user=request.user)
    quizzes_data = []
    for q in quizzes:
        quizzes_data.append({
            'id': q.id,
            'title': q.title,
            'score': q.score,
            'total': q.total_questions,
            'created_at': q.created_at.isoformat()
        })
    return JsonResponse({'quizzes': quizzes_data})

@api_view(['GET'])
def get_quiz_api(request, quiz_id):
    if not request.user.is_authenticated:
        return JsonResponse({'error': 'Not authenticated'}, status=401)
    try:
        quiz = Quiz.objects.get(id=quiz_id, user=request.user)
        questions_data = []
        for q in quiz.questions.all():
            questions_data.append({
                'question_text': q.question_text,
                'option_a': q.option_a,
                'option_b': q.option_b,
                'option_c': q.option_c,
                'option_d': q.option_d,
                'correct_option': q.correct_option,
                'explanation': q.explanation
            })
        return JsonResponse({
            'id': quiz.id,
            'title': quiz.title,
            'study_material_id': quiz.study_material.id if quiz.study_material else None,
            'questions': questions_data
        })
    except Quiz.DoesNotExist:
        return JsonResponse({'error': 'Quiz not found'}, status=404)

@api_view(['POST'])
def submit_quiz_answer_api(request, quiz_id):
    if not request.user.is_authenticated:
        return JsonResponse({'error': 'Not authenticated'}, status=401)
    question_index = int(request.data.get('question_index', 0))
    user_answer = request.data.get('user_answer', '').upper()
    try:
        quiz = Quiz.objects.get(id=quiz_id, user=request.user)
        questions = list(quiz.questions.all())
        if question_index < len(questions):
            q = questions[question_index]
            q.user_answer = user_answer
            q.save()
            return JsonResponse({'status': 'saved'})
        return JsonResponse({'error': 'Invalid question index'}, status=400)
    except Quiz.DoesNotExist:
        return JsonResponse({'error': 'Quiz not found'}, status=404)

@api_view(['POST'])
def finish_quiz_api(request, quiz_id):
    if not request.user.is_authenticated:
        return JsonResponse({'error': 'Not authenticated'}, status=401)
    score = int(request.data.get('score', 0))
    try:
        quiz = Quiz.objects.get(id=quiz_id, user=request.user)
        quiz.score = score
        quiz.save()
        return JsonResponse({'status': 'finished'})
    except Quiz.DoesNotExist:
        return JsonResponse({'error': 'Quiz not found'}, status=404)

@api_view(['POST'])
def track_study_time_api(request):
    if not request.user.is_authenticated:
        return JsonResponse({'error': 'Not authenticated'}, status=401)
    activity_type = request.data.get('activity_type')
    material_id = request.data.get('study_material_id')
    duration = int(request.data.get('duration_seconds', 30))
    if activity_type not in ('chat', 'flashcards', 'quiz'):
        return JsonResponse({'error': 'Invalid activity type'}, status=400)
    today = timezone.now().date()
    material = None
    if material_id:
        try:
            material = StudyMaterial.objects.get(id=material_id, user=request.user)
        except StudyMaterial.DoesNotExist:
            pass
    record, created = StudySessionRecord.objects.get_or_create(
        user=request.user,
        activity_type=activity_type,
        study_material=material,
        date=today,
        defaults={'duration_seconds': 0}
    )
    record.duration_seconds += duration
    record.save(update_fields=['duration_seconds'])
    return JsonResponse({'status': 'success', 'total_duration_seconds': record.duration_seconds})