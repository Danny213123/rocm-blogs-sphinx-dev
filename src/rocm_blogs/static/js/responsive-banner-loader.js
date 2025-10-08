/**
 * Responsive Banner Image Loader with Error Handling
 * Handles srcset loading, fallbacks, and progressive enhancement
 */

(function() {
    'use strict';

    // Configuration
    const config = {
        retryAttempts: 3,
        retryDelay: 1000,
        loadTimeout: 10000,
        fallbackSrc: './_images/generic.webp'
    };

    // Track loading state
    const imageLoadingState = new Map();

    /**
     * Initialize banner image loading
     */
    function initBannerImageLoader() {
        const bannerImages = document.querySelectorAll(
            '.wp-post-image, .attachment-full-page-width, .size-full-page-width'
        );

        bannerImages.forEach(img => {
            setupImageLoading(img);
        });

        // Handle dynamically added images
        observeNewImages();
    }

    /**
     * Setup loading handlers for an image
     */
    function setupImageLoading(img) {
        if (imageLoadingState.has(img)) return;

        const state = {
            attempts: 0,
            loaded: false,
            originalSrc: img.src,
            originalSrcset: img.srcset
        };

        imageLoadingState.set(img, state);

        // Add loading class
        img.classList.add('loading');
        
        // Set up load timeout
        const timeoutId = setTimeout(() => {
            if (!state.loaded) {
                handleImageError(img, new Error('Image load timeout'));
            }
        }, config.loadTimeout);

        // Success handler
        img.addEventListener('load', function handleLoad() {
            clearTimeout(timeoutId);
            state.loaded = true;
            img.classList.remove('loading');
            img.classList.add('loaded');
            img.removeEventListener('load', handleLoad);
        }, { once: true });

        // Error handler
        img.addEventListener('error', function handleError(e) {
            clearTimeout(timeoutId);
            handleImageError(img, e);
        }, { once: true });

        // Check if already loaded
        if (img.complete && img.naturalHeight !== 0) {
            clearTimeout(timeoutId);
            state.loaded = true;
            img.classList.remove('loading');
            img.classList.add('loaded');
        }
    }

    /**
     * Handle image loading errors with retry logic
     */
    function handleImageError(img, error) {
        const state = imageLoadingState.get(img);
        if (!state) return;

        console.warn('Banner image failed to load:', img.src, error);
        
        state.attempts++;

        if (state.attempts < config.retryAttempts) {
            // Retry loading
            setTimeout(() => {
                retryImageLoad(img, state);
            }, config.retryDelay * state.attempts);
        } else {
            // All retries failed, apply fallback
            applyFallback(img, state);
        }
    }

    /**
     * Retry loading an image
     */
    function retryImageLoad(img, state) {
        console.log(`Retrying image load (attempt ${state.attempts + 1}/${config.retryAttempts}):`, state.originalSrc);

        // Try without srcset first
        if (state.attempts === 1 && img.srcset) {
            img.srcset = '';
            img.sizes = '';
        }
        
        // Force reload
        const src = img.src;
        img.src = '';
        img.src = src;

        // Re-setup loading handlers
        setupImageLoading(img);
    }

    /**
     * Apply fallback image when all retries fail
     */
    function applyFallback(img, state) {
        console.error('All retry attempts failed for image:', state.originalSrc);
        
        img.classList.remove('loading');
        img.classList.add('error');
        
        // Clear srcset to prevent further errors
        img.srcset = '';
        img.sizes = '';
        
        // Try fallback image
        if (img.src !== config.fallbackSrc) {
            img.src = config.fallbackSrc;
            
            // Give fallback one chance to load
            img.addEventListener('load', function() {
                img.classList.remove('error');
                img.classList.add('loaded', 'fallback');
            }, { once: true });
            
            img.addEventListener('error', function() {
                // Even fallback failed, show error state
                img.classList.add('error-permanent');
                createErrorPlaceholder(img);
            }, { once: true });
        } else {
            createErrorPlaceholder(img);
        }
    }

    /**
     * Create visual error placeholder
     */
    function createErrorPlaceholder(img) {
        const container = img.parentElement;
        if (!container || container.classList.contains('has-error-placeholder')) return;
        
        container.classList.add('has-error-placeholder');
        
        const placeholder = document.createElement('div');
        placeholder.className = 'image-error-placeholder';
        placeholder.innerHTML = `
            <svg width="64" height="64" viewBox="0 0 24 24" fill="none" stroke="currentColor">
                <rect x="3" y="3" width="18" height="18" rx="2" ry="2"/>
                <line x1="9" y1="9" x2="15" y2="15"/>
                <line x1="15" y1="9" x2="9" y2="15"/>
            </svg>
            <p>Image could not be loaded</p>
        `;
        
        img.style.display = 'none';
        container.appendChild(placeholder);
    }

    /**
     * Observe for dynamically added images
     */
    function observeNewImages() {
        if (!window.MutationObserver) return;
        
        const observer = new MutationObserver(mutations => {
            mutations.forEach(mutation => {
                mutation.addedNodes.forEach(node => {
                    if (node.nodeType === 1) { // Element node
                        if (node.tagName === 'IMG' && (
                            node.classList.contains('wp-post-image') ||
                            node.classList.contains('attachment-full-page-width') ||
                            node.classList.contains('size-full-page-width')
                        )) {
                            setupImageLoading(node);
                        }
                        
                        // Check descendants
                        const images = node.querySelectorAll(
                            '.wp-post-image, .attachment-full-page-width, .size-full-page-width'
                        );
                        images.forEach(img => setupImageLoading(img));
                    }
                });
            });
        });
        
        observer.observe(document.body, {
            childList: true,
            subtree: true
        });
    }

    /**
     * Handle responsive image switching
     */
    function handleResponsiveImages() {
        const images = document.querySelectorAll('img[srcset]');
        
        // Create picture element wrapper for better responsive control
        images.forEach(img => {
            if (img.parentElement.tagName === 'PICTURE') return;
            
            const srcset = img.getAttribute('srcset');
            if (!srcset) return;
            
            // Parse srcset to create source elements
            const sources = parseSrcset(srcset);
            if (sources.length === 0) return;
            
            const picture = document.createElement('picture');
            
            // Add WebP sources if available
            sources.forEach(source => {
                if (source.url.includes('.webp')) {
                    const webpSource = document.createElement('source');
                    webpSource.srcset = `${source.url} ${source.descriptor}`;
                    webpSource.type = 'image/webp';
                    if (source.media) {
                        webpSource.media = source.media;
                    }
                    picture.appendChild(webpSource);
                }
            });
            
            // Clone original image as fallback
            const fallbackImg = img.cloneNode(true);
            picture.appendChild(fallbackImg);
            
            // Replace original image with picture element
            img.parentElement.replaceChild(picture, img);
            
            // Setup loading for new image
            setupImageLoading(fallbackImg);
        });
    }

    /**
     * Parse srcset attribute
     */
    function parseSrcset(srcset) {
        const sources = [];
        const parts = srcset.split(',').map(s => s.trim());
        
        parts.forEach(part => {
            const match = part.match(/^(.+?)\s+(\d+w|\d+x)$/);
            if (match) {
                sources.push({
                    url: match[1],
                    descriptor: match[2]
                });
            }
        });
        
        return sources;
    }

    /**
     * Preload critical images
     */
    function preloadCriticalImages() {
        const criticalImages = document.querySelectorAll('img[fetchpriority="high"]');
        
        criticalImages.forEach(img => {
            if (img.src && !img.complete) {
                const link = document.createElement('link');
                link.rel = 'preload';
                link.as = 'image';
                link.href = img.src;
                
                if (img.srcset) {
                    link.imageSrcset = img.srcset;
                }
                
                if (img.sizes) {
                    link.imageSizes = img.sizes;
                }
                
                document.head.appendChild(link);
            }
        });
    }

    // Initialize on DOM ready
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', initBannerImageLoader);
    } else {
        initBannerImageLoader();
    }

    // Preload critical images immediately
    preloadCriticalImages();

    // Handle responsive image switching
    handleResponsiveImages();

    // Re-check images on window load
    window.addEventListener('load', () => {
        const images = document.querySelectorAll(
            '.wp-post-image, .attachment-full-page-width, .size-full-page-width'
        );
        images.forEach(img => {
            if (!img.classList.contains('loaded') && !img.classList.contains('error')) {
                setupImageLoading(img);
            }
        });
    });

    // Export for debugging
    window.BannerImageLoader = {
        config,
        imageLoadingState,
        retryImageLoad,
        setupImageLoading
    };
})();