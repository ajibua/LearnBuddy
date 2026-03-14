// Modern Chat Interface
let currentFile = null;
let chatSessions = [];
let currentSessionId = null;
let isLoading = false;
let currentPreviewUrl = null;

// ---- Document Viewer State ----
let currentMaterialUrl = null;
let currentMaterialType = null;
let currentMaterialName = null;

// Initialize
document.addEventListener('DOMContentLoaded', () => {
    document.body.classList.add('light-mode');  // always use light mode
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
            if (currentFile) {
                processFile({ messageSource: 'mainInput' });
            } else {
                sendMessage();
            }
        }
    });
    messageInput.addEventListener('input', () => autoResizeTextarea(messageInput));
    messageInput.addEventListener('paste', handleClipboardPaste);

    const fileMessageInput = document.getElementById('fileMessage');
    fileMessageInput.addEventListener('keydown', (e) => {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            processFile({ messageSource: 'fileInput' });
        }
    });
    fileMessageInput.addEventListener('paste', handleClipboardPaste);

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
    document.addEventListener('paste', handleClipboardPaste);

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

function isSupportedUploadFile(file) {
    if (!file) return false;

    const supportedExtensions = ['.pdf', '.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp', '.docx', '.txt'];
    const supportedMimePrefixes = ['image/'];
    const supportedMimes = ['application/pdf', 'text/plain'];

    const fileType = (file.type || '').toLowerCase();
    if (supportedMimes.includes(fileType) || supportedMimePrefixes.some((prefix) => fileType.startsWith(prefix))) {
        return true;
    }

    if (!file.name) return false;
    const lowerName = file.name.toLowerCase();

    return supportedExtensions.some((extension) => lowerName.endsWith(extension));
}

function extensionFromMimeType(mimeType) {
    const type = (mimeType || '').toLowerCase();
    if (type === 'image/png') return '.png';
    if (type === 'image/jpeg' || type === 'image/jpg') return '.jpg';
    if (type === 'image/webp') return '.webp';
    if (type === 'image/gif') return '.gif';
    if (type === 'image/bmp') return '.bmp';
    if (type === 'application/pdf') return '.pdf';
    if (type === 'text/plain') return '.txt';
    return '';
}

function ensureNamedFile(file, fallbackPrefix = 'pasted-file') {
    if (!file) return null;

    const hasName = !!file.name;
    const hasExtension = hasName && file.name.includes('.');
    if (hasName && hasExtension) return file;

    const extension = extensionFromMimeType(file.type);
    const generatedName = `${fallbackPrefix}-${Date.now()}${extension}`;

    try {
        return new File([file], generatedName, {
            type: file.type || 'application/octet-stream',
            lastModified: Date.now(),
        });
    } catch (error) {
        // Older browsers may not support File constructor.
        file.name = generatedName;
        return file;
    }
}

function dataUrlToFile(dataUrl, fallbackPrefix = 'pasted-image') {
    if (!dataUrl || !dataUrl.startsWith('data:')) return null;

    const parts = dataUrl.split(',');
    if (parts.length < 2) return null;

    const meta = parts[0];
    const base64Data = parts[1];
    const mimeMatch = meta.match(/^data:([^;]+);base64$/i);
    const mimeType = mimeMatch ? mimeMatch[1].toLowerCase() : 'image/png';

    try {
        const binaryString = atob(base64Data);
        const bytes = new Uint8Array(binaryString.length);
        for (let i = 0; i < binaryString.length; i += 1) {
            bytes[i] = binaryString.charCodeAt(i);
        }

        const extension = extensionFromMimeType(mimeType) || '.png';
        const fileName = `${fallbackPrefix}-${Date.now()}${extension}`;
        return new File([bytes], fileName, { type: mimeType, lastModified: Date.now() });
    } catch (error) {
        console.error('Failed to convert pasted image data URL:', error);
        return null;
    }
}

function syncFileInput(file) {
    const fileInput = document.getElementById('fileInput');
    if (!fileInput || !file || typeof DataTransfer === 'undefined') return;

    const dataTransfer = new DataTransfer();
    dataTransfer.items.add(file);
    fileInput.files = dataTransfer.files;
}

function releasePreviewUrl() {
    if (currentPreviewUrl) {
        URL.revokeObjectURL(currentPreviewUrl);
        currentPreviewUrl = null;
    }
}

