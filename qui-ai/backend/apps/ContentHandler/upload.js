// Enhanced upload.js with MCQ integration
// Add this to your HTML file, replace the existing handleSubmit function

// Configuration
const API_BASE_URL = 'http://localhost:8000/api/v1';

// Enhanced handleSubmit function with MCQ support
const handleSubmit = async () => {
    if (!selectedFile || selectedServices.length === 0) {
        alert('Please select a file and at least one service.');
        return;
    }

    try {
        // Show loading state
        const submitButton = document.querySelector('button[onclick="handleSubmit()"]');
        if (submitButton) {
            submitButton.disabled = true;
            submitButton.textContent = 'Uploading...';
        }

        // Create FormData for file upload
        const formData = new FormData();
        formData.append('file', selectedFile);

        // Upload file
        const uploadResponse = await fetch(`${API_BASE_URL}/upload`, {
            method: 'POST',
            body: formData
        });

        if (!uploadResponse.ok) {
            throw new Error(`Upload failed: ${uploadResponse.statusText}`);
        }

        const uploadData = await uploadResponse.json();

        if (!uploadData.success) {
            throw new Error(uploadData.error || 'Upload failed');
        }

        const sessionId = uploadData.session_id;
        const documentId = uploadData.document_id; // Assuming this is returned from upload

        // Store session ID and services for later use
        const uploadRecord = {
            id: sessionId,
            documentId: documentId,
            fileName: selectedFile.name,
            date: new Date().toLocaleDateString(),
            services: selectedServices,
            status: 'processing',
            serviceResults: {}
        };

        // Add to upload history in localStorage
        updateUploadHistory(uploadRecord);

        // Show success modal
        setIsModalOpen(true);

        // Start processing each selected service
        await processSelectedServices(documentId, sessionId, selectedServices);

        // Start polling for status updates
        pollProcessingStatus(sessionId);

    } catch (error) {
        console.error('Upload error:', error);
        alert(`Upload failed: ${error.message}`);
    } finally {
        // Reset button
        const submitButton = document.querySelector('button[onclick="handleSubmit()"]');
        if (submitButton) {
            submitButton.disabled = false;
            submitButton.textContent = 'Generate';
        }
    }
};

// Process selected services (including MCQ generation)
const processSelectedServices = async (documentId, sessionId, services) => {
    console.log(`Processing services for document ${documentId}:`, services);

    // Process each service
    for (const service of services) {
        try {
            switch (service) {
                case 'mcq':
                    await startMCQGeneration(documentId, sessionId);
                    break;
                case 'rephrase':
                    await startRephraseGeneration(documentId, sessionId);
                    break;
                case 'flashcards':
                    await startFlashcardGeneration(documentId, sessionId);
                    break;
                case 'summary':
                    await startSummaryGeneration(documentId, sessionId);
                    break;
                default:
                    console.warn(`Unknown service: ${service}`);
            }
        } catch (error) {
            console.error(`Error starting ${service} generation:`, error);
            updateServiceStatus(sessionId, service, 'failed', error.message);
        }
    }
};

// MCQ Generation Functions
const startMCQGeneration = async (documentId, sessionId) => {
    console.log(`Starting MCQ generation for document ${documentId}`);

    try {
        const response = await fetch(`${API_BASE_URL}/mcq/generate/${documentId}?session_id=${sessionId}`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            }
        });

        if (!response.ok) {
            throw new Error(`MCQ generation failed: ${response.statusText}`);
        }

        const data = await response.json();

        if (data.success) {
            console.log(`MCQ generation started with session ${data.session_id}`);
            updateServiceStatus(sessionId, 'mcq', 'processing');

            // Start polling MCQ status
            pollMCQStatus(data.session_id, sessionId);
        } else {
            throw new Error(data.message || 'MCQ generation failed');
        }

    } catch (error) {
        console.error('MCQ generation error:', error);
        updateServiceStatus(sessionId, 'mcq', 'failed', error.message);
        throw error;
    }
};

