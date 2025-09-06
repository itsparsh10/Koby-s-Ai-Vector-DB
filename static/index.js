// Modern AI Product Search Assistant JavaScript
document.addEventListener('DOMContentLoaded', function() {
    // DOM elements
    const questionInput = document.getElementById('question');
    const searchButton = document.getElementById('searchButton');
    const voiceButton = document.getElementById('voiceButton');
    const imageButton = document.getElementById('imageButton');
    const statusIndicator = document.getElementById('statusIndicator');
    const statusText = document.getElementById('statusText');
    const resultsContent = document.getElementById('resultsContent');
    const samplePrompts = document.querySelectorAll('[data-prompt]');

    // Voice recognition setup
    let recognition = null;
    let isListening = false;

    if ('webkitSpeechRecognition' in window || 'SpeechRecognition' in window) {
        const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
        recognition = new SpeechRecognition();
        recognition.continuous = false;
        recognition.interimResults = true;
        recognition.lang = 'en-US';

        recognition.onstart = () => {
            isListening = true;
            updateVoiceButton();
            showVoiceIndicator();
        };

        recognition.onresult = (event) => {
            let transcript = '';
            for (let i = event.resultIndex; i < event.results.length; i++) {
                transcript += event.results[i][0].transcript;
            }
            questionInput.value = transcript;
        };

        recognition.onend = () => {
            isListening = false;
            updateVoiceButton();
            hideVoiceIndicator();
            
            // Auto-search if we have text
            if (questionInput.value.trim()) {
                handleSearch();
            }
        };

        recognition.onerror = (event) => {
            isListening = false;
            updateVoiceButton();
            hideVoiceIndicator();
            
            let errorMessage = 'Voice recognition error occurred.';
            if (event.error === 'not-allowed') {
                errorMessage = 'Microphone access denied. Please allow microphone access and try again.';
            } else if (event.error === 'no-speech') {
                errorMessage = 'No speech detected. Please try again.';
            }
            showError(errorMessage);
        };
    } else {
        // Hide voice button if not supported
        if (voiceButton) {
            voiceButton.style.display = 'none';
        }
    }

    // Event listeners
    searchButton.addEventListener('click', handleSearch);
    questionInput.addEventListener('keypress', (e) => {
        if (e.key === 'Enter') {
            e.preventDefault();
            handleSearch();
        }
    });

    voiceButton.addEventListener('click', async () => {
        // Check authentication status before proceeding with voice search
        try {
            const authResponse = await fetch('/api/auth/check/');
            const authData = await authResponse.json();
            
            if (!authData.success || !authData.authenticated) {
                // User is not authenticated, show message and redirect to login
                showError('Please login to use the voice search functionality');
                
                // Show a more prominent message
                const resultsSection = document.getElementById('resultsSection');
                if (resultsSection) {
                    resultsSection.classList.remove('hidden');
                    resultsContent.innerHTML = `
                        <div class="auth-required-message">
                            <div class="auth-icon">
                                <i class="fas fa-lock"></i>
                            </div>
                            <h3>Authentication Required</h3>
                            <p>You need to be logged in to use the voice search functionality.</p>
                            <button onclick="window.location.href='/'" class="auth-login-btn">
                                <i class="fas fa-sign-in-alt"></i>
                                Go to Login
                            </button>
                        </div>
                    `;
                }
                
                // Redirect to login page after 3 seconds
                setTimeout(() => {
                    window.location.href = '/';
                }, 3000);
                
                return;
            }
        } catch (error) {
            console.error('Auth check error:', error);
            showError('Authentication check failed. Please try logging in again.');
            setTimeout(() => {
                window.location.href = '/';
            }, 2000);
            return;
        }

        if (!recognition) {
            showError('Voice recognition is not supported in your browser.');
            return;
        }

        if (isListening) {
            recognition.stop();
        } else {
            try {
                recognition.start();
            } catch (error) {
                showError('Failed to start voice recognition. Please try again.');
            }
        }
    });

    imageButton.addEventListener('click', () => {
        // Create a temporary file input
        const fileInput = document.createElement('input');
        fileInput.type = 'file';
        fileInput.accept = 'image/*';
        fileInput.style.display = 'none';
        
        fileInput.addEventListener('change', (e) => {
            const file = e.target.files[0];
            if (file) {
                uploadAndSearchImage(file);
            }
        });
        
        fileInput.click();
    });

    // Upload and search with image
    async function uploadAndSearchImage(file) {
        // Check authentication status before proceeding with image search
        try {
            const authResponse = await fetch('/api/auth/check/');
            const authData = await authResponse.json();
            
            if (!authData.success || !authData.authenticated) {
                // User is not authenticated, show message and redirect to login
                showError('Please login to use the image search functionality');
                
                // Show a more prominent message
                const resultsSection = document.getElementById('resultsSection');
                if (resultsSection) {
                    resultsSection.classList.remove('hidden');
                    resultsContent.innerHTML = `
                        <div class="auth-required-message">
                            <div class="auth-icon">
                                <i class="fas fa-lock"></i>
                            </div>
                            <h3>Authentication Required</h3>
                            <p>You need to be logged in to use the image search functionality.</p>
                            <button onclick="window.location.href='/'" class="auth-login-btn">
                                <i class="fas fa-sign-in-alt"></i>
                                Go to Login
                            </button>
                        </div>
                    `;
                }
                
                // Redirect to login page after 3 seconds
                setTimeout(() => {
                    window.location.href = '/';
                }, 3000);
                
                return;
            }
        } catch (error) {
            console.error('Auth check error:', error);
            showError('Authentication check failed. Please try logging in again.');
            setTimeout(() => {
                window.location.href = '/';
            }, 2000);
            return;
        }

        // Validate file size (10MB limit)
        if (file.size > 10 * 1024 * 1024) {
            showError('Image file too large. Maximum size is 10MB.');
            return;
        }

        // Validate file type
        if (!file.type.startsWith('image/')) {
            showError('Please select a valid image file.');
            return;
        }

        showImageLoading();
        
        const startTime = Date.now();
        
        try {
            const formData = new FormData();
            formData.append('image', file);
            
            const response = await fetch('/api/image-search/', {
                method: 'POST',
                body: formData
            });
            
            const data = await response.json();
            const processingTime = Date.now() - startTime;
            
            if (data.success && data.answer) {
                showImageSearchResult(data.answer, data.image_description, data.sources, data.processing_time || (processingTime/1000).toFixed(2));
            } else {
                let errorMessage = 'An error occurred while processing your image';
                
                if (data.error) {
                    errorMessage = data.error;
                }
                
                showError(errorMessage);
            }
        } catch (error) {
            const processingTime = Date.now() - startTime;
            showError(`Network error after ${(processingTime/1000).toFixed(2)}s: ${error.message}`);
            console.error('Image search error:', error);
        } finally {
            hideImageLoading();
        }
    }

    // Show image search result
    function showImageSearchResult(answer, imageDescription, sources, processingTime) {
        statusIndicator.classList.add('hidden');
        
        let imageDescriptionHtml = '';
        if (imageDescription) {
            imageDescriptionHtml = `
                <div class="image-analysis">
                    <h4>Image Analysis</h4>
                    <p>${imageDescription}</p>
                </div>
            `;
        }
        
        resultsContent.innerHTML = `
            <div class="image-result">
                <h3><i class="fas fa-image"></i> Image Search Result</h3>
                <div class="result-content">
                    ${formatAnswer(answer)}
                </div>
                ${imageDescriptionHtml}
                ${processingTime ? `<div class="processing-time">Processed in ${processingTime}s</div>` : ''}
            </div>
        `;
        
        resultsContent.classList.remove('hidden');
    }

    // Sample prompt buttons
    samplePrompts.forEach(button => {
        button.addEventListener('click', () => {
            const prompt = button.getAttribute('data-prompt');
            questionInput.value = prompt;
            questionInput.focus();
        });
    });

    // Main search function
    async function handleSearch() {
        const question = questionInput.value.trim();
        
        if (!question) {
            showError('Please enter a question');
            return;
        }

        // Show loading state
        showLoading();
        
        const startTime = Date.now();
        
        try {
            const response = await fetch('/api/ask/', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({ question: question })
            });

            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }

            const data = await response.json();
            const processingTime = Date.now() - startTime;
            
            if (data.success && data.answer) {
                showAnswer(data.answer, data.sources, data.processing_time || (processingTime/1000).toFixed(2));
            } else {
                // Handle API errors
                let errorMessage = 'An error occurred while processing your request';
                
                if (data.error) {
                    errorMessage = data.error;
                    if (data.details) {
                        const detailsArray = Object.values(data.details);
                        if (detailsArray.length > 0) {
                            errorMessage = detailsArray[0];
                        }
                    }
                }
                
                showError(errorMessage);
            }
        } catch (error) {
            console.error('Error:', error);
            let errorMessage = 'An error occurred while processing your request. Please try again.';
            
            if (error.message && error.message.includes('HTTP error! status: 500')) {
                errorMessage = 'Server error occurred. Please check if the AI service is properly configured and try again.';
            } else if (error.message && error.message.includes('HTTP error! status: 404')) {
                errorMessage = 'No relevant information found. Try rephrasing your question or ask about a different topic.';
            }
            
            showError(errorMessage);
        } finally {
            hideLoading();
        }
    }

    // Show loading state
    function showLoading() {
        searchButton.disabled = true;
        searchButton.classList.add('loading');
        searchButton.innerHTML = '<i class="fas fa-spinner fa-spin"></i>';
        
        // Show results section and skeleton loading
        const resultsSection = document.getElementById('resultsSection');
        if (resultsSection) {
            resultsSection.classList.remove('hidden');
        }
        
        // Show skeleton loading
        resultsContent.innerHTML = `
            <div class="skeleton-card">
                <div class="skeleton skeleton-text long"></div>
                <div class="skeleton skeleton-text medium"></div>
                <div class="skeleton skeleton-text short"></div>
                <div style="margin-top: 1rem;">
                    <div class="skeleton skeleton-text medium"></div>
                    <div class="skeleton skeleton-text long"></div>
                </div>
            </div>
            <div class="skeleton-card">
                <div class="skeleton skeleton-text medium"></div>
                <div class="skeleton skeleton-text long"></div>
                <div class="skeleton skeleton-text short"></div>
            </div>
        `;
    }

    function hideLoading() {
        searchButton.disabled = false;
        searchButton.classList.remove('loading');
        searchButton.innerHTML = '<i class="fas fa-search"></i>';
        
        // Ensure status indicator is hidden for text searches
        statusIndicator.classList.add('hidden');
    }

    function showImageLoading() {
        imageButton.disabled = true;
        imageButton.classList.add('loading');
        imageButton.innerHTML = '<i class="fas fa-spinner fa-spin"></i>';
        statusIndicator.classList.remove('hidden');
        statusIndicator.className = 'status-indicator status-uploading';
        statusText.textContent = 'Processing your image...';
        
        // Show results section
        const resultsSection = document.getElementById('resultsSection');
        if (resultsSection) {
            resultsSection.classList.remove('hidden');
        }
        
        resultsContent.innerHTML = `
            <div class="skeleton-card">
                <div style="display: flex; align-items: center; gap: 0.75rem; margin-bottom: 1rem;">
                    <div class="skeleton" style="width: 60px; height: 60px; border-radius: 8px;"></div>
                    <div style="flex: 1;">
                        <div class="skeleton skeleton-text medium"></div>
                        <div class="skeleton skeleton-text short"></div>
                    </div>
                </div>
                <div class="skeleton skeleton-text long"></div>
                <div class="skeleton skeleton-text medium"></div>
                <div class="skeleton skeleton-text short"></div>
            </div>
        `;
    }

    function hideImageLoading() {
         imageButton.disabled = false;
         imageButton.classList.remove('loading');
         imageButton.innerHTML = '<i class="fas fa-image"></i>';
     }

     // Show answer
    function showAnswer(answer, sources, processingTime) {
        // Hide status indicator for text search results
        statusIndicator.classList.add('hidden');
        
        // Ensure results section is visible
        const resultsSection = document.getElementById('resultsSection');
        if (resultsSection) {
            resultsSection.classList.remove('hidden');
        }
        
        resultsContent.innerHTML = `
            <div class="result-card">
                <div class="result-content">
                    ${formatAnswer(answer)}
                </div>
                ${processingTime ? `<div class="processing-time">Processed in ${processingTime}s</div>` : ''}
            </div>
        `;
    }

    // Show error
    function showError(message) {
        // Hide status indicator for errors
        statusIndicator.classList.add('hidden');
        
        // Show results section for errors
        const resultsSection = document.getElementById('resultsSection');
        if (resultsSection) {
            resultsSection.classList.remove('hidden');
        }
        
        resultsContent.innerHTML = `
            <div class="error-card">
                <h3><i class="fas fa-exclamation-triangle"></i> Error</h3>
                <p>${message}</p>
                <div class="error-suggestions">
                    <h4>Suggestions:</h4>
                    <ul>
                        <li>Try rephrasing your question</li>
                        <li>Make sure your question is related to the uploaded documents</li>
                        <li>Check if the system has been properly initialized</li>
                    </ul>
                </div>
            </div>
        `;
    }

    // Format answer for better readability
    function formatAnswer(answer) {
        // Convert markdown-style formatting to HTML with better structure
        let formatted = answer
            .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>') // Bold text
            .replace(/\*(.*?)\*/g, '<em>$1</em>') // Italic text
            .replace(/\n\n/g, '</p><p>') // Double line breaks
            .replace(/\n/g, '<br>'); // Single line breaks
        
        // Add special formatting for menu items and lists
        formatted = formatted
            .replace(/(\*\*.*?\*\*)/g, '<h3 class="menu-title">$1</h3>') // Menu titles
            .replace(/(\*.*?\*\*)/g, '<h4 class="menu-item">$1</h4>') // Menu items
            .replace(/(Medium size|uses|Preparation involves|In a jar)/g, '<span class="detail-label">$1</span>')
            .replace(/(200ml milk|1\/4 scoop of ice|syrup sachet|2 cubes of ice|milkshake pouch|30 seconds)/g, '<span class="detail-value">$1</span>');
        
        return `<div class="formatted-answer">${formatted}</div>`;
    }

    // Voice button update function
    function updateVoiceButton() {
        if (!voiceButton) return;
        
        if (isListening) {
            voiceButton.classList.add('recording');
            voiceButton.innerHTML = '<i class="fas fa-stop"></i>';
        } else {
            voiceButton.classList.remove('recording');
            voiceButton.innerHTML = '<i class="fas fa-microphone"></i>';
        }
    }

    // Show voice indicator
    function showVoiceIndicator() {
        statusIndicator.classList.remove('hidden');
        statusIndicator.className = 'status-indicator status-recording';
        statusText.textContent = 'Listening... Speak now';
    }

    // Hide voice indicator
    function hideVoiceIndicator() {
        statusIndicator.classList.add('hidden');
        statusIndicator.className = 'status-indicator hidden';
    }

    // Generate dynamic prompts based on available data
    function generateDynamicPrompts() {
        const promptsGrid = document.getElementById('dynamicPromptsGrid');
        if (!promptsGrid) return;

        // All possible prompts based on your data
        const allPrompts = [
            {
                question: "What are the available coffee options?",
                icon: "fas fa-coffee",
                label: "Coffee Options"
            },
            {
                question: "Tell me about the bagel varieties",
                icon: "fas fa-bread-slice", 
                label: "Bagel Varieties"
            },
            {
                question: "What sandwich options are available?",
                icon: "fas fa-hamburger",
                label: "Sandwich Menu"
            },
            {
                question: "Show me the milkshake menu",
                icon: "fas fa-glass-whiskey",
                label: "Milkshakes"
            },
            {
                question: "What are the hot coffee varieties?",
                icon: "fas fa-mug-hot",
                label: "Hot Coffees"
            },
            {
                question: "Tell me about the iced coffee options",
                icon: "fas fa-ice-cream",
                label: "Iced Coffees"
            },
            {
                question: "What frappe options do you have?",
                icon: "fas fa-blender",
                label: "Frappes"
            },
            {
                question: "Show me the vegetarian sandwich options",
                icon: "fas fa-leaf",
                label: "Veg Sandwiches"
            },
            {
                question: "What non-vegetarian sandwiches are available?",
                icon: "fas fa-drumstick-bite",
                label: "Non-Veg Sandwiches"
            },
            {
                question: "Tell me about the vegetarian bagel options",
                icon: "fas fa-seedling",
                label: "Veg Bagels"
            },
            {
                question: "What non-vegetarian bagel varieties exist?",
                icon: "fas fa-egg",
                label: "Non-Veg Bagels"
            },
            {
                question: "How are the sandwiches prepared and packed?",
                icon: "fas fa-box",
                label: "Preparation Info"
            }
        ];

        // Shuffle the prompts array
        const shuffledPrompts = allPrompts.sort(() => Math.random() - 0.5);
        
        // Take only 6 prompts (3x2 grid)
        const selectedPrompts = shuffledPrompts.slice(0, 6);
        
        // Generate HTML for the selected prompts
        const promptsHTML = selectedPrompts.map(prompt => `
            <button class="prompt-btn" data-prompt="${prompt.question}">
                <i class="${prompt.icon}"></i>
                <span>${prompt.label}</span>
            </button>
        `).join('');
        
        promptsGrid.innerHTML = promptsHTML;
        
        // Add click event listeners to the new prompt buttons
        addPromptButtonListeners();
    }

    // Add event listeners to prompt buttons
    function addPromptButtonListeners() {
        const promptButtons = document.querySelectorAll('.prompt-btn');
        promptButtons.forEach(button => {
            button.addEventListener('click', () => {
                const prompt = button.getAttribute('data-prompt');
                if (prompt && questionInput) {
                    questionInput.value = prompt;
                    questionInput.focus();
                    // Optionally trigger search automatically
                    // handleSearch();
                }
            });
        });
    }

    // Generate prompts when page loads
    generateDynamicPrompts();

    // Focus on input when page loads
    questionInput.focus();

    // Add some interactive effects
    questionInput.addEventListener('focus', () => {
        questionInput.parentElement.style.transform = 'scale(1.02)';
        questionInput.parentElement.style.boxShadow = '0 25px 50px rgba(0, 0, 0, 0.15)';
    });

    questionInput.addEventListener('blur', () => {
        questionInput.parentElement.style.transform = 'scale(1)';
        questionInput.parentElement.style.boxShadow = '0 20px 40px rgba(0, 0, 0, 0.1)';
    });

    // Drag and drop functionality for images
    const dropZone = document.body;
    let dragCounter = 0;

    dropZone.addEventListener('dragenter', (e) => {
        e.preventDefault();
        dragCounter++;
        if (dragCounter === 1) {
            showDropZone();
        }
    });

    dropZone.addEventListener('dragleave', (e) => {
        e.preventDefault();
        dragCounter--;
        if (dragCounter === 0) {
            hideDropZone();
        }
    });

    dropZone.addEventListener('dragover', (e) => {
        e.preventDefault();
    });

    dropZone.addEventListener('drop', (e) => {
        e.preventDefault();
        dragCounter = 0;
        hideDropZone();
        
        const files = e.dataTransfer.files;
        if (files.length > 0) {
            const file = files[0];
            if (file.type.startsWith('image/')) {
                uploadAndSearchImage(file);
            } else {
                showError('Please drop an image file.');
            }
        }
    });

    // Show drop zone overlay
    function showDropZone() {
        const overlay = document.createElement('div');
        overlay.id = 'drop-overlay';
        overlay.className = 'fixed inset-0 bg-blue-500 bg-opacity-20 flex items-center justify-center z-50 backdrop-blur-sm';
        overlay.innerHTML = `
            <div class="drop-zone">
                <i class="fas fa-image"></i>
                <h3>Drop Image Here</h3>
                <p>Release to search with your image</p>
            </div>
        `;
        document.body.appendChild(overlay);
    }

    // Hide drop zone overlay
    function hideDropZone() {
        const overlay = document.getElementById('drop-overlay');
        if (overlay) {
            overlay.remove();
        }
    }

    // Add hover effects to sample prompts
    samplePrompts.forEach(button => {
        button.addEventListener('mouseenter', () => {
            button.style.transform = 'translateY(-4px)';
            button.style.boxShadow = '0 12px 30px rgba(0, 0, 0, 0.15)';
        });

        button.addEventListener('mouseleave', () => {
            button.style.transform = 'translateY(0)';
            button.style.boxShadow = '0 4px 15px rgba(0, 0, 0, 0.1)';
        });
    });
});
  