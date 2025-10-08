document.addEventListener('DOMContentLoaded', function() {
    // Simple and effective image loading handler
    function handleImageLoading() {
        const images = document.querySelectorAll('img.responsive-image, img.wp-post-image, .sd-card-img-top');
        
        images.forEach(img => {
            // Add loading class initially
            if (!img.complete) {
                img.classList.add('loading');
            }
            
            // Handle successful load
            img.addEventListener('load', function() {
                this.classList.remove('loading');
                this.classList.add('loaded');
            });
            
            // Handle errors gracefully
            img.addEventListener('error', function() {
                console.warn('Image failed to load:', this.src);
                this.classList.remove('loading');
                this.classList.add('error');
                // Fallback to base image if srcset fails
                if (this.srcset) {
                    this.srcset = '';
                    // Try loading just the src
                    const baseSrc = this.src;
                    this.src = '';
                    this.src = baseSrc;
                }
            });
            
            // If already loaded
            if (img.complete && img.naturalWidth > 0) {
                img.classList.remove('loading');
                img.classList.add('loaded');
            }
        });
    }
    
    // Run immediately
    handleImageLoading();
    
    // Run again after a short delay to catch dynamically added images
    setTimeout(handleImageLoading, 100);
});