function setPendingFile(file, options = {}) {
    if (!file || !isSupportedUploadFile(file)) {
        addMessage('assistant', 'That file type is not supported yet. Use PDF, images, DOCX, or TXT.');
        return;
    }

    const { openPanel = true } = options;
    currentFile = file;
    syncFileInput(file);

    // Format file size
    const fileSize = file.size < 1024 * 1024
        ? (file.size / 1024).toFixed(0) + ' KB'
        : (file.size / 1024 / 1024).toFixed(2) + ' MB';

    document.getElementById('fileName').textContent = file.name;
    document.getElementById('fileSize').textContent = fileSize;
    document.getElementById('fileInfo').style.display = 'flex';
    document.getElementById('fileMessageArea').style.display = 'block';

    const previewEl = document.getElementById('localPreview');
    previewEl.innerHTML = '';
    const isImage = file.type.startsWith('image/');

    releasePreviewUrl();

    if (isImage) {
        const img = document.createElement('img');
        currentPreviewUrl = URL.createObjectURL(file);
        img.src = currentPreviewUrl;
        img.alt = file.name;
        previewEl.appendChild(img);
    } else {
        const isPdf = file.name.toLowerCase().endsWith('.pdf');
        const isDoc = file.name.toLowerCase().match(/\.(docx|txt)$/);
        const iconColor = isPdf ? '#ef4444' : '#3b82f6';
        const label = isPdf ? 'PDF Document' : isDoc ? 'Document' : 'File';
        previewEl.innerHTML = `
            <div class="pdf-thumb">
                <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="${iconColor}" stroke-width="1.5">
                    <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/>
                    <polyline points="14 2 14 8 20 8"/>
                    <line x1="16" y1="13" x2="8" y2="13"/>
                    <line x1="16" y1="17" x2="8" y2="17"/>
                    <polyline points="10 9 9 9 8 9"/>
                </svg>
                <span>${file.name}</span>
                <small>${label} · ${fileSize}</small>
            </div>`;
    }

    previewEl.style.display = 'flex';
    document.getElementById('processBtn').style.display = 'block';

    if (openPanel) {
        showUploadPanel();
    }
}

function getClipboardFile(clipboardData) {
    if (!clipboardData) return null;

    if (clipboardData.files && clipboardData.files.length > 0) {
        const directFile = Array.from(clipboardData.files)
            .map((file) => ensureNamedFile(file, 'clipboard-file'))
            .find(isSupportedUploadFile);
        if (directFile) return directFile;
    }

    if (!clipboardData.items) return null;

    for (const item of clipboardData.items) {
        if (item.kind === 'file') {
            const file = item.getAsFile();
            if (!file) continue;

            const normalized = ensureNamedFile(file, 'pasted-file');
            if (isSupportedUploadFile(normalized)) {
                return normalized;
            }
        }

        if (item.kind === 'string' && item.type === 'text/html') {
            // Some apps place screenshots as HTML with data URLs.
            // We cannot synchronously read getAsString, so skip here and use async fallback in handler.
            continue;
        }
    }

    return null;
}

async function getClipboardFileFromAsyncApi() {
    if (!navigator.clipboard || !navigator.clipboard.read) return null;

    try {
        const clipboardItems = await navigator.clipboard.read();
        for (const clipboardItem of clipboardItems) {
            for (const mimeType of clipboardItem.types) {
                if (!mimeType.startsWith('image/') && mimeType !== 'application/pdf' && mimeType !== 'text/plain') {
                    continue;
                }

                const blob = await clipboardItem.getType(mimeType);
                const candidate = ensureNamedFile(blob, 'clipboard-api');
                if (isSupportedUploadFile(candidate)) {
                    return candidate;
                }
            }
        }
    } catch (error) {
        // Permission denied or browser policy; keep silent fallback behavior.
        console.debug('Async clipboard API not available for file paste:', error);
    }

    return null;
}

function getHtmlDataImage(clipboardData) {
    if (!clipboardData || !clipboardData.getData) return null;
    const html = clipboardData.getData('text/html');
    if (!html) return null;

    const dataImageMatch = html.match(/src=["'](data:image\/[a-zA-Z0-9.+-]+;base64,[^"']+)["']/i);
    if (!dataImageMatch) return null;

    return dataUrlToFile(dataImageMatch[1], 'pasted-html-image');
}

