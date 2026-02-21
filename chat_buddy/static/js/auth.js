// Auth page functionality
document.addEventListener('DOMContentLoaded', function() {
    const form = document.getElementById('loginForm') || document.getElementById('signupForm');
    
    if (form) {
        form.addEventListener('submit', function(e) {
            const submitBtn = form.querySelector('button[type="submit"]');
            submitBtn.disabled = true;
            submitBtn.textContent = 'Processing...';
        });
    }

    // Focus on first input field
    const firstInput = document.querySelector('input[type="text"], input[type="email"]');
    if (firstInput) {
        firstInput.focus();
    }
});

// Form validation for signup
function validateSignupForm() {
    const password = document.getElementById('password');
    const passwordConfirm = document.getElementById('password_confirm');
    
    if (password && passwordConfirm) {
        if (password.value !== passwordConfirm.value) {
            alert('Passwords do not match!');
            return false;
        }
        if (password.value.length < 6) {
            alert('Password must be at least 6 characters long');
            return false;
        }
    }
    return true;
}
