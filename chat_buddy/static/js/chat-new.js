// Modern Chat Interface
let currentFile = null;
let chatSessions = [];
let currentSessionId = null;
let isLoading = false;

// Initialize
document.addEventListener('DOMContentLoaded', () => {
    loadTheme();                // restore dark/light preference
    initializeEventListeners();
    updateUserProfile();        // fetch and update current user profile
    loadChatHistory();
    checkInitialMessage();
});

function initializeEventListeners() {
    // Message input
    const messageInput = document.getElementById('messageInput');
    messageInput.addEventListener('keydown', (e) => {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            sendMessage();
        }
    });
    messageInput.addEventListener('input', () => autoResizeTextarea(messageInput));

    // File upload
    const uploadArea = document.getElementById('uploadArea');
    const fileInput = document.getElementById('fileInput');
    
    uploadArea.addEventListener('click', () => fileInput.click());
    uploadArea.addEventListener('dragover', (e) => {
        e.preventDefault();
        uploadArea.style.borderColor = 'var(--primary)';
        uploadArea.style.background = 'rgba(59, 130, 246, 0.05)';
    });
    
    uploadArea.addEventListener('dragleave', () => {
        uploadArea.style.borderColor = 'var(--border)';
        uploadArea.style.background = '';
    });
    
    uploadArea.addEventListener('drop', (e) => {
        e.preventDefault();
        uploadArea.style.borderColor = 'var(--border)';
        uploadArea.style.background = '';
        
        const files = e.dataTransfer.files;
        if (files.length > 0) {
            fileInput.files = files;
            handleFileUpload({ target: { files } });
        }
    });

    fileInput.addEventListener('change', handleFileUpload);

    // Action card click handlers
    const actionCards = document.querySelectorAll('.action-card');
    actionCards.forEach(card => {
        card.addEventListener('click', (e) => {
            e.stopPropagation();
            if (card.textContent.includes('Upload Material')) {
                showUploadPanel();
            } else if (card.textContent.includes('Ask')) {
                document.getElementById('messageInput').focus();
            }
        });
    });

    // Close upload panel on outside click
    document.addEventListener('click', (e) => {
        const uploadPanel = document.getElementById('uploadPanel');
        if (uploadPanel && uploadPanel.classList.contains('active') && 
            !uploadPanel.contains(e.target) && 
            !e.target.closest('.tool-btn') &&
            !e.target.closest('.action-card')) {
            closeUploadPanel();
        }
    });
}

async function updateUserProfile() {
    try {
        const response = await fetch('/api/current-user/', {
            method: 'GET',
            headers: { 'Content-Type': 'application/json', 'X-CSRFToken': getCookie('csrftoken') }
        });

        if (response.ok) {
            const userData = await response.json();
            const firstName = userData.first_name || userData.username || 'User';
            const firstLetter = firstName.charAt(0).toUpperCase();

            // Update sidebar avatar + name
            const profileAvatar = document.getElementById('profileAvatar');
            if (profileAvatar) profileAvatar.textContent = firstLetter;

            const profileName = document.getElementById('profileName');
            if (profileName) profileName.textContent = firstName;

            // Update welcome heading if visible
            const welcomeHeading = document.querySelector('.welcome-section h2');
            if (welcomeHeading) welcomeHeading.textContent = `Hey there, ${firstName}! 👋`;

        } else if (response.status === 401) {
            window.location.href = '/auth/login/';
        }
    } catch (error) {
        console.error('Error updating user profile:', error);
    }
}
function autoResizeTextarea(textarea) {
    textarea.style.height = 'auto';
    textarea.style.height = Math.min(textarea.scrollHeight, 80) + 'px';
}

function showUploadPanel() {
    console.log('showUploadPanel called');
    const panel = document.getElementById('uploadPanel');
    if (panel) {
        panel.classList.add('active');
        console.log('uploadPanel active class added');
    } else {
        console.error('uploadPanel element not found');
    }
}

function closeUploadPanel() {
    console.log('closeUploadPanel called');
    const panel = document.getElementById('uploadPanel');
    if (panel) {
        panel.classList.remove('active');
        console.log('uploadPanel active class removed');
    }
}