// Poll MCQ generation status
const pollMCQStatus = async (mcqSessionId, uploadSessionId) => {
    let attempts = 0;
    const maxAttempts = 60; // 5 minutes with 5-second intervals

    const poll = async () => {
        try {
            attempts++;
            console.log(`Polling MCQ status for ${mcqSessionId}, attempt ${attempts}`);

            const statusResponse = await fetch(`${API_BASE_URL}/mcq/status/${mcqSessionId}`);

            if (!statusResponse.ok) {
                console.warn(`MCQ status check failed: ${statusResponse.statusText}`);
                return;
            }

            const statusData = await statusResponse.json();
            console.log(`MCQ Status for ${mcqSessionId}:`, statusData);

            // Update service status based on MCQ progress
            if (statusData.status === 'completed') {
                console.log(`MCQ generation completed for ${mcqSessionId}`);
                updateServiceStatus(uploadSessionId, 'mcq', 'completed');
                showNotification(`MCQ generation completed! Generated ${statusData.mcq_count || 0} questions.`, 'success');
                return;
            }

            if (statusData.status === 'failed') {
                console.error(`MCQ generation failed for ${mcqSessionId}:`, statusData.error);
                updateServiceStatus(uploadSessionId, 'mcq', 'failed', statusData.error);
                showNotification('MCQ generation failed', 'error');
                return;
            }

            if (statusData.status === 'processing') {
                updateServiceStatus(uploadSessionId, 'mcq', 'processing', null, {
                    progress: statusData.progress,
                    stage: statusData.stage,
                    mcq_count: statusData.mcq_count
                });
            }

            // Continue polling if not complete and within max attempts
            if (attempts < maxAttempts) {
                setTimeout(poll, 5000);
            } else {
                console.warn(`Max polling attempts reached for MCQ ${mcqSessionId}`);
                updateServiceStatus(uploadSessionId, 'mcq', 'timeout');
            }

        } catch (error) {
            console.error(`MCQ status polling error for ${mcqSessionId}:`, error);
            if (attempts < maxAttempts) {
                setTimeout(poll, 5000);
            }
        }
    };

    // Start polling after a short delay
    setTimeout(poll, 2000);
};

// Fetch MCQs for a document
const fetchMCQsForDocument = async (documentId) => {
    try {
        const response = await fetch(`${API_BASE_URL}/mcq/document/${documentId}`);

        if (!response.ok) {
            throw new Error(`Failed to fetch MCQs: ${response.statusText}`);
        }

        const mcqs = await response.json();
        return mcqs;

    } catch (error) {
        console.error('Error fetching MCQs:', error);
        throw error;
    }
};

// Get MCQ statistics
const getMCQStatistics = async (documentId) => {
    try {
        const response = await fetch(`${API_BASE_URL}/mcq/statistics/${documentId}`);

        if (!response.ok) {
            throw new Error(`Failed to fetch MCQ statistics: ${response.statusText}`);
        }

        const stats = await response.json();
        return stats;

    } catch (error) {
        console.error('Error fetching MCQ statistics:', error);
        throw error;
    }
};

// Update MCQ
const updateMCQ = async (mcqId, updates) => {
    try {
        const response = await fetch(`${API_BASE_URL}/mcq/${mcqId}`, {
            method: 'PUT',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(updates)
        });

        if (!response.ok) {
            throw new Error(`Failed to update MCQ: ${response.statusText}`);
        }

        const updatedMCQ = await response.json();
        return updatedMCQ;

    } catch (error) {
        console.error('Error updating MCQ:', error);
        throw error;
    }
};

// Delete MCQ
const deleteMCQ = async (mcqId) => {
    try {
        const response = await fetch(`${API_BASE_URL}/mcq/${mcqId}`, {
            method: 'DELETE'
        });

        if (!response.ok) {
            throw new Error(`Failed to delete MCQ: ${response.statusText}`);
        }

        const result = await response.json();
        return result;

    } catch (error) {
        console.error('Error deleting MCQ:', error);
        throw error;
    }
};

