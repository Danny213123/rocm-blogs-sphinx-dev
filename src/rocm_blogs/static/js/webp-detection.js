/**
 * WebP Support Detection and Fallback Management
 * Ensures proper image format selection based on browser capabilities
 */

(function() {
    'use strict';
    
    /**
     * Check WebP support using canvas method
     */
    function checkWebPSupport(callback) {
        const webP = new Image();
        webP.onload = webP.onerror = function() {
            callback(webP.height === 2);
        };
        webP.src = 'data:image/webp;base64,UklGRjoAAABXRUJQVlA4IC4AAACyAgCdASoCAAIALmk0mk0iIiIiIgBoSygABc6WWgAA/veff/0PP8bA//LwYAAA';
    }
    
    /**
     * Update image sources based on WebP support
     */
    function updateImageSources(supportsWebP) {
        if (supportsWebP) {
            // WebP is supported, add class for CSS hooks
            document.documentElement.classList.add('webp-supported');
        } else {
            // WebP not supported, add fallback class and update sources
            document.documentElement.classList.add('webp-not-supported');
            
            // Find all images with WebP sources
            const images = document.querySelectorAll('img[src*=".webp"], img[srcset*=".webp"]');
            
            images.forEach(img => {
                // Handle src attribute
                if (img.src && img.src.includes('.webp')) {
                    // Try to fallback to JPG or PNG
                    const fallbackSrc = img.src.replace('.webp', '.jpg');
                    img.dataset.originalWebp = img.src;
                    img.src = fallbackSrc;
                    
                    // Add error handler for fallback
                    img.addEventListener('error', function() {
                        // Try PNG if JPG fails
                        if (this.src.includes('.jpg')) {
                            this.src = this.src.replace('.jpg', '.png');
                        }
                    });
                }
                
                // Handle srcset attribute
                if (img.srcset && img.srcset.includes('.webp')) {
                    // Store original srcset
                    img.dataset.originalSrcset = img.srcset;
                    
                    // Convert WebP srcset to JPG
                    const fallbackSrcset = img.srcset.replace(/\.webp/g, '.jpg');
                    img.srcset = fallbackSrcset;
                }
            });
        }
    }
    
    /**
     * Initialize WebP detection
     */
    function initialize() {
        // Check WebP support
        checkWebPSupport(function(supported) {
            updateImageSources(supported);
            
            // Store result in sessionStorage for faster subsequent checks
            try {
                sessionStorage.setItem('webp-supported', supported ? 'true' : 'false');
            } catch (e) {
                // SessionStorage not available
            }
        });
    }
    
    // Check if we already have a cached result
    try {
        const cached = sessionStorage.getItem('webp-supported');
        if (cached !== null) {
            updateImageSources(cached === 'true');
        } else {
            initialize();
        }
    } catch (e) {
        // SessionStorage not available, run detection
        initialize();
    }
    
    // Export for debugging
    window.WebPDetection = {
        checkWebPSupport,
        updateImageSources
    };
})();