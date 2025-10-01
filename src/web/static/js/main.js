// Main JavaScript for AI Job Agent

// Global utility functions
function showToast(message, type = 'info') {
    // Create toast element
    const toast = document.createElement('div');
    toast.className = `toast align-items-center text-white bg-${type} border-0`;
    toast.setAttribute('role', 'alert');
    toast.setAttribute('aria-live', 'assertive');
    toast.setAttribute('aria-atomic', 'true');
    
    toast.innerHTML = `
        <div class="d-flex">
            <div class="toast-body">
                ${message}
            </div>
            <button type="button" class="btn-close btn-close-white me-2 m-auto" data-bs-dismiss="toast"></button>
        </div>
    `;
    
    // Add to toast container or create one
    let toastContainer = document.getElementById('toast-container');
    if (!toastContainer) {
        toastContainer = document.createElement('div');
        toastContainer.id = 'toast-container';
        toastContainer.className = 'toast-container position-fixed top-0 end-0 p-3';
        toastContainer.style.zIndex = '1055';
        document.body.appendChild(toastContainer);
    }
    
    toastContainer.appendChild(toast);
    
    // Show toast
    const bsToast = new bootstrap.Toast(toast);
    bsToast.show();
    
    // Remove from DOM after hiding
    toast.addEventListener('hidden.bs.toast', () => {
        toast.remove();
    });
}

// Loading state management
function setButtonLoading(button, loading = true) {
    if (loading) {
        button.dataset.originalText = button.innerHTML;
        button.innerHTML = '<i class="fas fa-spinner fa-spin me-2"></i>Loading...';
        button.disabled = true;
    } else {
        button.innerHTML = button.dataset.originalText || button.innerHTML;
        button.disabled = false;
    }
}

// API helper functions
async function apiRequest(url, options = {}) {
    try {
        const response = await fetch(url, {
            headers: {
                'Content-Type': 'application/json',
                ...options.headers
            },
            ...options
        });
        
        const data = await response.json();
        
        if (!response.ok) {
            throw new Error(data.detail || 'Request failed');
        }
        
        return data;
    } catch (error) {
        console.error('API request failed:', error);
        throw error;
    }
}

// Job matching functions
async function refreshMatches(button = null) {
    if (button) {
        setButtonLoading(button, true);
    }
    
    try {
        const data = await apiRequest('/api/refresh-matches', { method: 'POST' });
        showToast(`Success! Found ${data.match_count} job matches.`, 'success');
        
        // Reload page after a short delay
        setTimeout(() => {
            window.location.reload();
        }, 1500);
        
    } catch (error) {
        showToast(`Error refreshing matches: ${error.message}`, 'danger');
    } finally {
        if (button) {
            setButtonLoading(button, false);
        }
    }
}

// Form handling
function handleFormSubmit(form, successMessage = 'Success!') {
    form.addEventListener('submit', async (e) => {
        const submitButton = form.querySelector('button[type="submit"]');
        
        if (submitButton) {
            setButtonLoading(submitButton, true);
        }
        
        // Let the form submit naturally, but show loading state
        setTimeout(() => {
            if (submitButton) {
                setButtonLoading(submitButton, false);
            }
        }, 2000);
    });
}

// File upload handling
function setupFileUpload() {
    const fileInputs = document.querySelectorAll('input[type="file"]');
    
    fileInputs.forEach(input => {
        input.addEventListener('change', (e) => {
            const file = e.target.files[0];
            if (file) {
                // Validate file size (10MB limit)
                if (file.size > 10 * 1024 * 1024) {
                    showToast('File size must be less than 10MB', 'warning');
                    input.value = '';
                    return;
                }
                
                // Show file name
                const fileName = file.name;
                const label = input.parentElement.querySelector('.form-text');
                if (label) {
                    label.textContent = `Selected: ${fileName}`;
                    label.style.color = '#198754';
                }
            }
        });
    });
}

// Search and filter handling
function setupSearchFilters() {
    const filterForms = document.querySelectorAll('form[method="get"]');
    
    filterForms.forEach(form => {
        // Auto-submit on select change
        const selects = form.querySelectorAll('select');
        selects.forEach(select => {
            select.addEventListener('change', () => {
                form.submit();
            });
        });
        
        // Clear filters functionality
        const clearButton = document.createElement('button');
        clearButton.type = 'button';
        clearButton.className = 'btn btn-outline-secondary btn-sm ms-2';
        clearButton.innerHTML = '<i class="fas fa-times me-1"></i>Clear';
        clearButton.addEventListener('click', () => {
            // Clear all form inputs
            const inputs = form.querySelectorAll('input, select');
            inputs.forEach(input => {
                if (input.type === 'text' || input.type === 'number') {
                    input.value = '';
                } else if (input.type === 'select-one') {
                    input.selectedIndex = 0;
                }
            });
            
            // Submit form to clear filters
            form.submit();
        });
        
        // Add clear button to form
        const submitButton = form.querySelector('button[type="submit"]');
        if (submitButton && !form.querySelector('.btn-outline-secondary')) {
            submitButton.parentElement.appendChild(clearButton);
        }
    });
}