function handleFileUpload(e) {
    const file = e.target.files[0];
    if (!file) return;

    currentFile = file;
    
    // Format file size
    const fileSize = (file.size / 1024 / 1024).toFixed(2);
    
    // Show file info
    document.getElementById('fileName').textContent = file.name;
    document.getElementById('fileSize').textContent = `${fileSize} MB`;
    document.getElementById('fileInfo').style.display = 'flex';
    document.getElementById('fileMessageArea').style.display = 'block';
    document.getElementById('processBtn').style.display = 'block';
}

function clearFile() {
    currentFile = null;
    document.getElementById('fileInput').value = '';
    document.getElementById('fileInfo').style.display = 'none';
    document.getElementById('fileMessageArea').style.display = 'none';
    document.getElementById('fileMessage').value = '';
    document.getElementById('processBtn').style.display = 'none';
}

async function processFile() {
    if (!currentFile) return;

    const userMessage = (document.getElementById('fileMessage')?.value || '').trim();

    const formData = new FormData();
    formData.append('file', currentFile);
    // Pass the current session ID so the file gets linked to this conversation
    if (currentSessionId) {
        formData.append('session_id', currentSessionId);
    }
    if (userMessage) {
        formData.append('user_message', userMessage);
    }

    // Show user bubble immediately — file + optional message
    const welcomeSection = document.querySelector('.welcome-section');
    if (welcomeSection) welcomeSection.remove();
    const bubbleContent = userMessage
        ? `📎 **${currentFile.name}**\n\n${userMessage}`
        : `📎 **${currentFile.name}**`;
    addMessage('user', bubbleContent);

    closeUploadPanel();
    clearFile();

    try {
        showLoadingIndicator();
        
        const response = await fetch('/api/upload/', {
            method: 'POST',
            headers: {
                'X-CSRFToken': getCookie('csrftoken')
            },
            body: formData
        });

        removeLoadingIndicator();
        const data = await response.json();
        
        if (response.ok) {
            // Persist the session_id returned after linking the material
            if (data.session_id) {
                currentSessionId = data.session_id;
            }
            
            // Add assistant message with summary
            addMessage('assistant', `✅ **${data.filename}** uploaded successfully!\n\n**📝 Summary:**\n\n${data.summary}\n\nFeel free to ask me any questions about this material!`);
            updateChatTitle(data.filename, data.filename);
        } else {
            addMessage('assistant', `❌ Error: ${data.error}`);
        }
    } catch (error) {
        removeLoadingIndicator();
        addMessage('assistant', '❌ Error uploading file. Please try again.');
        console.error('Error:', error);
    }
}

async function sendMessage() {
    const input = document.getElementById('messageInput');
    const message = input.value.trim();

    if (!message || isLoading) return;

    // Remove welcome section if needed
    const welcomeSection = document.querySelector('.welcome-section');
    if (welcomeSection) {
        welcomeSection.remove();
    }

    // Add user message
    addMessage('user', message);
    input.value = '';
    input.style.height = 'auto';

    // Show loading indicator
    isLoading = true;
    showLoadingIndicator();

    try {
        const response = await fetch('/api/chat/', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': getCookie('csrftoken')
            },
            body: JSON.stringify({
                message: message,
                session_id: currentSessionId
            })
        });

        removeLoadingIndicator();

        if (response.ok) {
            const data = await response.json();
            addMessage('assistant', data.response);
            // CRITICAL: persist the real DB session_id for conversation continuity
            if (data.session_id) {
                currentSessionId = data.session_id;
            }
            updateChatTitle(message);
        } else {
            addMessage('assistant', 'Sorry, I encountered an error. Please try again.');
        }
    } catch (error) {
        removeLoadingIndicator();
        addMessage('assistant', 'Connection error. Please try again.');
        console.error('Error:', error);
    } finally {
        isLoading = false;
    }
}

