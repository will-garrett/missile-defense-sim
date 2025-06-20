// Status page functionality

function refreshStatus() {
    fetch('/api/status')
        .then(response => response.json())
        .then(data => {
            const lastUpdateElement = document.getElementById('lastUpdate');
            if (lastUpdateElement) {
                lastUpdateElement.textContent = new Date().toLocaleTimeString();
            }

            // Update status indicator
            const statusIndicator = document.getElementById('statusIndicator');
            const statusText = document.getElementById('statusText');
            if (statusIndicator && statusText && data.test_status) {
                statusIndicator.className = `status-indicator status-${data.test_status}`;
                statusText.textContent = data.test_status.charAt(0).toUpperCase() + data.test_status.slice(1);
            }

            // Update scenario name
            const scenarioElement = document.getElementById('currentScenario');
            if (scenarioElement) {
                scenarioElement.textContent = data.current_scenario || 'N/A';
            }

            // Show/hide stop button
            const stopButton = document.getElementById('stopButton');
            if (stopButton) {
                if (data.test_status === 'running') {
                    stopButton.style.display = 'flex';
                } else {
                    stopButton.style.display = 'none';
                }
            }

            // Update active tests container
            const activeTestsContainer = document.getElementById('activeTestsContainer');
            if (activeTestsContainer) {
                if (data.active_tests && data.active_tests.length > 0) {
                    activeTestsContainer.innerHTML = data.active_tests.map(test => `
                        <div class="flex items-center justify-between p-4 border rounded-lg dark:border-gray-700">
                            <div class="flex items-center space-x-3">
                                <i data-lucide="activity" class="h-5 w-5 text-green-500"></i>
                                <div>
                                    <h4 class="font-semibold">${test.name}</h4>
                                    <p class="text-sm text-muted-foreground">${test.status} • Started at ${new Date(test.start_time).toLocaleTimeString()}</p>
                                </div>
                            </div>
                            <span class="badge badge-secondary">${test.status}</span>
                        </div>
                    `).join('');
                } else {
                    activeTestsContainer.innerHTML = `
                        <div class="text-center py-12">
                            <i data-lucide="inbox" class="h-12 w-12 text-muted-foreground mx-auto mb-4"></i>
                            <h3 class="text-lg font-semibold mb-2">No Active Tests</h3>
                            <p class="text-muted-foreground mb-4">No tests are currently running.</p>
                            <a href="/scenarios" class="btn btn-primary">
                                <i data-lucide="play" class="h-4 w-4 mr-2"></i>
                                Start a Test
                            </a>
                        </div>
                    `;
                }
                if (typeof lucide !== 'undefined') {
                    lucide.createIcons();
                }
            }
        })
        .catch(error => {
            console.error('Error refreshing status:', error);
        });
}

async function stopScenario() {
    try {
        const response = await fetch('/api/scenarios/stop', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            }
        });

        if (response.ok) {
            showNotification('Scenario stopped successfully', 'success');
            setTimeout(refreshStatus, 500);
        } else {
            const error = await response.json();
            showNotification(`Failed to stop scenario: ${error.detail}`, 'error');
        }
    } catch (error) {
        console.error('Error stopping scenario:', error);
        showNotification('Error stopping scenario', 'error');
    }
}

// Initialize status page
document.addEventListener('DOMContentLoaded', function() {
    if (window.location.pathname === '/status') {
        refreshStatus();
        setInterval(refreshStatus, 5000);
    }
}); 