// Pagination handling
function setupPagination() {
    const paginationLinks = document.querySelectorAll('.pagination .page-link');
    
    paginationLinks.forEach(link => {
        link.addEventListener('click', (e) => {
            // Add loading state to clicked pagination link
            const clickedLink = e.target.closest('.page-link');
            if (clickedLink && !clickedLink.closest('.page-item').classList.contains('active')) {
                clickedLink.innerHTML = '<i class="fas fa-spinner fa-spin"></i>';
            }
        });
    });
}

// Job application handling
function setupJobApplications() {
    const applyButtons = document.querySelectorAll('[data-bs-target="#applyModal"]');
    
    applyButtons.forEach(button => {
        button.addEventListener('click', () => {
            const jobTitle = button.closest('.job-card, .card')?.querySelector('.job-title, h4')?.textContent?.trim();
            const modal = document.getElementById('applyModal');
            if (modal && jobTitle) {
                const modalTitle = modal.querySelector('.modal-title');
                if (modalTitle) {
                    modalTitle.textContent = `Apply to ${jobTitle}`;
                }
            }
        });
    });
    
    // Handle apply form submission
    const applyForm = document.querySelector('#applyModal form');
    if (applyForm) {
        handleFormSubmit(applyForm, 'Application submitted successfully!');
    }
}

// Statistics and progress bars animation
function animateProgressBars() {
    const progressBars = document.querySelectorAll('.progress-bar');
    
    const observer = new IntersectionObserver((entries) => {
        entries.forEach(entry => {
            if (entry.isIntersecting) {
                const progressBar = entry.target;
                const width = progressBar.style.width;
                
                // Animate from 0 to target width
                progressBar.style.width = '0%';
                progressBar.style.transition = 'width 1s ease-in-out';
                
                setTimeout(() => {
                    progressBar.style.width = width;
                }, 100);
                
                observer.unobserve(progressBar);
            }
        });
    });
    
    progressBars.forEach(bar => observer.observe(bar));
}

// Statistics cards animation
function animateStatCards() {
    const statCards = document.querySelectorAll('.card.bg-primary, .card.bg-success, .card.bg-info, .card.bg-warning');
    
    statCards.forEach((card, index) => {
        card.style.opacity = '0';
        card.style.transform = 'translateY(20px)';
        card.style.transition = 'opacity 0.5s ease, transform 0.5s ease';
        
        setTimeout(() => {
            card.style.opacity = '1';
            card.style.transform = 'translateY(0)';
        }, index * 100);
    });
}

// Keyboard shortcuts
function setupKeyboardShortcuts() {
    document.addEventListener('keydown', (e) => {
        // Ctrl/Cmd + K for search
        if ((e.ctrlKey || e.metaKey) && e.key === 'k') {
            e.preventDefault();
            const searchInput = document.querySelector('input[name="location"], input[type="search"]');
            if (searchInput) {
                searchInput.focus();
            }
        }
        
        // Escape to close modals
        if (e.key === 'Escape') {
            const openModal = document.querySelector('.modal.show');
            if (openModal) {
                const modal = bootstrap.Modal.getInstance(openModal);
                if (modal) {
                    modal.hide();
                }
            }
        }
    });
}

// Auto-save form data
function setupAutoSave() {
    const forms = document.querySelectorAll('form[data-autosave]');
    
    forms.forEach(form => {
        const inputs = form.querySelectorAll('input, textarea, select');
        
        inputs.forEach(input => {
            const key = `autosave_${form.id || 'form'}_${input.name}`;
            
            // Load saved value
            const savedValue = localStorage.getItem(key);
            if (savedValue && !input.value) {
                input.value = savedValue;
            }
            
            // Save on change
            input.addEventListener('input', () => {
                localStorage.setItem(key, input.value);
            });
        });
        
        // Clear saved data on successful submit
        form.addEventListener('submit', () => {
            setTimeout(() => {
                inputs.forEach(input => {
                    const key = `autosave_${form.id || 'form'}_${input.name}`;
                    localStorage.removeItem(key);
                });
            }, 1000);
        });
    });
}

// Initialize everything when DOM is loaded
document.addEventListener('DOMContentLoaded', () => {
    setupFileUpload();
    setupSearchFilters();
    setupPagination();
    setupJobApplications();
    setupKeyboardShortcuts();
    setupAutoSave();
    
    // Animate elements
    animateProgressBars();
    animateStatCards();
    
    // Setup form handlers
    const forms = document.querySelectorAll('form:not([method="get"])');
    forms.forEach(form => {
        if (!form.querySelector('input[type="file"]')) {
            handleFormSubmit(form);
        }
    });
});

// Export functions for global use
window.refreshMatches = refreshMatches;
window.showToast = showToast;
window.apiRequest = apiRequest;