function cleanMathNotation(text) {
    // Unicode superscript and subscript characters
    const superscripts = {
        '0': '⁰', '1': '¹', '2': '²', '3': '³', '4': '⁴', '5': '⁵', '6': '⁶', '7': '⁷', '8': '⁸', '9': '⁹',
        'a': 'ᵃ', 'b': 'ᵇ', 'c': 'ᶜ', 'd': 'ᵈ', 'e': 'ᵉ', 'f': 'ᶠ', 'g': 'ᵍ', 'h': 'ʰ', 'i': 'ⁱ', 'j': 'ʲ', 'k': 'ᵏ', 'l': 'ˡ', 'm': 'ᵐ', 'n': 'ⁿ', 'o': 'ᵒ', 'p': 'ᵖ', 'q': 'ᵍ', 'r': 'ʳ', 's': 'ˢ', 't': 'ᵗ', 'u': 'ᵘ', 'v': 'ᵛ', 'w': 'ʷ', 'x': 'ˣ', 'y': 'ʸ', 'z': 'ᶻ',
        'A': 'ᴬ', 'B': 'ᴮ', 'C': 'ᶜ', 'D': 'ᴰ', 'E': 'ᴱ', 'F': 'ᶠ', 'G': 'ᴳ', 'H': 'ᴴ', 'I': 'ᴵ', 'J': 'ᴶ', 'K': 'ᴷ', 'L': 'ᴸ', 'M': 'ᴹ', 'N': 'ᴺ', 'O': 'ᴼ', 'P': 'ᴾ', 'Q': 'ᵠ', 'R': 'ᴿ', 'S': 'ˢ', 'T': 'ᵀ', 'U': 'ᵁ', 'V': 'ᵛ', 'W': 'ʷ', 'X': 'ˣ', 'Y': 'ʸ', 'Z': 'ᶻ',
        '+': '⁺', '-': '⁻', '=': '⁼', '(': '⁽', ')': '⁾'
    };
    
    const subscripts = {
        '0': '₀', '1': '₁', '2': '₂', '3': '₃', '4': '₄', '5': '₅', '6': '₆', '7': '₇', '8': '₈', '9': '₉',
        'a': 'ₐ', 'b': 'ᵦ', 'c': 'ᶜ', 'd': 'ᵨ', 'e': 'ₑ', 'f': 'ᶠ', 'g': 'ᵍ', 'h': 'ₕ', 'i': 'ᵢ', 'j': 'ⱼ', 'k': 'ₖ', 'l': 'ₗ', 'm': 'ₘ', 'n': 'ₙ', 'o': 'ₒ', 'p': 'ₚ', 'q': 'ᵩ', 'r': 'ᵣ', 's': 'ₛ', 't': 'ₜ', 'u': 'ᵤ', 'v': 'ᵥ', 'w': 'ₓ', 'x': 'ₓ', 'y': 'ᵧ', 'z': 'ᵤ',
        '+': '₊', '-': '₋', '=': '₌', '(': '₍', ')': '₎'
    };
    
    // Remove $ symbols used for LaTeX math mode
    text = text.replace(/\$\$/g, '');
    text = text.replace(/\$/g, '');
    
    // Convert \frac{numerator}{denominator} to "numerator/denominator"
    text = text.replace(/\\frac\{([^}]+)\}\{([^}]+)\}/g, '$1/$2');
    
    // Convert \sqrt{} to sqrt()
    text = text.replace(/\\sqrt\{([^}]+)\}/g, 'sqrt($1)');
    
    // Remove other LaTeX commands like \left, \right, etc
    text = text.replace(/\\(left|right|Big|big|bigg|Bigg|displaystyle|textstyle)\s*/g, '');
    
    // SUPERSCRIPTS - Convert x^2, x^n, etc. to Unicode superscript characters
    // Handle patterns: variable^{multiple_chars}, variable^single_char
    text = text.replace(/([a-zA-Z0-9])\^\{([^}]+)\}/g, (match, variable, power) => {
        return variable + Array.from(power).map(c => superscripts[c] || c).join('');
    });
    
    text = text.replace(/([a-zA-Z0-9])\^([0-9])/g, (match, variable, power) => {
        return variable + (superscripts[power] || power);
    });
    
    text = text.replace(/([a-zA-Z0-9])\^([a-zA-Z])/g, (match, variable, power) => {
        return variable + (superscripts[power] || power);
    });
    
    // SUBSCRIPTS - Convert x_1, a_n, etc. to Unicode subscript characters
    text = text.replace(/([a-zA-Z0-9])_\{([^}]+)\}/g, (match, variable, sub) => {
        return variable + Array.from(sub).map(c => subscripts[c] || c).join('');
    });
    
    text = text.replace(/([a-zA-Z0-9])_([0-9])/g, (match, variable, sub) => {
        return variable + (subscripts[sub] || sub);
    });
    
    text = text.replace(/([a-zA-Z0-9])_([a-zA-Z])/g, (match, variable, sub) => {
        return variable + (subscripts[sub] || sub);
    });
    
    // MATHEMATICAL OPERATORS - Keep as symbols, not words
    text = text.replace(/\\times/g, '×');
    text = text.replace(/\\div/g, '÷');
    text = text.replace(/\\cdot/g, '·');
    text = text.replace(/\\ast/g, '*');
    
    // COMPARISON OPERATORS
    text = text.replace(/\\approx/g, '≈');
    text = text.replace(/\\neq/g, '≠');
    text = text.replace(/\\leq/g, '≤');
    text = text.replace(/\\geq/g, '≥');
    text = text.replace(/\\equiv/g, '≡');
    
    // SPECIAL SYMBOLS
    text = text.replace(/\\infty/g, '∞');
    text = text.replace(/\\partial/g, '∂');
    text = text.replace(/\\nabla/g, '∇');
    text = text.replace(/\\emptyset/g, '∅');
    text = text.replace(/\\forall/g, '∀');
    text = text.replace(/\\exists/g, '∃');
    
    // CALCULUS SYMBOLS
    text = text.replace(/\\sum/g, '∑');
    text = text.replace(/\\prod/g, '∏');
    text = text.replace(/\\int/g, '∫');
    text = text.replace(/\\iint/g, '∬');
    text = text.replace(/\\iiint/g, '∭');
    text = text.replace(/\\oint/g, '∮');
    
    // GREEK LETTERS - UPPERCASE
    text = text.replace(/\\Delta/g, 'Δ');
    text = text.replace(/\\Sigma/g, 'Σ');
    text = text.replace(/\\Pi/g, 'Π');
    text = text.replace(/\\Omega/g, 'Ω');
    text = text.replace(/\\Lambda/g, 'Λ');
    text = text.replace(/\\Gamma/g, 'Γ');
    text = text.replace(/\\Theta/g, 'Θ');
    
    // GREEK LETTERS - LOWERCASE
    text = text.replace(/\\pi/g, 'π');
    text = text.replace(/\\alpha/g, 'α');
    text = text.replace(/\\beta/g, 'β');
    text = text.replace(/\\gamma/g, 'γ');
    text = text.replace(/\\delta/g, 'δ');
    text = text.replace(/\\epsilon/g, 'ε');
    text = text.replace(/\\zeta/g, 'ζ');
    text = text.replace(/\\eta/g, 'η');
    text = text.replace(/\\theta/g, 'θ');
    text = text.replace(/\\iota/g, 'ι');
    text = text.replace(/\\kappa/g, 'κ');
    text = text.replace(/\\lambda/g, 'λ');
    text = text.replace(/\\mu/g, 'μ');
    text = text.replace(/\\nu/g, 'ν');
    text = text.replace(/\\xi/g, 'ξ');
    text = text.replace(/\\omicron/g, 'ο');
    text = text.replace(/\\rho/g, 'ρ');
    text = text.replace(/\\sigma/g, 'σ');
    text = text.replace(/\\tau/g, 'τ');
    text = text.replace(/\\upsilon/g, 'υ');
    text = text.replace(/\\phi/g, 'φ');
    text = text.replace(/\\chi/g, 'χ');
    text = text.replace(/\\psi/g, 'ψ');
    text = text.replace(/\\omega/g, 'ω');
    
    // ARROW SYMBOLS
    text = text.replace(/\\rightarrow/g, '→');
    text = text.replace(/\\leftarrow/g, '←');
    text = text.replace(/\\leftrightarrow/g, '↔');
    text = text.replace(/\\Rightarrow/g, '⇒');
    text = text.replace(/\\Leftarrow/g, '⇐');
    text = text.replace(/\\uparrow/g, '↑');
    text = text.replace(/\\downarrow/g, '↓');
    
    // SET SYMBOLS
    text = text.replace(/\\in/g, '∈');
    text = text.replace(/\\notin/g, '∉');
    text = text.replace(/\\subset/g, '⊂');
    text = text.replace(/\\supset/g, '⊃');
    text = text.replace(/\\subseteq/g, '⊆');
    text = text.replace(/\\supseteq/g, '⊇');
    text = text.replace(/\\cup/g, '∪');
    text = text.replace(/\\cap/g, '∩');
    text = text.replace(/\\mathbb\{N\}/g, 'ℕ');
    text = text.replace(/\\mathbb\{Z\}/g, 'ℤ');
    text = text.replace(/\\mathbb\{Q\}/g, 'ℚ');
    text = text.replace(/\\mathbb\{R\}/g, 'ℝ');
    text = text.replace(/\\mathbb\{C\}/g, 'ℂ');
    
    // LOGICAL SYMBOLS
    text = text.replace(/\\land/g, '∧');
    text = text.replace(/\\lor/g, '∨');
    text = text.replace(/\\neg/g, '¬');
    
    return text;
}

