document.addEventListener('DOMContentLoaded', function() {
    const form = document.getElementById('loginForm') || document.getElementById('signupForm');
    
    if (form) {
        form.addEventListener('submit', function(e) {
            if (form.id === 'signupForm' && !validateSignupForm()) {
                e.preventDefault();
                return;
            }
            const submitBtn = form.querySelector('button[type="submit"]');
            submitBtn.disabled = true;
            submitBtn.textContent = 'Processing...';
        });
    }

    const firstInput = document.querySelector('input[type="text"], input[type="email"]');
    if (firstInput) {
        firstInput.focus();
    }
});

function validateSignupForm() {
    const password = document.getElementById('password');
    const passwordConfirm = document.getElementById('password_confirm');
    
    if (password && passwordConfirm) {
        if (password.value !== passwordConfirm.value) {
            alert('Passwords do not match!');
            return false;
        }
        if (password.value.length < 8) {
            alert('Password must be at least 8 characters long.');
            return false;
        }
        if (!/[a-zA-Z]/.test(password.value)) {
            alert('Password must contain at least one letter.');
            return false;
        }
        if (!/[0-9]/.test(password.value)) {
            alert('Password must contain at least one number.');
            return false;
        }
        if (!/[^a-zA-Z0-9]/.test(password.value)) {
            alert('Password must contain at least one special character (e.g., !, @, #, $, etc.).');
            return false;
        }
    }
    return true;
}
