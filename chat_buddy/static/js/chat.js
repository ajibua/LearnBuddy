console.log('JavaScript is loading...');
        
        let currentFile = null;
        let hasSummary = false;
        let chatSessions = [
            { id: 0, title: 'Current Chat', messages: [], session_id: null }
        ];
        let currentChatId = 0;
        let sidebarOpen = true;

        // Wait for DOM to be fully loaded
        document.addEventListener('DOMContentLoaded', function() {
            console.log('DOM loaded, initializing...');
            initializeEventListeners();
            loadChatHistoryFromServer();
        });

        function toggleSidebar() {
    const sidebar = document.getElementById('sidebar');
    sidebar.classList.toggle('closed');
}

        function autoResizeTextarea(textarea) {
            textarea.style.height = 'auto';
            textarea.style.height = Math.min(textarea.scrollHeight, 150) + 'px';
        }

        function initializeEventListeners() {
            const messageInput = document.getElementById('messageInput');
            if (messageInput) {
                // Enter to send, Shift+Enter for new line
                messageInput.addEventListener('keydown', (e) => {
                    if (e.key === 'Enter' && !e.shiftKey) {
                        e.preventDefault();
                        sendMessage();
                    }
                });
                
                // Handle paste events for images and files
                messageInput.addEventListener('paste', (e) => {
                    handlePaste(e);
                });
            }

            document.addEventListener('click', (e) => {
                if (!e.target.closest('.popup-panel') && !e.target.closest('.action-btn')) {
                    document.querySelectorAll('.popup-panel').forEach(p => p.classList.remove('active'));
                }
            });
            
            // Handle paste on the entire document for images
            document.addEventListener('paste', (e) => {
                if (e.target.id !== 'messageInput') {
                    handlePaste(e);
                }
            });
        }

        function handlePaste(e) {
            const items = (e.clipboardData || e.originalEvent.clipboardData).items;
            
            for (let item of items) {
                // Handle image paste
                if (item.kind === 'file' && item.type.startsWith('image/')) {
                    e.preventDefault();
                    const file = item.getAsFile();
                    
                    // Create a synthetic event to reuse handleImageUpload
                    const synthEvent = {
                        target: {
                            files: [file],
                            value: ''
                        }
                    };
                    handleImageUpload(synthEvent);
                    return;
                }
                // Handle file paste (PDF, etc)
                else if (item.kind === 'file') {
                    e.preventDefault();
                    const file = item.getAsFile();
                    
                    if (file.name.toLowerCase().endsWith('.pdf')) {
                        currentFile = file;
                        document.getElementById('fileName').textContent = file.name;
                        processPDF();
                    }
                    return;
                }
            }
        }

        function togglePanel(panelId) {
            console.log('Toggle panel:', panelId);
            const panel = document.getElementById(panelId);
            const allPanels = document.querySelectorAll('.popup-panel');
            
            allPanels.forEach(p => {
                if (p.id !== panelId) {
                    p.classList.remove('active');
                }
            });
            
            panel.classList.toggle('active');
        }

        function closePanel(panelId) {
            document.getElementById(panelId).classList.remove('active');
        }

        function handleFileSelect(e) {
            if (e.target.files.length > 0) {
                currentFile = e.target.files[0];
                document.getElementById('fileName').textContent = currentFile.name;
            } else {
                currentFile = null;
                document.getElementById('fileName').textContent = 'No file chosen';
            }
        }

        function handleImageUpload(e) {
            if (e.target.files.length > 0) {
                const imageFile = e.target.files[0];
                
                // Show processing message
                addMessage('assistant', `Processing "${imageFile.name}"... Please wait while I analyze the image.`);

                // Create FormData
                const formData = new FormData();
                formData.append('image', imageFile);

                // Send to backend for image processing
                fetch('/api/process-image/', {
                    method: 'POST',
                    body: formData,
                    headers: {
                        'X-CSRFToken': getCookie('csrftoken')
                    }
                })
                .then(response => response.json())
                .then(data => {
                    // Update summary panel with extracted content
                    const summaryContent = document.getElementById('summaryContent');
                    summaryContent.innerHTML = `
                        <strong>Image:</strong> ${imageFile.name}<br>
                        <strong>Summary:</strong><br><br>
                        ${data.summary || 'Image analysis in progress...'}
                        <br><br>
                        <strong>Key Topics:</strong><br>
                        ${data.key_topics ? data.key_topics.join(', ') : 'Extracting topics...'}
                    `;

                    hasSummary = true;
                    document.getElementById('summaryBadge').style.display = 'block';
                    
                    // Provide detailed analysis
                    addMessage('assistant', `I've successfully analyzed "${imageFile.name}"!\n\n Here's what I found:\n\n${data.summary || 'This image contains valuable content.'}\n\n💡 I'm now ready to help you understand this content deeply. You can ask me:\n• Questions about specific sections\n• Explanations of complex topics\n• Study tips for this material\n• Biblical connections (if applicable)\n\nHow would you like to proceed?`);
                    updateChatHistory();
                })
                .catch(error => {
                    console.error('Error processing image:', error);
                    addMessage('assistant', `I encountered an issue processing the image. However, I can still help you! Please describe what's in the image or ask me questions about it.`);
                });
                
                // Reset file input
                e.target.value = '';
            }
        }

        function processPDF() {
            if (!currentFile) {
                alert('Please select a document or your study material first');
                return;
            }

            // Show processing message
            addMessage('assistant', `Processing "${currentFile.name}"... Please wait while I analyze the document.`);

            // Determine if it's an image or PDF
            const isImage = currentFile.name.match(/\.(jpg|jpeg|png|gif|bmp|webp)$/i);
            const endpoint = isImage ? '/api/process-image/' : '/api/process-pdf/';
            const formField = isImage ? 'image' : 'pdf';

            // Create FormData
            const formData = new FormData();
            formData.append(formField, currentFile);

            // Send to backend for processing
            fetch(endpoint, {
                method: 'POST',
                body: formData,
                headers: {
                    'X-CSRFToken': getCookie('csrftoken')
                }
            })
            .then(response => response.json())
            .then(data => {
                // Update summary panel with extracted content
                const summaryContent = document.getElementById('summaryContent');
                const pageInfo = data.pages ? `<strong>Pages:</strong> ${data.pages}<br>` : '';
                summaryContent.innerHTML = `
                    <strong>Document:</strong> ${currentFile.name}<br>
                    ${pageInfo}
                    <strong>Summary:</strong><br><br>
                    ${data.summary || 'Document analysis in progress...'}
                    <br><br>
                    <strong>Key Topics:</strong><br>
                    ${data.key_topics ? data.key_topics.join(', ') : 'Extracting topics...'}
                `;

                hasSummary = true;
                document.getElementById('summaryBadge').style.display = 'block';
                
                closePanel('uploadPanel');
                
                // Provide detailed analysis
                const docType = isImage ? 'image' : 'document';
                addMessage('assistant', `I've successfully analyzed "${currentFile.name}"!\n\n Here's what I found:\n\n${data.summary || 'This document contains valuable study material.'}\n\n💡 I'm now ready to help you understand this content deeply. You can ask me:\n• Questions about specific sections\n• Explanations of complex topics\n• Study tips for this material\n• Biblical connections (if applicable)\n\nHow would you like to proceed?`);
                updateChatHistory();
            })
            .catch(error => {
                console.error('Error processing file:', error);
                addMessage('assistant', `I encountered an issue processing the ${isImage ? 'image' : 'PDF'}. However, I can still help you! Please describe what's in the document or ask me questions about your study material.`);
            });
        }

        function loadChatHistoryFromServer() {
            // Load chat history from backend database
            fetch('/api/chat-history/')
                .then(response => response.json())
                .then(data => {
                    if (data.sessions && data.sessions.length > 0) {
                        // Clear the default session and load server sessions
                        chatSessions = [];
                        
                        data.sessions.forEach(session => {
                            chatSessions.push({
                                id: chatSessions.length,
                                title: session.material ? `Chat - ${session.material}` : `Chat - ${new Date(session.created_at).toLocaleDateString()}`,
                                messages: session.messages,
                                session_id: session.session_id  // Store the actual database session ID
                            });
                        });
                        
                        // Load the first session if it exists
                        if (chatSessions.length > 0) {
                            currentChatId = 0;
                            loadChat(0);
                        }
                        
                        renderChatHistory();
                    }
                })
                .catch(error => console.log('No chat history found or error loading:', error));
        }

        // Helper function to get CSRF token
        function getCookie(name) {
            let cookieValue = null;
            if (document.cookie && document.cookie !== '') {
                const cookies = document.cookie.split(';');
                for (let i = 0; i < cookies.length; i++) {
                    const cookie = cookies[i].trim();
                    if (cookie.substring(0, name.length + 1) === (name + '=')) {
                        cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
                        break;
                    }
                }
            }
            return cookieValue;
        }

        function sendMessage() {
            const input = document.getElementById('messageInput');
            const message = input.value.trim();
            
            if (message) {
                // Add user message
                addMessage('user', message);
                input.value = '';
                input.style.height = 'auto';
                
                // Show typing indicator
                const typingDiv = document.createElement('div');
                typingDiv.className = 'message assistant typing-indicator';
                typingDiv.innerHTML = '<span></span><span></span><span></span>';
                typingDiv.id = 'typing-indicator';
                document.getElementById('messages').appendChild(typingDiv);
                document.getElementById('messages').scrollTop = document.getElementById('messages').scrollHeight;
                
                // Send to backend AI
                fetch('/api/chat/', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        'X-CSRFToken': getCookie('csrftoken')
                    },
                    body: JSON.stringify({
                        message: message,
                        has_document: hasSummary,
                        document_name: currentFile ? currentFile.name : null,
                        chat_history: chatSessions[currentChatId].messages,
                        session_id: chatSessions[currentChatId].session_id  // Send session_id
                    })
                })
                .then(response => response.json())
                .then(data => {
                    // Remove typing indicator
                    const indicator = document.getElementById('typing-indicator');
                    if (indicator) {
                        indicator.remove();
                    }
                    
                    // Save session_id from backend
                    if (data.session_id) {
                        chatSessions[currentChatId].session_id = data.session_id;
                    }
                    
                    // Add AI response
                    addMessage('assistant', data.response);
                    updateChatHistory();
                })
                .catch(error => {
                    console.error('Error:', error);
                    
                    // Remove typing indicator
                    const indicator = document.getElementById('typing-indicator');
                    if (indicator) {
                        indicator.remove();
                    }
                    
                    // Fallback response with personality
                    const response = generateFallbackResponse(message);
                    addMessage('assistant', response);
                    updateChatHistory();
                });
            }
        }

        function generateFallbackResponse(userMessage) {
            const lowerMessage = userMessage.toLowerCase();
            
            // Christian/Godly topics - more engaged and helpful
            const christianKeywords = ['god', 'jesus', 'christ', 'bible', 'scripture', 'prayer', 'faith', 'christian', 'church', 'lord', 'salvation', 'gospel', 'holy spirit', 'worship'];
            const isChristianTopic = christianKeywords.some(keyword => lowerMessage.includes(keyword));
            
            if (isChristianTopic) {
                const christianResponses = [
                    "That's a wonderful question about faith! While I can provide general insights, I'd encourage you to explore the Scriptures directly. The Bible says in James 1:5, 'If any of you lacks wisdom, you should ask God, who gives generously to all without finding fault, and it will be given to you.' What specific aspect would you like to explore deeper?",
                    "I'm glad you're seeking understanding about spiritual matters! The Bible is full of wisdom on this topic. Have you considered studying specific passages related to your question? I can help guide you through biblical concepts if you share more details.",
                    "What a beautiful topic to discuss! God's Word has so much to say about this. In 2 Timothy 3:16-17, we learn that 'All Scripture is God-breathed and is useful for teaching, rebuking, correcting and training in righteousness.' How can I help you understand this biblical principle better?",
                    "This is an important spiritual question! The Bible offers profound wisdom on this subject. Would you like me to help you explore relevant Scripture passages or explain biblical principles related to your question?"
                ];
                return christianResponses[Math.floor(Math.random() * christianResponses.length)];
            }
            
            // Explicit/inappropriate content - restricted but polite
            const inappropriateKeywords = ['sex', 'porn', 'explicit', 'nsfw', 'nude'];
            const isInappropriate = inappropriateKeywords.some(keyword => lowerMessage.includes(keyword));
            
            if (isInappropriate) {
                return "I'm designed to be a study assistant focused on educational content. I'd be happy to help you with academic materials, study questions, or discussions about faith and biblical principles. What can I help you learn about today?";
            }
            
            // Document-related questions
            if (hasSummary && currentFile) {
                return `Based on "${currentFile.name}", I can help you understand the content better. Could you be more specific about which section or concept you'd like me to explain? I'm here to help you master this material!`;
            }
            
            // General educational assistance
            if (lowerMessage.includes('help') || lowerMessage.includes('explain') || lowerMessage.includes('what is')) {
                return "I'm here to help you learn! To give you the best assistance:\n\n 1. Upload a PDF document if you have study materials\n 2. Ask specific questions about topics you're studying\n 3. I'm especially helpful with biblical studies and Christian topics\n\nWhat would you like to explore?";
            }
            
            // Default response
            return "I understand you're asking about that topic. 🤔 To provide the most helpful response:\n\n• Upload a study document for detailed analysis\n• Ask specific questions about your learning material\n• For spiritual questions, I'm very engaged in biblical discussions\n\nHow can I assist your learning journey today?";
        }

        function addMessage(type, text) {
            const messages = document.getElementById('messages');
            const messageDiv = document.createElement('div');
            messageDiv.className = `message ${type}`;
            
            // Convert markdown to HTML for assistant messages
            if (type === 'assistant') {
                messageDiv.innerHTML = renderCleanResponse(text);
            } else {
                messageDiv.textContent = text;
            }
            
            messages.appendChild(messageDiv);
            messages.scrollTop = messages.scrollHeight;

            // Store in current chat session
            chatSessions[currentChatId].messages.push({ type, text });
        }

        function updateChatHistory() {
            const currentChat = chatSessions[currentChatId];
            const lastMessage = currentChat.messages[currentChat.messages.length - 1];
            
            if (lastMessage) {
                currentChat.title = lastMessage.text.substring(0, 30) + '...';
            }

            renderChatHistory();
        }

        function renderChatHistory() {
            const chatHistory = document.getElementById('chatHistory');
            chatHistory.innerHTML = chatSessions.map((chat, index) => `
                <div class="chat-history-item ${index === currentChatId ? 'active' : ''}" onclick="loadChat(${index})">
                    <div class="chat-history-title">${chat.title}</div>
                    <div class="chat-history-preview">${chat.messages.length > 0 ? chat.messages[chat.messages.length - 1].text.substring(0, 40) + '...' : 'No messages yet'}</div>
                </div>
            `).join('');
        }

        function loadChat(chatId) {
            currentChatId = chatId;
            const chat = chatSessions[chatId];
            
            const messagesContainer = document.getElementById('messages');
            messagesContainer.innerHTML = chat.messages.map(msg => {
                if (msg.type === 'assistant') {
                    return `<div class="message ${msg.type}">${renderCleanResponse(msg.text)}</div>`;
                } else {
                    return `<div class="message ${msg.type}">${msg.text}</div>`;
                }
            }).join('');
            
            if (chat.messages.length === 0) {
                messagesContainer.innerHTML = `
                    <div class="message assistant">
                        Hello! I'm LearnBuddy, your AI study assistant. Upload a PDF to get started, or ask me anything!
                    </div>
                `;
            }

            renderChatHistory();
        }

        function newSession() {
            const newChatId = chatSessions.length;
            chatSessions.push({
                id: newChatId,
                title: `Chat ${newChatId + 1}`,
                messages: [],
                session_id: null  // New session, no session_id yet
            });
            
            currentChatId = newChatId;
            currentFile = null;
            hasSummary = false;
            
            const fileNameEl = document.getElementById('fileName');
            if (fileNameEl) fileNameEl.textContent = 'No file chosen';
            
            const summaryContentEl = document.getElementById('summaryContent');
            if (summaryContentEl) summaryContentEl.innerHTML = 'No material loaded yet. Upload a PDF to see the summary here.';
            
            const summaryBadgeEl = document.getElementById('summaryBadge');
            if (summaryBadgeEl) summaryBadgeEl.style.display = 'none';
            
            loadChat(newChatId);
        }
        function renderCleanResponse(text) {
    return text
        // Replace ## with clean, spaced headers
        .replace(/^## (.*$)/gim, '<div style="font-weight: bold; font-size: 1.3em; margin: 15px 0 5px 0;">$1</div>')
        // Replace ** with bold tags
        .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
        // Remove * and add bullet points with indentation
        .replace(/^\* (.*$)/gim, '<div style="padding-left: 15px;">• $1</div>')
        // Convert double newlines into paragraph breaks
        .replace(/\n\n/g, '<div style="margin-bottom: 10px;"></div>')
        // Convert single newlines to breaks
        .replace(/\n/g, '<br>');
}

function addMessageToUI(sender, text) {
    const messagesDiv = document.getElementById('messages');
    const newMsg = document.createElement('div');
    newMsg.className = `message ${sender}`;
    
    if (sender === 'assistant') {
        newMsg.innerHTML = formatAIResponse(text);
    } else {
        newMsg.textContent = text;
    }
    
    messagesDiv.appendChild(newMsg);
    messagesDiv.scrollTop = messagesDiv.scrollHeight;
}
function showThinking() {
    const messagesContainer = document.getElementById('messages');
    
    const thinkingDiv = document.createElement('div');
    thinkingDiv.className = 'message assistant thinking';
    thinkingDiv.id = 'ai-thinking'; // ID helps us find it to remove it later
    
    thinkingDiv.innerHTML = `
        <div class="dot"></div>
        <div class="dot"></div>
        <div class="dot"></div>
    `;
    
    messagesContainer.appendChild(thinkingDiv);
    messagesContainer.scrollTop = messagesContainer.scrollHeight;
}

function hideThinking() {
    const thinkingDiv = document.getElementById('ai-thinking');
    if (thinkingDiv) {
        thinkingDiv.remove();
    }
}

        console.log('All functions defined. typeof togglePanel:', typeof togglePanel);