function addMessage(role, content) {
    const messagesList = document.getElementById('messagesList');
    
    // Create message element
    const messageEl = document.createElement('div');
    messageEl.className = `message ${role}`;
    
    const contentEl = document.createElement('div');
    contentEl.className = 'message-content';
    
    // Parse and render markdown for assistant messages
    if (role === 'assistant') {
        // Clean up LaTeX notation first
        const cleanedContent = cleanMathNotation(content);
        contentEl.innerHTML = marked.parse(cleanedContent);
    } else {
        // User messages as plain text
        contentEl.textContent = content;
    }
    
    messageEl.appendChild(contentEl);
    
    // Add time
    const timeEl = document.createElement('div');
    timeEl.className = 'message-time';
    timeEl.textContent = new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
    messageEl.appendChild(timeEl);
    
    messagesList.appendChild(messageEl);
    
    // Scroll to bottom
    document.getElementById('messagesContainer').scrollTop = document.getElementById('messagesContainer').scrollHeight;
}

function showLoadingIndicator() {
    const messagesList = document.getElementById('messagesList');
    const messageEl = document.createElement('div');
    messageEl.className = 'message assistant';
    messageEl.id = 'loadingIndicator';
    
    const contentEl = document.createElement('div');
    contentEl.className = 'message-content loading';
    contentEl.innerHTML = '<span></span><span></span><span></span>';
    
    messageEl.appendChild(contentEl);
    messagesList.appendChild(messageEl);
    
    document.getElementById('messagesContainer').scrollTop = document.getElementById('messagesContainer').scrollHeight;
}

