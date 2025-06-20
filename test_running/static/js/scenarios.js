// Scenarios page functionality

async function loadScenarios() {
    try {
        const response = await fetch('/api/scenarios');
        const data = await response.json();
        const scenariosGrid = document.getElementById('scenariosGrid');
        
        if (data.scenarios && data.scenarios.length > 0) {
            scenariosGrid.innerHTML = data.scenarios.map(scenario => `
                <div class="card">
                    <div class="card-header">
                        <div class="flex items-center justify-between">
                            <h3 class="card-title">${scenario.name}</h3>
                            <span class="badge badge-secondary">${Math.round(scenario.duration_seconds / 60)} min</span>
                        </div>
                        <p class="card-description">${scenario.description}</p>
                    </div>
                    <div class="card-content">
                        <div class="grid grid-cols-2 gap-4 mb-4">
                            <div class="space-y-1">
                                <p class="text-sm font-medium text-muted-foreground">Duration</p>
                                <p class="text-2xl font-bold">${Math.round(scenario.duration_seconds / 60)} min</p>
                            </div>
                            <div class="space-y-1">
                                <p class="text-sm font-medium text-muted-foreground">Max Users</p>
                                <p class="text-2xl font-bold">${scenario.max_concurrent_users}</p>
                            </div>
                        </div>
                    </div>
                    <div class="card-footer">
                        <button class="btn btn-primary w-full" onclick="runScenario('${scenario.name}')" id="btn-${scenario.name}">
                            <i data-lucide="play" class="h-4 w-4 mr-2"></i>
                            Run Scenario
                        </button>
                    </div>
                </div>
            `).join('');
        } else {
            scenariosGrid.innerHTML = `
                <div class="col-span-full">
                    <div class="card">
                        <div class="card-content text-center py-12">
                            <i data-lucide="alert-circle" class="h-12 w-12 text-muted-foreground mx-auto mb-4"></i>
                            <h3 class="text-lg font-semibold mb-2">No Scenarios Available</h3>
                            <p class="text-muted-foreground">No scenarios have been configured.</p>
                        </div>
                    </div>
                </div>
            `;
        }
        
        // Re-initialize icons
        if (typeof lucide !== 'undefined') {
            lucide.createIcons();
        }
    } catch (error) {
        console.error('Error loading scenarios:', error);
        document.getElementById('scenariosGrid').innerHTML = `
            <div class="col-span-full">
                <div class="card">
                    <div class="card-content text-center py-12">
                        <i data-lucide="alert-triangle" class="h-12 w-12 text-destructive mx-auto mb-4"></i>
                        <h3 class="text-lg font-semibold mb-2">Error Loading Scenarios</h3>
                        <p class="text-muted-foreground">Failed to load scenarios. Please try again.</p>
                        <button class="btn btn-outline mt-4" onclick="loadScenarios()">
                            <i data-lucide="refresh-cw" class="h-4 w-4 mr-2"></i>
                            Retry
                        </button>
                    </div>
                </div>
            </div>
        `;
        if (typeof lucide !== 'undefined') {
            lucide.createIcons();
        }
    }
}

async function runScenario(scenarioName) {
    const button = document.getElementById(`btn-${scenarioName}`);
    const originalText = button.innerHTML;
    
    // Update button state
    button.disabled = true;
    button.innerHTML = `
        <i data-lucide="loader-2" class="h-4 w-4 mr-2 animate-spin"></i>
        Starting...
    `;
    
    try {
        const response = await fetch(`/api/run/${scenarioName}`, {
            method: 'POST'
        });
        
        if (response.ok) {
            const result = await response.json();
            
            // Show success notification
            if (typeof showNotification !== 'undefined') {
                showNotification(`Scenario ${scenarioName} started successfully!`, 'success');
            }
            
            // Update button to show running state
            button.innerHTML = `
                <i data-lucide="check-circle" class="h-4 w-4 mr-2 text-green-500"></i>
                Running
            `;
            button.className = 'btn btn-secondary w-full';
            
            // Automatically navigate to dashboard after a short delay
            setTimeout(() => {
                window.location.href = '/dashboard';
            }, 1500);
            
        } else {
            const error = await response.text();
            button.disabled = false;
            button.innerHTML = originalText;
            if (typeof showNotification !== 'undefined') {
                showNotification(`Failed to start scenario: ${error}`, 'error');
            }
        }
    } catch (error) {
        button.disabled = false;
        button.innerHTML = originalText;
        if (typeof showNotification !== 'undefined') {
            showNotification(`Error starting scenario: ${error.message}`, 'error');
        }
    }
    
    // Re-initialize icons
    if (typeof lucide !== 'undefined') {
        lucide.createIcons();
    }
}

// Load scenarios on page load
document.addEventListener('DOMContentLoaded', function() {
    if (window.location.pathname === '/scenarios') {
        loadScenarios();
    }
}); 