// Dashboard functionality

let map;
let pollingInterval;
let autoRefresh = true;
let showTrajectories = true;
let showEvents = true;
let mapInitialized = false;

// Initialize map
async function initializeMap() {
    try {
        // Get scenario bounds first
        const boundsResponse = await fetch('/api/scenario/bounds');
        const boundsData = await boundsResponse.json();
        
        map = new maplibregl.Map({
            container: 'map',
            style: 'https://basemaps.cartocdn.com/gl/positron-gl-style/style.json',
            center: boundsData.center,
            zoom: boundsData.zoom
        });
        
        // Add navigation controls
        map.addControl(new maplibregl.NavigationControl());
        
        // Add fullscreen control
        map.addControl(new maplibregl.FullscreenControl());
        
        // Initialize data sources
        let missileSource = {
            type: 'geojson',
            data: {
                type: 'FeatureCollection',
                features: []
            }
        };
        
        let defenseSource = {
            type: 'geojson',
            data: {
                type: 'FeatureCollection',
                features: []
            }
        };
        
        let radarSource = {
            type: 'geojson',
            data: {
                type: 'FeatureCollection',
                features: []
            }
        };
        
        let eventSource = {
            type: 'geojson',
            data: {
                type: 'FeatureCollection',
                features: []
            }
        };
        
        // Add sources to map
        map.on('load', function() {
            map.addSource('missiles', missileSource);
            map.addSource('defenses', defenseSource);
            map.addSource('radars', radarSource);
            map.addSource('events', eventSource);
            
            // Add layers
            map.addLayer({
                id: 'missiles',
                type: 'circle',
                source: 'missiles',
                paint: {
                    'circle-radius': 8,
                    'circle-color': '#ef4444',
                    'circle-stroke-width': 2,
                    'circle-stroke-color': '#ffffff'
                }
            });
            
            map.addLayer({
                id: 'defenses',
                type: 'circle',
                source: 'defenses',
                paint: {
                    'circle-radius': 10,
                    'circle-color': '#10b981',
                    'circle-stroke-width': 2,
                    'circle-stroke-color': '#ffffff'
                }
            });
            
            map.addLayer({
                id: 'radars',
                type: 'circle',
                source: 'radars',
                paint: {
                    'circle-radius': 12,
                    'circle-color': '#3b82f6',
                    'circle-stroke-width': 2,
                    'circle-stroke-color': '#ffffff'
                }
            });
            
            map.addLayer({
                id: 'events',
                type: 'circle',
                source: 'events',
                paint: {
                    'circle-radius': 6,
                    'circle-color': [
                        'case',
                        ['==', ['get', 'type'], 'detection'], '#f59e0b',
                        ['==', ['get', 'type'], 'detonation'], '#ef4444',
                        ['==', ['get', 'type'], 'intercept'], '#8b5cf6',
                        '#6b7280'
                    ],
                    'circle-stroke-width': 2,
                    'circle-stroke-color': '#ffffff'
                }
            });
            
            // Set bounds if available
            if (boundsData.bounds && boundsData.bounds[0][0] !== 0) {
                map.fitBounds(boundsData.bounds, {
                    padding: 50,
                    duration: 1000
                });
            }
            
            mapInitialized = true;
            
            // Load initial data
            loadData();
        });
    } catch (error) {
        console.error('Error initializing map:', error);
        document.getElementById('map').innerHTML = '<div class="text-center py-8 text-red-600">Error loading map. Please refresh the page.</div>';
    }
}

async function loadData() {
    try {
        // Load missile positions
        const missileResponse = await fetch('/api/metrics/missile_positions');
        if (missileResponse.ok) {
            const missileData = await missileResponse.json();
            updateMissileData(missileData);
        }
        
        // Load defense positions
        const defenseResponse = await fetch('/api/metrics/defense_positions');
        if (defenseResponse.ok) {
            const defenseData = await defenseResponse.json();
            updateDefenseData(defenseData);
        }
        
        // Load radar positions
        const radarResponse = await fetch('/api/metrics/radar_positions');
        if (radarResponse.ok) {
            const radarData = await radarResponse.json();
            updateRadarData(radarData);
        }
        
        // Load events
        const eventResponse = await fetch('/api/metrics/events');
        if (eventResponse.ok) {
            const eventData = await eventResponse.json();
            updateEventData(eventData);
        }
        
    } catch (error) {
        console.error('Error loading data:', error);
        const eventTable = document.getElementById('eventTable');
        if (eventTable) {
             eventTable.innerHTML = `
                <div class="text-center py-8 text-amber-600 dark:text-amber-400">
                    <i data-lucide="shield-alert" class="h-8 w-8 mx-auto mb-2"></i>
                    <h3 class="font-semibold">Could not load data</h3>
                    <p class="text-sm">Failed to fetch monitoring data. This might be caused by a network issue or a browser extension (like an ad-blocker). Please check your connection, browser extensions, and try again.</p>
                </div>
            `;
            if (typeof lucide !== 'undefined') {
                lucide.createIcons();
            }
        }
    }
}

