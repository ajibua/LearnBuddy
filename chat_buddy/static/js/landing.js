// Random Greetings
const greetings = [
    "Good morning! Ready to learn something new?",
    "Welcome back! Let's dive into your studies.",
    "Hey there! What would you like to explore today?",
    "Great to see you! Your learning journey awaits.",
    "Hello! Let's make today productive.",
    "Welcome! What's on your mind today?",
    "Good to have you here! Ready to grow?",
    "Hey! Let's unlock new knowledge together.",
    "Welcome! Your next breakthrough is waiting.",
    "Hi there! Time to expand your horizons?",
    "Greetings! What shall we discover today?",
    "Welcome back, learner! Let's get started.",
    "Hello! Today is a great day to learn.",
    "Hey! Ready to challenge yourself?",
    "Welcome! Knowledge is just one question away."
];

// Initialize landing page
document.addEventListener('DOMContentLoaded', function() {
    const isAuthenticated = document.body.dataset.authenticated === 'true';
    
    if (!isAuthenticated) {
        displayRandomGreeting();
        // Change greeting every 30 seconds for non-authenticated users
        setInterval(() => {
            displayRandomGreeting();
        }, 30000);
    }
    
    setupEventListeners();
});

function displayRandomGreeting() {
    const greeting = greetings[Math.floor(Math.random() * greetings.length)];
    const greetingElement = document.getElementById('greetingText');
    
    // Fade out current greeting
    greetingElement.style.opacity = '0';
    
    // After fade, change text and fade in
    setTimeout(() => {
        greetingElement.textContent = greeting;
        greetingElement.style.opacity = '1';
    }, 300);
}

function setupEventListeners() {
    const input = document.getElementById('landingInput');
    
    // Enter to send
    if (input) {
        input.addEventListener('keydown', (e) => {
            if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                handleLandingInput();
            }
        });
    }
}

function autoResizeTextarea(textarea) {
    textarea.style.height = 'auto';
    textarea.style.height = Math.min(textarea.scrollHeight, 200) + 'px';
}

function handleLandingInput() {
    const input = document.getElementById('landingInput');
    const message = input.value.trim();
    
    if (message) {
        // Store the message and redirect to chat
        sessionStorage.setItem('initialMessage', message);
        // Redirect to chat page (we'll create this route)
        window.location.href = '/chat/';
        input.value = '';
    }
}

function quickAction(action) {
    if (action === 'upload') {
        // Redirect to chat page for upload
        window.location.href = '/chat/';
    } else if (action === 'auth') {
        // Redirect to login/signup (we'll create this later)
        window.location.href = '/auth/login/';
    }
}