async function handleClipboardPaste(e) {
    let clipboardFile = getClipboardFile(e.clipboardData);

    if (!clipboardFile) {
        clipboardFile = getHtmlDataImage(e.clipboardData);
    }

    if (!clipboardFile) {
        clipboardFile = await getClipboardFileFromAsyncApi();
    }

    if (!clipboardFile) return;

    e.preventDefault();
    setPendingFile(clipboardFile, { openPanel: true });
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

    setPendingFile(file, { openPanel: false });
}

function clearFile() {
    currentFile = null;
    releasePreviewUrl();
    document.getElementById('fileInput').value = '';
    document.getElementById('fileInfo').style.display = 'none';
    document.getElementById('fileMessageArea').style.display = 'none';
    document.getElementById('fileMessage').value = '';
    document.getElementById('processBtn').style.display = 'none';
    const previewEl = document.getElementById('localPreview');
    if (previewEl) { previewEl.innerHTML = ''; previewEl.style.display = 'none'; }
}

async function processFile(options = {}) {
    if (!currentFile || isLoading) return;

    const { messageSource = 'fileInput' } = options;
    const fileMessageInput = document.getElementById('fileMessage');
    const mainMessageInput = document.getElementById('messageInput');
    const userMessage = messageSource === 'mainInput'
        ? (mainMessageInput?.value || '').trim()
        : (fileMessageInput?.value || '').trim();

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
        ? `Attached: ${currentFile.name}\n\n${userMessage}`
        : `Attached: ${currentFile.name}`;
    addMessage('user', bubbleContent);
    isLoading = true;

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

            closeUploadPanel();
            clearFile();
            if (messageSource === 'mainInput' && mainMessageInput) {
                mainMessageInput.value = '';
                mainMessageInput.style.height = 'auto';
            } else if (fileMessageInput) {
                fileMessageInput.value = '';
            }
            
            // Add assistant message with summary
            addMessage('assistant', `**${data.filename}** uploaded successfully!\n\n**Summary:**\n\n${data.summary}\n\nFeel free to ask me any questions about this material!`);
            updateChatTitle(data.filename, data.filename);

            // Open the document viewer with the uploaded file
            if (data.file_url) {
                openDocViewer(data.file_url, data.file_type || 'pdf', data.filename);
            }
        } else {
            addMessage('assistant', `Error: ${data.error}`);
        }
    } catch (error) {
        removeLoadingIndicator();
        addMessage('assistant', 'Error uploading file. Please try again.');
        console.error('Error:', error);
    } finally {
        isLoading = false;
    }
}

