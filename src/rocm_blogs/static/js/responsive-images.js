
(function() {
    'use strict';

    const supportsLazyLoading = 'loading' in HTMLImageElement.prototype;
    const supportsIntersectionObserver = 'IntersectionObserver' in window;
    const isSlowConnection = navigator.connection && 
                           (navigator.connection.effectiveType === '2g' || 
                            navigator.connection.effectiveType === 'slow-2g' ||
                            navigator.connection.saveData);
    
    const connectionOptimizedSettings = {
        rootMargin: isSlowConnection ? '100px 0px' : '50px 0px',
        threshold: isSlowConnection ? 0.01 : 0.1
    };

    let imageObserver;

    if (!supportsLazyLoading && supportsIntersectionObserver) {
        imageObserver = new IntersectionObserver((entries, observer) => {
            entries.forEach(entry => {
                if (entry.isIntersecting) {
                    const img = entry.target;
                    requestIdleCallback ? 
                        requestIdleCallback(() => loadImage(img)) : 
                        setTimeout(() => loadImage(img), 0);
                    observer.unobserve(img);
                }
            });
        }, connectionOptimizedSettings);
    }

    function loadImage(img) {
        const container = img.closest('.image-container, .banner-image-container');
        
        if (container) {
            container.classList.add('loading');
        }
        
        if (img.dataset.src) {
            img.src = img.dataset.src;
        }
        if (img.dataset.srcset) {
            img.srcset = img.dataset.srcset;
        }
        
        img.onload = () => {
            requestAnimationFrame(() => {
                img.classList.add('loaded');
                if (container) {
                    container.classList.remove('loading');
                    container.classList.add('loaded');
                }
            });
        };
    }

    function handleImageLoad(img) {
        const container = img.closest('.image-container, .banner-image-container');
        
        if (container) {
            container.classList.add('loading');
        }
        
        requestAnimationFrame(() => {
            img.classList.add('loaded');
            if (container) {
                container.classList.remove('loading');
                container.classList.add('loaded');
            }
        });
    }

    function handleImageError(img) {
        img.classList.add('image-error');
        console.warn('Image failed to load:', img.src);
        
        if (img.dataset.fallback && !img.dataset.fallbackAttempted) {
            img.dataset.fallbackAttempted = 'true';
            img.src = img.dataset.fallback;
        }
    }

    function setupProgressiveLoading(img) {
        if (isSlowConnection) return;
        
        if (img.dataset.placeholder) {
            const placeholder = new Image();
            placeholder.loading = 'eager';
            placeholder.src = img.dataset.placeholder;
            placeholder.onload = function() {
                img.style.setProperty('--placeholder-image', `url(${placeholder.src})`);
                img.classList.add('has-placeholder');
            };
        }
    }

    function optimizeSrcset(img) {
        const dpr = window.devicePixelRatio || 1;
        const width = img.clientWidth * dpr;
        const currentSrcset = img.getAttribute('srcset');
        
        if (currentSrcset && width) {
            const sources = currentSrcset.split(',').map(src => {
                const parts = src.trim().split(' ');
                return {
                    url: parts[0],
                    width: parseInt(parts[1])
                };
            });
            
            const optimal = sources
                .filter(s => s.width >= width)
                .sort((a, b) => a.width - b.width)[0];
            
            if (optimal && img.src !== optimal.url) {
                img.dataset.optimalSrc = optimal.url;
            }
        }
    }

    function initResponsiveImages() {
        const images = document.querySelectorAll('.responsive-image, .banner-image, .img-fluid');
        
        images.forEach(img => {
            setupProgressiveLoading(img);
            
            optimizeSrcset(img);
            
            const container = img.closest('.image-container, .banner-image-container');
            if (container && !container.classList.contains('loaded')) {
                container.classList.add('loading');
            }
            
            img.addEventListener('load', () => handleImageLoad(img));
            img.addEventListener('error', () => handleImageError(img));
            
            if (img.loading === 'lazy') {
                if (!supportsLazyLoading && imageObserver) {
                    img.dataset.src = img.src;
                    img.dataset.srcset = img.srcset;
                    img.src = '';
                    img.srcset = '';
                    imageObserver.observe(img);
                } else {
                    img.addEventListener('load', () => {
                        handleImageLoad(img);
                    }, { once: true });
                }
            } else {
                if (img.complete && img.naturalWidth > 0) {
                    handleImageLoad(img);
                } else {
                    img.addEventListener('load', () => {
                        handleImageLoad(img);
                    }, { once: true });
                }
            }
        });
    }

    let resizeTimeout;
    function handleResize() {
        clearTimeout(resizeTimeout);
        const delay = isSlowConnection ? 500 : 250;
        resizeTimeout = setTimeout(() => {
            const updateImages = () => {
                const images = document.querySelectorAll('.responsive-image, .banner-image');
                images.forEach(optimizeSrcset);
            };
            
            if (requestIdleCallback) {
                requestIdleCallback(updateImages, { timeout: 1000 });
            } else {
                updateImages();
            }
        }, delay);
    }

    function preloadCriticalImages() {
        const criticalImages = document.querySelectorAll('img[fetchpriority="high"]');
        criticalImages.forEach(img => {
            if (img.loading !== 'eager') {
                img.loading = 'eager';
            }
            const link = document.createElement('link');
            link.rel = 'preload';
            link.as = 'image';
            link.href = img.src;
            if (img.srcset) {
                link.imageSrcset = img.srcset;
                link.imageSizes = img.sizes;
            }
            document.head.appendChild(link);
        });
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', () => {
            preloadCriticalImages();
            initResponsiveImages();
        });
    } else {
        preloadCriticalImages();
        initResponsiveImages();
    }

    if (!isSlowConnection) {
        window.addEventListener('resize', handleResize, { passive: true });
    } else {
        console.log('Resize optimization disabled for slow connection');
    }

    const mutationObserver = new MutationObserver(mutations => {
        mutations.forEach(mutation => {
            mutation.addedNodes.forEach(node => {
                if (node.nodeType === 1) {
                    if (node.matches && node.matches('.responsive-image, .banner-image, .img-fluid')) {
                        initResponsiveImages();
                    } else if (node.querySelectorAll) {
                        const images = node.querySelectorAll('.responsive-image, .banner-image, .img-fluid');
                        if (images.length > 0) {
                            initResponsiveImages();
                        }
                    }
                }
            });
        });
    });

    mutationObserver.observe(document.body, {
        childList: true,
        subtree: true
    });

    window.ResponsiveImages = {
        init: initResponsiveImages,
        optimizeSrcset: optimizeSrcset,
        preloadCriticalImages: preloadCriticalImages
    };

})();