// Placeholder functions for other services (implement as needed)
const startRephraseGeneration = async (documentId, sessionId) => {
    console.log(`Rephrase generation not implemented yet for document ${documentId}`);
    updateServiceStatus(sessionId, 'rephrase', 'pending');
};

const startFlashcardGeneration = async (documentId, sessionId) => {
    console.log(`Flashcard generation not implemented yet for document ${documentId}`);
    updateServiceStatus(sessionId, 'flashcards', 'pending');
};

const startSummaryGeneration = async (documentId, sessionId) => {
    console.log(`Summary generation not implemented yet for document ${documentId}`);
    updateServiceStatus(sessionId, 'summary', 'pending');
};

// Enhanced service status management
const updateServiceStatus = (sessionId, service, status, error = null, metadata = null) => {
    const userData = JSON.parse(localStorage.getItem('Q.Ai_userData') || '{}');
    if (userData.uploadHistory) {
        const record = userData.uploadHistory.find(item => item.id === sessionId);
        if (record) {
            if (!record.serviceResults) {
                record.serviceResults = {};
            }

            record.serviceResults[service] = {
                status: status,
                error: error,
                metadata: metadata,
                updated_at: new Date().toISOString()
            };

            // Update overall status based on service statuses
            const serviceStatuses = Object.values(record.serviceResults).map(r => r.status);
            if (serviceStatuses.every(s => s === 'completed')) {
                record.status = 'completed';
            } else if (serviceStatuses.some(s => s === 'failed')) {
                record.status = 'partial'; // Some services failed
            } else if (serviceStatuses.some(s => s === 'processing')) {
                record.status = 'processing';
            }

            localStorage.setItem('Q.Ai_userData', JSON.stringify(userData));

            // Update UI
            if (typeof setUploadHistory === 'function') {
                setUploadHistory([...userData.uploadHistory]);
            }
        }
    }
};

// Function to update upload history (enhanced)
const updateUploadHistory = (uploadRecord) => {
    const userData = JSON.parse(localStorage.getItem('Q.Ai_userData') || '{}');
    if (!userData.uploadHistory) {
        userData.uploadHistory = [];
    }

    // Add new record at the beginning
    userData.uploadHistory.unshift(uploadRecord);

    // Keep only last 20 records
    userData.uploadHistory = userData.uploadHistory.slice(0, 20);

    localStorage.setItem('Q.Ai_userData', JSON.stringify(userData));

    // Update UI immediately
    if (typeof setUploadHistory === 'function') {
        setUploadHistory([...userData.uploadHistory]);
    }
};

// Enhanced polling for overall processing status
const pollProcessingStatus = async (sessionId) => {
    let attempts = 0;
    const maxAttempts = 60;

    const poll = async () => {
        try {
            attempts++;
            console.log(`Polling overall status for ${sessionId}, attempt ${attempts}`);

            // Check if all services are complete by looking at localStorage
            const userData = JSON.parse(localStorage.getItem('Q.Ai_userData') || '{}');
            const record = userData.uploadHistory?.find(item => item.id === sessionId);

            if (record && record.serviceResults) {
                const serviceStatuses = Object.values(record.serviceResults).map(r => r.status);
                const allComplete = serviceStatuses.every(s => s === 'completed' || s === 'failed');

                if (allComplete) {
                    console.log(`All services completed for ${sessionId}`);

                    const completedCount = serviceStatuses.filter(s => s === 'completed').length;
                    const failedCount = serviceStatuses.filter(s => s === 'failed').length;

                    if (completedCount > 0) {
                        showNotification(
                            `Processing complete! ${completedCount} service(s) succeeded${failedCount > 0 ? `, ${failedCount} failed` : ''}.`,
                            failedCount === 0 ? 'success' : 'warning'
                        );
                    }
                    return;
                }
            }

            // Continue polling if not all complete and within max attempts
            if (attempts < maxAttempts) {
                setTimeout(poll, 5000);
            } else {
                console.warn(`Max polling attempts reached for overall status ${sessionId}`);
                updateUploadRecordStatus(sessionId, 'timeout');
            }

        } catch (error) {
            console.error(`Overall status polling error for ${sessionId}:`, error);
            if (attempts < maxAttempts) {
                setTimeout(poll, 5000);
            }
        }
    };

    setTimeout(poll, 2000);
};