function removeLoadingIndicator() {
    const loadingEl = document.getElementById('loadingIndicator');
    if (loadingEl) {
        loadingEl.remove();
    }
}

function updateChatTitle(context, material = null) {
    let title = context;
    
    // If material filename is provided, use it as title
    if (material) {
        title = material.split('/').pop(); // Get filename from path
    } else if (context && context.length > 0) {
        // Extract first sentence or question from context
        const sentences = context.split(/[.!?]/)[0]; // Get first sentence
        title = sentences.substring(0, 50) + (sentences.length > 50 ? '...' : '');
    }
    
    // Clean up common prefixes
    title = title.replace(/^(Analyzing:|Analyzing )/i, '').trim();
    
    document.getElementById('chatTitle').textContent = title || 'Chat';
    
    // Show today's date as subtitle only
    const today = new Date();
    document.getElementById('chatSubtitle').textContent = today.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
}

function startNewChat() {
    currentSessionId = null;

    // Clear message list
    document.getElementById('messagesList').innerHTML = '';

    // Rebuild welcome section inside messagesContainer (not messagesList)
    const container = document.getElementById('messagesContainer');
    const existing = container.querySelector('.welcome-section');
    if (existing) existing.remove();

    const welcomeDiv = document.createElement('div');
    welcomeDiv.className = 'welcome-section';
    welcomeDiv.innerHTML = `
        <div class="welcome-icon">
            <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm0 18c-4.41 0-8-3.59-8-8s3.59-8 8-8 8 3.59 8 8-3.59 8-8 8z"/>
            </svg>
        </div>
        <h2>Hey there! 👋</h2>
        <p>I'm your personal AI study assistant. Upload your study materials to get started.</p>
        <div class="quick-actions">
            <button type="button" class="action-card" onclick="showUploadPanel()">
                <svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                    <path d="M12 2v20M2 12h20"/>
                </svg>
                <div><h3>Upload Material</h3><p>PDF, images, and more</p></div>
            </button>
            <button type="button" class="action-card" onclick="document.getElementById('messageInput').focus()">
                <svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                    <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/>
                </svg>
                <div><h3>Ask a Question</h3><p>Get instant help</p></div>
            </button>
        </div>`;

    // Insert before messagesList so DOM order is correct
    container.insertBefore(welcomeDiv, document.getElementById('messagesList'));

    // Refresh the greeting with logged-in user name
    updateUserProfile();

    document.getElementById('chatTitle').textContent = 'Welcome to LearnBuddy';
    document.getElementById('chatSubtitle').textContent = 'Upload materials and start learning';

    // Close sidebar after starting a new chat
    document.querySelector('.sidebar').classList.remove('open');
}