function updateMissileData(data) {
    if (!mapInitialized || !map.getSource('missiles')) return;
    
    const features = data.map(item => ({
        type: 'Feature',
        geometry: {
            type: 'Point',
            coordinates: decodePosition(item.value)
        },
        properties: {
            id: item.labels.missile_id,
            status: item.labels.status
        }
    }));
    
    map.getSource('missiles').setData({
        type: 'FeatureCollection',
        features: features
    });
    
    document.getElementById('activeMissiles').textContent = features.length;
}

function updateDefenseData(data) {
    if (!mapInitialized || !map.getSource('defenses')) return;
    
    const features = data.map(item => ({
        type: 'Feature',
        geometry: {
            type: 'Point',
            coordinates: decodePosition(item.value)
        },
        properties: {
            id: item.labels.defense_id,
            status: item.labels.status
        }
    }));
    
    map.getSource('defenses').setData({
        type: 'FeatureCollection',
        features: features
    });
    
    document.getElementById('activeDefenses').textContent = features.length;
}

function updateRadarData(data) {
    if (!mapInitialized || !map.getSource('radars')) return;
    
    const features = data.map(item => ({
        type: 'Feature',
        geometry: {
            type: 'Point',
            coordinates: decodePosition(item.value)
        },
        properties: {
            id: item.labels.radar_id,
            status: item.labels.status
        }
    }));
    
    map.getSource('radars').setData({
        type: 'FeatureCollection',
        features: features
    });
    
    document.getElementById('radarInstallations').textContent = features.length;
}

function updateEventData(data) {
    if (!mapInitialized || !map.getSource('events')) return;
    
    const features = data.map(item => ({
        type: 'Feature',
        geometry: {
            type: 'Point',
            coordinates: decodePosition(item.value)
        },
        properties: {
            type: item.labels.event_type,
            timestamp: item.labels.timestamp
        }
    }));
    
    map.getSource('events').setData({
        type: 'FeatureCollection',
        features: features
    });
    
    document.getElementById('totalEvents').textContent = features.length;
    
    // Update event table
    updateEventTable(data);
}

function updateEventTable(data) {
    if (data.length === 0) {
        document.getElementById('eventTable').innerHTML = '<div class="text-center py-8 text-muted-foreground">No events recorded yet. Start a scenario to see events.</div>';
        return;
    }
    
    const table = `
        <div class="overflow-x-auto">
            <table class="w-full">
                <thead>
                    <tr class="border-b">
                        <th class="text-left p-2">Time</th>
                        <th class="text-left p-2">Type</th>
                        <th class="text-left p-2">Location</th>
                        <th class="text-left p-2">Details</th>
                    </tr>
                </thead>
                <tbody>
                    ${data.slice(0, 50).map(item => {
                        const coords = decodePosition(item.value);
                        return `
                            <tr class="border-b hover:bg-gray-50">
                                <td class="p-2">${new Date(item.labels.timestamp).toLocaleTimeString()}</td>
                                <td class="p-2">
                                    <span class="inline-block w-2 h-2 rounded-full mr-2 bg-${getEventColor(item.labels.event_type)}"></span>
                                    ${item.labels.event_type}
                                </td>
                                <td class="p-2">${coords[1].toFixed(4)}, ${coords[0].toFixed(4)}</td>
                                <td class="p-2">${item.labels.details || '-'}</td>
                            </tr>
                        `;
                    }).join('')}
                </tbody>
            </table>
        </div>
    `;
    
    document.getElementById('eventTable').innerHTML = table;
}

function getEventColor(eventType) {
    switch(eventType) {
        case 'detection': return 'yellow-500';
        case 'detonation': return 'red-500';
        case 'intercept': return 'purple-500';
        default: return 'gray-500';
    }
}

function decodePosition(encodedValue) {
    // Decode the position from the encoded float value
    const lat = Math.floor(encodedValue / 1000000) / 10000;
    const lon = (encodedValue % 1000000) / 10000;
    return [lon, lat];
}

function updatePollingRate() {
    const rate = parseInt(document.getElementById('pollingRate').value);
    if (pollingInterval) {
        clearInterval(pollingInterval);
    }
    if (autoRefresh) {
        pollingInterval = setInterval(loadData, rate * 1000);
    }
}

function toggleAutoRefresh() {
    autoRefresh = document.getElementById('autoRefresh').value === 'true';
    if (autoRefresh) {
        const rate = parseInt(document.getElementById('pollingRate').value);
        pollingInterval = setInterval(loadData, rate * 1000);
    } else {
        if (pollingInterval) {
            clearInterval(pollingInterval);
        }
    }
}

function toggleTrajectories() {
    showTrajectories = document.getElementById('showTrajectories').value === 'true';
    // Implementation for trajectory display
}

function toggleEvents() {
    showEvents = document.getElementById('showEvents').value === 'true';
    // Implementation for event display
}

function refreshData() {
    loadData();
}

// Initialize dashboard when DOM is loaded
document.addEventListener('DOMContentLoaded', function() {
    if (window.location.pathname === '/dashboard') {
        initializeMap();
        updatePollingRate();
    }
}); 