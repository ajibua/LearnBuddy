document.addEventListener('DOMContentLoaded', () => {
    const savedTheme = localStorage.getItem('theme') || 'dark';
    if (savedTheme === 'light') {
        document.body.classList.add('light-mode');
        document.documentElement.classList.add('light-mode');
    }
    const toggleButtons = document.querySelectorAll('.theme-toggle-btn');
    toggleButtons.forEach(btn => {
        btn.addEventListener('click', () => {
            const isLight = document.body.classList.toggle('light-mode');
            if (isLight) {
                document.documentElement.classList.add('light-mode');
                localStorage.setItem('theme', 'light');
            } else {
                document.documentElement.classList.remove('light-mode');
                localStorage.setItem('theme', 'dark');
            }
        });
    });
});
