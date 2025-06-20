// Base JavaScript functionality for the missile defense test runner

// Theme management
let currentTheme = localStorage.getItem('theme') || 'light';

// Initialize theme
function initializeTheme() {
    const html = document.documentElement;
    const themeIcon = document.getElementById('themeIcon');
    
    if (currentTheme === 'dark') {
        html.classList.add('dark');
        if (themeIcon) {
            themeIcon.setAttribute('data-lucide', 'moon');
        }
    } else {
        html.classList.remove('dark');
        if (themeIcon) {
            themeIcon.setAttribute('data-lucide', 'sun');
        }
    }
    
    // Re-initialize icons
    if (typeof lucide !== 'undefined') {
        lucide.createIcons();
    }
}

// Toggle theme
function toggleTheme() {
    const html = document.documentElement;
    const themeIcon = document.getElementById('themeIcon');
    
    if (currentTheme === 'light') {
        currentTheme = 'dark';
        html.classList.add('dark');
        if (themeIcon) {
            themeIcon.setAttribute('data-lucide', 'moon');
        }
    } else {
        currentTheme = 'light';
        html.classList.remove('dark');
        if (themeIcon) {
            themeIcon.setAttribute('data-lucide', 'sun');
        }
    }
    
    localStorage.setItem('theme', currentTheme);
    
    // Re-initialize icons
    if (typeof lucide !== 'undefined') {
        lucide.createIcons();
    }
}

// Initialize Lucide icons
function initializeIcons() {
    if (typeof lucide !== 'undefined') {
        lucide.createIcons();
    }
}

// Show notification function
function showNotification(message, type = 'info') {
    // Create notification element
    const notification = document.createElement('div');
    notification.className = `fixed top-4 right-4 z-50 p-4 rounded-lg shadow-lg border max-w-sm ${
        type === 'success' ? 'bg-green-50 border-green-200 text-green-800 dark:bg-green-900/20 dark:border-green-800 dark:text-green-400' :
        type === 'error' ? 'bg-red-50 border-red-200 text-red-800 dark:bg-red-900/20 dark:border-red-800 dark:text-red-400' :
        'bg-blue-50 border-blue-200 text-blue-800 dark:bg-blue-900/20 dark:border-blue-800 dark:text-blue-400'
    }`;
    
    notification.innerHTML = `
        <div class="flex items-center space-x-2">
            <i data-lucide="${type === 'success' ? 'check-circle' : type === 'error' ? 'alert-circle' : 'info'}" class="h-5 w-5"></i>
            <span class="font-medium">${message}</span>
        </div>
    `;
    
    document.body.appendChild(notification);
    initializeIcons();
    
    // Remove notification after 5 seconds
    setTimeout(() => {
        notification.remove();
    }, 5000);
}

// Refresh status function
function refreshStatus() {
    fetch('/api/status')
        .then(response => response.json())
        .then(data => {
            const lastUpdateElement = document.getElementById('lastUpdate');
            if (lastUpdateElement) {
                lastUpdateElement.textContent = new Date().toLocaleTimeString();
            }
            
            // Update status indicator if it exists
            const statusIndicator = document.querySelector('.status-indicator');
            if (statusIndicator) {
                statusIndicator.className = `status-indicator status-${data.test_status}`;
                
                // Update status text
                const statusText = statusIndicator.nextElementSibling;
                if (statusText) {
                    statusText.textContent = data.test_status.charAt(0).toUpperCase() + data.test_status.slice(1);
                }
            }
            
            // Reload page if there are new results
            if (data.scenario_results && !window.currentResults) {
                window.currentResults = data.scenario_results;
                location.reload();
            }
        })
        .catch(error => {
            console.error('Error refreshing status:', error);
        });
}

// Initialize base functionality when DOM is loaded
document.addEventListener('DOMContentLoaded', function() {
    initializeTheme();
    initializeIcons();
    
    // Set up auto-refresh for status page
    if (window.location.pathname === '/status') {
        setInterval(refreshStatus, 5000);
    }
}); 