async function sendMessage() {
    if (currentFile) {
        return processFile({ messageSource: 'mainInput' });
    }

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
            const replyText = data.response && data.response.trim()
                ? data.response
                : "Hey there! 👋 I'm LearnBuddy. What would you like to learn today?";
            addMessage('assistant', replyText, data.message_id);
            // CRITICAL: persist the real DB session_id for conversation continuity
            if (data.session_id) {
                currentSessionId = data.session_id;
            }
            // Use AI-generated title if returned (first exchange only), else fall back to user message
            if (data.session_title) {
                updateChatTitle(data.session_title);
                // Also update the matching sidebar item so it reflects the new title immediately
                updateSidebarTitle(data.session_id, data.session_title);
            } else {
                updateChatTitle(message);
            }
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

// Render message content: protect LaTeX from marked, then render with KaTeX
function renderMessageContent(content) {
    const mathBlocks = [];

    // Extract $$...$$ display math
    let processed = content.replace(/\$\$([\s\S]+?)\$\$/g, (match) => {
        const idx = mathBlocks.length;
        mathBlocks.push({ src: match, display: true });
        return `\x02MATH${idx}\x03`;
    });

    // Extract $...$ inline math (single-line only)
    processed = processed.replace(/\$([^\$\n]+?)\$/g, (match) => {
        const idx = mathBlocks.length;
        mathBlocks.push({ src: match, display: false });
        return `\x02MATH${idx}\x03`;
    });

    // Parse markdown (LaTeX is protected as placeholders)
    let html = marked.parse(processed);

    // Restore math placeholders with rendered KaTeX
    html = html.replace(/\x02MATH(\d+)\x03/g, (_, i) => {
        const block = mathBlocks[parseInt(i)];
        try {
            // Strip outer $ delimiters before rendering
            const tex = block.display
                ? block.src.slice(2, -2).trim()
                : block.src.slice(1, -1).trim();
            return katex.renderToString(tex, { displayMode: block.display, throwOnError: false });
        } catch (e) {
            return block.src; // fall back to raw LaTeX on error
        }
    });

    return html;
}

function addMessage(role, content, messageId = null) {
    const messagesList = document.getElementById('messagesList');
    
    const messageEl = document.createElement('div');
    messageEl.className = `message ${role}`;
    if (messageId) messageEl.dataset.messageId = messageId;
    
    if (role === 'assistant') {
        // Column wrapper: bubble → actions → time
        const bodyEl = document.createElement('div');
        bodyEl.className = 'message-body';

        const contentEl = document.createElement('div');
        contentEl.className = 'message-content';
        contentEl.innerHTML = renderMessageContent(content);
        bodyEl.appendChild(contentEl);

        const actionsEl = document.createElement('div');
        actionsEl.className = 'message-actions';
        actionsEl.innerHTML = `
            <button class="action-btn feedback-btn" data-value="up" title="Good response" onclick="submitFeedback(this)">
                <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M14 9V5a3 3 0 0 0-3-3l-4 9v11h11.28a2 2 0 0 0 2-1.7l1.38-9a2 2 0 0 0-2-2.3H14z"/><path d="M7 22H4a2 2 0 0 1-2-2v-7a2 2 0 0 1 2-2h3"/></svg>
            </button>
            <button class="action-btn feedback-btn" data-value="down" title="Poor response" onclick="submitFeedback(this)">
                <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M10 15v4a3 3 0 0 0 3 3l4-9V2H5.72a2 2 0 0 0-2 1.7l-1.38 9a2 2 0 0 0 2 2.3H10z"/><path d="M17 2h2.67A2.31 2.31 0 0 1 22 4v7a2.31 2.31 0 0 1-2.33 2H17"/></svg>
            </button>
            <button class="action-btn regenerate-btn" title="Get another response" onclick="regenerateResponse(this)">
                <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M23 4v6h-6"/><path d="M20.49 15a9 9 0 1 1-2.12-9.36L23 10"/></svg>
            </button>
        `;
        bodyEl.appendChild(actionsEl);

        const timeEl = document.createElement('div');
        timeEl.className = 'message-time';
        timeEl.textContent = new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
        bodyEl.appendChild(timeEl);

        messageEl.appendChild(bodyEl);
    } else {
        const contentEl = document.createElement('div');
        contentEl.className = 'message-content';
        contentEl.textContent = content;
        messageEl.appendChild(contentEl);

        const timeEl = document.createElement('div');
        timeEl.className = 'message-time';
        timeEl.textContent = new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
        messageEl.appendChild(timeEl);
    }
    
    messagesList.appendChild(messageEl);
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
        // Trim if too long (only needed for raw message fallback)
        title = context.substring(0, 60) + (context.length > 60 ? '...' : '');
    }
    
    // Clean up common prefixes
    title = title.replace(/^(Analyzing:|Analyzing )/i, '').trim();
    
    document.getElementById('chatTitle').textContent = title || 'Chat';
    
    // Show today's date as subtitle only
    const today = new Date();
    document.getElementById('chatSubtitle').textContent = today.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
}

function updateSidebarTitle(sessionId, title) {
    // Find the sidebar chat-item that matches this session and update its title
    document.querySelectorAll('.chat-item').forEach(item => {
        if (item.dataset.sessionId == sessionId) {
            const titleEl = item.querySelector('.chat-item-title');
            if (titleEl) titleEl.textContent = title;
            item.title = title;
        }
    });
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

    // Close the document viewer when starting a fresh chat
    closeDocViewer();

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
                    // Prefer AI-generated title, fall back to first user message
                    const firstMessage = session.messages.find(m => m.type === 'user');
                    const preview = firstMessage ? firstMessage.text.substring(0, 30) + (firstMessage.text.length > 30 ? '...' : '') : 'Chat';
                    const title = session.material
                        ? session.material.split('/').pop()
                        : (session.title || preview);
                    
                    const item = document.createElement('div');
                    item.className = 'chat-item';
                    item.dataset.sessionId = session.session_id;
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
                    addMessage(msg.type, msg.text, msg.type === 'assistant' ? msg.id : null);
                });
                
                // Update title with stored title, material name, or first user message
                const firstUserMessage = session.messages.find(m => m.type === 'user');
                const titleContext = session.title || (firstUserMessage ? firstUserMessage.text : 'Chat');
                updateChatTitle(titleContext, session.material);

                // Re-open document viewer if the session has a material
                if (session.material_url) {
                    openDocViewer(session.material_url, session.material_type || 'pdf', session.material ? session.material.split('/').pop() : 'Document');
                } else {
                    closeDocViewer();
                }
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