// Function to update specific upload record status
const updateUploadRecordStatus = (sessionId, status) => {
    const userData = JSON.parse(localStorage.getItem('Q.Ai_userData') || '{}');
    if (userData.uploadHistory) {
        const record = userData.uploadHistory.find(item => item.id === sessionId);
        if (record) {
            record.status = status;
            localStorage.setItem('Q.Ai_userData', JSON.stringify(userData));

            // Update UI
            if (typeof setUploadHistory === 'function') {
                setUploadHistory([...userData.uploadHistory]);
            }
        }
    }
};

// Function to show notifications
const showNotification = (message, type = 'info') => {
    const notification = document.createElement('div');
    notification.style.cssText = `
        position: fixed;
        top: 80px;
        right: 20px;
        padding: 15px 20px;
        border-radius: 8px;
        color: white;
        font-weight: bold;
        z-index: 1000;
        max-width: 300px;
        background-color: ${
            type === 'success' ? '#10b981' :
            type === 'error' ? '#ef4444' :
            type === 'warning' ? '#f59e0b' :
            '#3b82f6'
        };
        animation: slideIn 0.3s ease-out;
    `;

    notification.textContent = message;
    document.body.appendChild(notification);

    setTimeout(() => {
        notification.style.animation = 'slideOut 0.3s ease-in';
        setTimeout(() => {
            if (notification.parentNode) {
                notification.parentNode.removeChild(notification);
            }
        }, 300);
    }, 5000);
};

// Enhanced HistoryPanel component with service status indicators
const HistoryPanel = ({ history, onClear }) => (
    <div className="mt-12">
        <div className="flex justify-between items-center mb-4">
            <h2 className="text-3xl font-bold">Your Upload History</h2>
            {history && history.length > 0 && (
                <button onClick={onClear} className="text-sm font-semibold text-gray-400 hover:text-red-500 transition">
                    <i className="fas fa-trash-alt mr-2"></i>Clear History
                </button>
            )}
        </div>
        <div className="space-y-3">
            {history && history.length > 0 ? (
                history.map(item => (
                    <div key={item.id} className="flex justify-between items-center p-4 bg-[#1c1c1c] rounded-lg hover:bg-gray-800/40 transition border border-gray-700">
                        <div className="flex items-center gap-4">
                            <i className="fas fa-file-alt text-2xl text-purple-400"></i>
                            <div className="flex-1">
                                <p className="font-bold text-white">{item.fileName}</p>
                                <p className="text-sm text-gray-400">{item.date}</p>

                                {/* Overall Status */}
                                <div className="flex items-center gap-2 mt-1">
                                    <span className={`text-xs px-2 py-1 rounded ${
                                        item.status === 'completed' ? 'bg-green-600 text-white' :
                                        item.status === 'processing' ? 'bg-blue-600 text-white' :
                                        item.status === 'partial' ? 'bg-yellow-600 text-white' :
                                        item.status === 'failed' ? 'bg-red-600 text-white' :
                                        'bg-gray-600 text-white'
                                    }`}>
                                        {item.status || 'pending'}
                                    </span>
                                    {item.status === 'processing' && (
                                        <i className="fas fa-spinner fa-spin text-blue-400"></i>
                                    )}
                                </div>

                                {/* Service Status Indicators */}
                                {item.serviceResults && (
                                    <div className="flex flex-wrap gap-1 mt-2">
                                        {Object.entries(item.serviceResults).map(([service, result]) => (
                                            <span key={service} className={`text-xs px-2 py-1 rounded capitalize ${
                                                result.status === 'completed' ? 'bg-green-500 text-white' :
                                                result.status === 'processing' ? 'bg-blue-500 text-white' :
                                                result.status === 'failed' ? 'bg-red-500 text-white' :
                                                'bg-gray-500 text-white'
                                            }`} title={result.error || `${service}: ${result.status}`}>
                                                {service}
                                                {result.status === 'processing' && result.metadata?.progress &&
                                                    ` (${result.metadata.progress}%)`
                                                }
                                            </span>
                                        ))}
                                    </div>
                                )}
                            </div>
                        </div>
                        <div className="flex items-center gap-3">
                            {(item.status === 'completed' || item.status === 'partial') && (
                                <a
                                    href={`ResultsPage.html?id=${item.id}`}
                                    className="text-green-400 hover:text-green-300"
                                    title="View Results"
                                >
                                    <i className="fas fa-eye"></i>
                                </a>
                            )}
                            <i className="fas fa-chevron-right text-gray-500"></i>
                        </div>
                    </div>
                ))
            ) : (
                <div className="text-gray-500 text-center py-8 bg-[#1c1c1c] rounded-lg border border-gray-700">
                    You haven't uploaded any documents yet.
                </div>
            )}
        </div>
    </div>
);

