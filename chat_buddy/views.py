from django.shortcuts import render
from rest_framework import status
from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework.parsers import MultiPartParser, FormParser
from rest_framework.views import APIView
from .models import StudyMaterial, ChatSession, ChatMessage
from .ai_service import summarize_pdf, summarize_image, ask_buddy
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
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

def chat_view(request):
    return render(request, 'chat.html')


@api_view(['GET'])
def get_chat_history(request):
    """Fetch all chat sessions with their messages for the current user"""
    try:
        # Get all chat sessions ordered by creation date (newest first)
        sessions = ChatSession.objects.all().order_by('-created_at')
        
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


def chat_view(request):
    return render(request, 'chat.html')

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
        # Parse JSON body
        body = json.loads(request.body)
        user_message = body.get('message', '').strip()
        has_document = body.get('has_document', False)
        document_name = body.get('document_name')
        chat_history = body.get('chat_history', [])
        session_id = body.get('session_id')  # Frontend will send this
        
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
                session = ChatSession.objects.get(id=session_id)
                if session.study_material:
                    material = session.study_material
                    material_context = f"Document Context ({material.file.name}):\n{material.summary}"
            except ChatSession.DoesNotExist:
                # Create new session if not found
                session = ChatSession.objects.create()
        else:
            # Create new session
            session = ChatSession.objects.create()
        
        # If document is uploaded, link it to session
        if has_document and document_name and not session.study_material:
            try:
                material = StudyMaterial.objects.filter(
                    file__icontains=document_name
                ).order_by('-uploaded_at').first()
                
                if material:
                    session.study_material = material
                    session.save()
                    material_context = f"Document Context ({document_name}):\n{material.summary}"
            except:
                pass
        
        # Build system context for AI
        system_context = """You are LearnBuddy, a friendly and helpful AI study assistant. Your personality:

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
   
3. MATHEMATICAL TOPICS: You help students understand mathematical concepts and topics.
   - Analyse the problem and help user understand solutions line by line
   - Use mathematical symbols and mathematical understandable and readable terms.
   - Be supportive and encouraging no matter how complex the problem is.
   - Be clear and precise in your explanation and don't bore user with your explanation, instead help user feel like a mathematics genius when with you.bb 
   
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
                elif has_document:
                    response_text = f"I understand you're asking about the material in {document_name}. I'm having a brief technical issue, but I'm here to help! Could you please rephrase your question or be more specific about which section you'd like me to explain?"
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
        
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON in request body'}, status=400)
    except Exception as e:
        return JsonResponse({
            'error': 'An error occurred processing your message',
            'details': str(e)
        }, status=500)


# Keep your original PDFUploadSummarizeView if needed elsewhere
class PDFUploadSummarizeView(APIView):
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
                summary = summarize_pdf(pdf_path)
                
                study_material = StudyMaterial.objects.create(
                    file=pdf_file,
                    file_type='pdf',
                    summary=summary
                )
                
                return Response({
                    'id': study_material.id,
                    'filename': pdf_file.name,
                    'summary': summary,
                    'uploaded_at': study_material.uploaded_at
                }, status=status.HTTP_201_CREATED)
            finally:
                # Clean up temp file if we created one
                if not hasattr(pdf_file, 'temporary_file_path'):
                    os.unlink(pdf_path)
            
        except Exception as e:
            return Response({'error': f'Failed to process PDF: {str(e)}'}, 
                          status=status.HTTP_500_INTERNAL_SERVER_ERROR)