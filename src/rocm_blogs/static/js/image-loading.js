document.addEventListener('DOMContentLoaded', function() {

    function handleImageLoading() {
        const lazyImages = document.querySelectorAll('img[loading="lazy"], .sd-card-img-top');
        const responsiveImages = document.querySelectorAll('.responsive-image');

        lazyImages.forEach(img => {
            if (!img.complete) {
                img.classList.add('loading');
            }
        });

        // Handle responsive images with eager loading
        responsiveImages.forEach(img => {
            if (!img.complete && !img.classList.contains('loading')) {
                img.classList.add('loading');
                
                const handleLoad = () => {
                    setTimeout(() => {
                        img.classList.remove('loading');
                        img.classList.add('loaded');
                    }, 50);
                    img.removeEventListener('load', handleLoad);
                };

                const handleError = () => {
                    img.classList.remove('loading');
                    img.classList.add('error');
                    img.removeEventListener('error', handleError);
                };

                if (img.complete) {
                    img.classList.remove('loading');
                    img.classList.add('loaded');
                } else {
                    img.addEventListener('load', handleLoad);
                    img.addEventListener('error', handleError);
                }
            }
        });

        const imageObserver = new IntersectionObserver((entries, observer) => {
            entries.forEach(entry => {
                if (entry.isIntersecting) {
                    const img = entry.target;

                    const handleLoad = () => {
                        setTimeout(() => {
                            img.classList.remove('loading');
                        }, 50);
                        img.removeEventListener('load', handleLoad);
                    };

                    if (img.complete) {
                        img.classList.remove('loading');
                    } else {
                        img.addEventListener('load', handleLoad);
                    }

                    observer.unobserve(img);
                }
            });
        }, {
            rootMargin: '200px 0px',
            threshold: 0.01
        });

        lazyImages.forEach(img => {
            imageObserver.observe(img);
        });
    }

    handleImageLoading();

    setTimeout(handleImageLoading, 500);
});
