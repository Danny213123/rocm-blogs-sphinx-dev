/**
 * Responsive Image Optimizer for ROCm Blogs
 * Enhances responsive image loading performance with preloading and error handling
 */

(function() {
    'use strict';
    
    // Configuration
    const CONFIG = {
        heroImageSelector: '.responsive-image:first-of-type',
        allImagesSelector: '.responsive-image',
        preloadHero: true,
        observerOptions: {
            rootMargin: '50px',
            threshold: 0.01
        }
    };
    
    /**
     * Preload hero image for better LCP performance
     */
    function preloadHeroImage() {
        const heroImage = document.querySelector(CONFIG.heroImageSelector);
        if (!heroImage) return;
        
        const srcset = heroImage.getAttribute('srcset');
        const sizes = heroImage.getAttribute('sizes');
        
        if (srcset && sizes) {
            // Create preload link
            const preloadLink = document.createElement('link');
            preloadLink.rel = 'preload';
            preloadLink.as = 'image';
            preloadLink.setAttribute('imagesrcset', srcset);
            preloadLink.setAttribute('imagesizes', sizes);
            
            // Add fetchpriority for modern browsers
            preloadLink.setAttribute('fetchpriority', 'high');
            
            // Append to head
            document.head.appendChild(preloadLink);
            
            // Also set fetchpriority on the actual image
            heroImage.setAttribute('fetchpriority', 'high');
            heroImage.setAttribute('loading', 'eager');
        }
    }
    
    /**
     * Optimize loading for all responsive images
     */
    function optimizeResponsiveImages() {
        const images = document.querySelectorAll(CONFIG.allImagesSelector);
        
        images.forEach((img, index) => {
            // Hero image (first image) gets priority treatment
            if (index === 0) {
                img.setAttribute('fetchpriority', 'high');
                img.setAttribute('loading', 'eager');
                img.setAttribute('decoding', 'async');
            } else {
                // Other images use lazy loading
                img.setAttribute('fetchpriority', 'auto');
                img.setAttribute('loading', 'lazy');
                img.setAttribute('decoding', 'async');
            }
            
            // Add error handling
            img.addEventListener('error', handleImageError);
            
            // Add load success handling
            img.addEventListener('load', handleImageLoad);
        });
    }
    
    /**
     * Handle image loading errors
     */
    function handleImageError(event) {
        const img = event.target;
        
        // Log the error
        console.warn('Failed to load image:', img.src);
        
        // Clear srcset to prevent further errors
        img.removeAttribute('srcset');
        img.removeAttribute('sizes');
        
        // Add error class for styling
        img.classList.add('image-error');
        
        // Try fallback to src only
        if (img.src && !img.dataset.fallbackAttempted) {
            img.dataset.fallbackAttempted = 'true';
            const originalSrc = img.src;
            img.src = '';
            setTimeout(() => {
                img.src = originalSrc;
            }, 100);
        }
    }
    
    /**
     * Handle successful image load
     */
    function handleImageLoad(event) {
        const img = event.target;
        img.classList.add('image-loaded');
        img.classList.remove('image-error');
    }
    
    /**
     * Set up intersection observer for lazy loading enhancements
     */
    function setupIntersectionObserver() {
        if (!('IntersectionObserver' in window)) return;
        
        const imageObserver = new IntersectionObserver((entries) => {
            entries.forEach(entry => {
                if (entry.isIntersecting) {
                    const img = entry.target;
                    
                    // Enhance loading for images about to enter viewport
                    if (img.loading === 'lazy') {
                        // Browser will handle lazy loading, we just observe
                        imageObserver.unobserve(img);
                    }
                }
            });
        }, CONFIG.observerOptions);
        
        // Observe all non-hero images
        const images = document.querySelectorAll(CONFIG.allImagesSelector);
        images.forEach((img, index) => {
            if (index > 0) { // Skip hero image
                imageObserver.observe(img);
            }
        });
    }
    
    /**
     * Initialize the optimizer
     */
    function initialize() {
        // Wait for DOM to be ready
        if (document.readyState === 'loading') {
            document.addEventListener('DOMContentLoaded', initialize);
            return;
        }
        
        // Preload hero image
        if (CONFIG.preloadHero) {
            preloadHeroImage();
        }
        
        // Optimize all responsive images
        optimizeResponsiveImages();
        
        // Set up lazy loading observer
        setupIntersectionObserver();
    }
    
    // Start initialization
    initialize();
    
    // Export for debugging
    window.ResponsiveImageOptimizer = {
        preloadHeroImage,
        optimizeResponsiveImages,
        CONFIG
    };
})();