async function submitFeedback(btn) {
    const messageEl = btn.closest('.message');
    const messageId = messageEl?.dataset.messageId;
    if (!messageId) return;

    const value = btn.dataset.value; // 'up' or 'down'

    // Visual state
    messageEl.querySelectorAll('.feedback-btn').forEach(b => b.classList.remove('active'));
    btn.classList.add('active');

    try {
        await fetch(`/api/feedback/${messageId}/`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': getCookie('csrftoken'),
            },
            body: JSON.stringify({ feedback: value }),
        });
    } catch (e) {
        console.error('Feedback error:', e);
    }
}

async function regenerateResponse(btn) {
    if (isLoading) return;
    if (!currentSessionId) return;

    const messageEl = btn.closest('.message');

    // Replace content with loading dots
    const contentEl = messageEl.querySelector('.message-content');
    const originalHTML = contentEl.innerHTML;
    contentEl.innerHTML = '<span class="regen-loading"></span>';
    btn.disabled = true;
    isLoading = true;

    try {
        const response = await fetch('/api/regenerate/', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': getCookie('csrftoken'),
            },
            body: JSON.stringify({ session_id: currentSessionId }),
        });

        if (response.ok) {
            const data = await response.json();
            contentEl.innerHTML = renderMessageContent(data.response);
            if (data.message_id) messageEl.dataset.messageId = data.message_id;
            // Reset any previous feedback highlight
            messageEl.querySelectorAll('.feedback-btn').forEach(b => b.classList.remove('active'));
        } else {
            contentEl.innerHTML = originalHTML;
        }
    } catch (e) {
        contentEl.innerHTML = originalHTML;
        console.error('Regenerate error:', e);
    } finally {
        btn.disabled = false;
        isLoading = false;
    }
}

// Close profile dropdown
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

// ========== DOCUMENT VIEWER ==========

function openDocViewer(url, fileType, filename) {
    currentMaterialUrl = url;
    currentMaterialType = fileType;
    currentMaterialName = filename;

    const viewer = document.getElementById('docViewer');
    const body = document.getElementById('docViewerBody');
    const nameEl = document.getElementById('docViewerName');
    const iconEl = document.getElementById('docViewerIcon');
    const btn = document.getElementById('viewDocBtn');

    const name = filename ? filename.split('/').pop() : 'Document';
    if (nameEl) nameEl.textContent = name;

    // Set icon based on type
    const isImage = fileType === 'image';
    if (iconEl) {
        iconEl.innerHTML = isImage
            ? `<svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="#3b82f6" stroke-width="2"><rect x="3" y="3" width="18" height="18" rx="2"/><circle cx="8.5" cy="8.5" r="1.5"/><polyline points="21 15 16 10 5 21"/></svg>`
            : `<svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="#ef4444" stroke-width="2"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/></svg>`;
    }

    // Build viewer content
    body.innerHTML = '';
    if (isImage) {
        const img = document.createElement('img');
        img.src = url;
        img.alt = name;
        body.appendChild(img);
    } else {
        // PDF / document — embed in iframe with browser's built-in viewer
        const iframe = document.createElement('iframe');
        iframe.src = url;
        iframe.title = name;
        iframe.setAttribute('allowfullscreen', '');
        body.appendChild(iframe);
    }

    viewer.classList.add('open');

    if (btn) {
        btn.style.display = 'flex';
        btn.classList.add('active');
    }
}

function closeDocViewer() {
    const viewer = document.getElementById('docViewer');
    const btn = document.getElementById('viewDocBtn');

    viewer.classList.remove('open');

    if (btn) {
        btn.classList.remove('active');
        // Only hide the button if there's no current material
        if (!currentMaterialUrl) btn.style.display = 'none';
    }
}

function toggleDocViewer() {
    const viewer = document.getElementById('docViewer');
    if (viewer.classList.contains('open')) {
        closeDocViewer();
    } else if (currentMaterialUrl) {
        openDocViewer(currentMaterialUrl, currentMaterialType, currentMaterialName);
    }
}

// ========== COOKIES ==========

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