// Function to fetch document results (enhanced for ResultsPage.html)
const fetchDocumentResults = async (sessionId) => {
    try {
        // Get upload record from localStorage
        const userData = JSON.parse(localStorage.getItem('Q.Ai_userData') || '{}');
        const uploadRecord = userData.uploadHistory?.find(item => item.id === sessionId);

        if (!uploadRecord) {
            throw new Error('Upload record not found');
        }

        const results = {
            uploadInfo: uploadRecord,
            services: {}
        };

        // Fetch results for each completed service
        if (uploadRecord.serviceResults) {
            for (const [service, result] of Object.entries(uploadRecord.serviceResults)) {
                if (result.status === 'completed') {
                    try {
                        switch (service) {
                            case 'mcq':
                                results.services.mcq = await fetchMCQsForDocument(uploadRecord.documentId);
                                results.services.mcqStats = await getMCQStatistics(uploadRecord.documentId);
                                break;
                            case 'rephrase':
                                // Implement when rephrase API is ready
                                results.services.rephrase = { message: 'Rephrase service not implemented' };
                                break;
                            case 'flashcards':
                                // Implement when flashcards API is ready
                                results.services.flashcards = { message: 'Flashcards service not implemented' };
                                break;
                            case 'summary':
                                // Implement when summary API is ready
                                results.services.summary = { message: 'Summary service not implemented' };
                                break;
                        }
                    } catch (error) {
                        console.error(`Error fetching ${service} results:`, error);
                        results.services[service] = { error: error.message };
                    }
                }
            }
        }

        return results;

    } catch (error) {
        console.error('Error fetching document results:', error);
        throw error;
    }
};

// Initialize status checking for existing uploads on page load
const initializeStatusChecking = () => {
    const userData = JSON.parse(localStorage.getItem('Q.Ai_userData') || '{}');
    if (userData.uploadHistory) {
        userData.uploadHistory.forEach(item => {
            if (item.status === 'processing') {
                console.log(`Resuming status polling for ${item.id}`);
                pollProcessingStatus(item.id);

                // Resume individual service polling if needed
                if (item.serviceResults) {
                    Object.entries(item.serviceResults).forEach(([service, result]) => {
                        if (result.status === 'processing' && service === 'mcq' && result.metadata?.mcq_session_id) {
                            pollMCQStatus(result.metadata.mcq_session_id, item.id);
                        }
                    });
                }
            }
        });
    }
};

// Call this when the page loads
document.addEventListener('DOMContentLoaded', () => {
    setTimeout(initializeStatusChecking, 1000);
});

// Export enhanced API functions
window.QUI_API = {
    fetchDocumentResults,
    showNotification,
    API_BASE_URL,
    // MCQ specific functions
    fetchMCQsForDocument,
    getMCQStatistics,
    updateMCQ,
    deleteMCQ,
    startMCQGeneration,
    // Service management
    updateServiceStatus,
    pollMCQStatus
};