function loadChatHistory() {
    fetch('/api/chat-history/')
        .then(r => r.json())
        .then(data => {
            const container = document.getElementById('chatListContainer');
            if (data.sessions && data.sessions.length > 0) {
                data.sessions.forEach(session => {
                    // Get first user message as preview
                    const firstMessage = session.messages.find(m => m.type === 'user');
                    const preview = firstMessage ? firstMessage.text.substring(0, 30) + (firstMessage.text.length > 30 ? '...' : '') : 'Chat';
                    const title = session.material ? session.material.split('/').pop() : preview;
                    
                    const item = document.createElement('div');
                    item.className = 'chat-item';
                    item.title = title; // Show full title on hover
                    item.innerHTML = `
                        <div class="chat-item-title">${title}</div>
                        <div class="chat-item-time">${new Date(session.created_at).toLocaleDateString()}</div>
                        <div class="chat-item-preview">${preview}</div>
                    `;
                    item.onclick = () => loadChat(session.session_id);
                    container.appendChild(item);
                });
            }
        })
        .catch(error => console.error('Error loading chat history:', error));
}

function loadChat(sessionId) {
    // Update current session
    currentSessionId = sessionId;
    
    // Mark chat as active in sidebar
    document.querySelectorAll('.chat-item').forEach(item => item.classList.remove('active'));
    event.target.closest('.chat-item').classList.add('active');
    
    // Fetch messages for this session from history
    fetch('/api/chat-history/')
        .then(r => r.json())
        .then(data => {
            const session = data.sessions.find(s => s.session_id === sessionId);
            if (session) {
                // Clear current messages
                document.getElementById('messagesList').innerHTML = '';
                
                // Remove welcome section if present
                const welcomeSection = document.querySelector('.welcome-section');
                if (welcomeSection) {
                    welcomeSection.remove();
                }
                
                // Load all messages from this session
                session.messages.forEach(msg => {
                    addMessage(msg.type, msg.text);
                });
                
                // Update title with material name or first user message
                const firstUserMessage = session.messages.find(m => m.type === 'user');
                const titleContext = firstUserMessage ? firstUserMessage.text : 'Chat';
                updateChatTitle(titleContext, session.material);
            }
        })
        .catch(error => {
            console.error('Error loading chat:', error);
            addMessage('assistant', 'Sorry, I could not load that chat. Please try again.');
        });
}

function checkInitialMessage() {
    const initialMessage = sessionStorage.getItem('initialMessage');
    if (initialMessage) {
        document.getElementById('messageInput').value = initialMessage;
        autoResizeTextarea(document.getElementById('messageInput'));
        sessionStorage.removeItem('initialMessage');
        document.getElementById('messageInput').focus();
    }
}

function toggleSidebar() {
    document.querySelector('.sidebar').classList.toggle('open');
}

function toggleProfileDropdown() {
    const dropdown = document.getElementById('profileDropdown');
    const btn = document.getElementById('profileBtn');
    const isActive = dropdown.classList.toggle('active');
    btn.classList.toggle('dropdown-open', isActive);
}

function toggleTheme() {
    const isLight = document.body.classList.toggle('light-mode');
    localStorage.setItem('learnbuddy-theme', isLight ? 'light' : 'dark');
    const label = document.getElementById('themeLabel');
    if (label) label.textContent = isLight ? 'Dark Mode' : 'Light Mode';
}

function loadTheme() {
    const saved = localStorage.getItem('learnbuddy-theme');
    if (saved === 'light') {
        document.body.classList.add('light-mode');
        const label = document.getElementById('themeLabel');
        if (label) label.textContent = 'Dark Mode';
    }
}

// Close profile dropdown and sidebar when clicking outside
document.addEventListener('click', (e) => {
    const profileSection = document.querySelector('.profile-section');
    if (profileSection && !profileSection.contains(e.target)) {
        const dropdown = document.getElementById('profileDropdown');
        const btn = document.getElementById('profileBtn');
        if (dropdown) dropdown.classList.remove('active');
        if (btn) btn.classList.remove('dropdown-open');
    }

    // Close sidebar when clicking in the main area (not the toggle or the sidebar itself)
    const sidebar = document.querySelector('.sidebar');
    const toggle = document.querySelector('.menu-toggle');
    if (sidebar && sidebar.classList.contains('open') &&
        !sidebar.contains(e.target) && !toggle?.contains(e.target)) {
        sidebar.classList.remove('open');
    }
});

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
