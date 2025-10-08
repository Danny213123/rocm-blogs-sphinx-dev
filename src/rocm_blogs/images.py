"""
Image processing utilities for ROCm Blogs.

This module contains functions for image optimization, WebP conversion,
and other image-related operations used in the ROCm Blogs package.
"""

import os
import shutil
from datetime import datetime

from PIL import Image
from sphinx.util import logging as sphinx_logging

from ._rocmblogs import ROCmBlogs
from .constants import *
from .logger.logger import create_step_log_file, log_message, safe_log_write

WEBP_CONVERSION_STATISTICS = {
    "converted": 0,
    "skipped": 0,
    "failed": 0,
    "total_size_original": 0,
    "total_size_webp": 0,
}


def generate_responsive_images(source_image_path, target_widths=None, output_dir=None):
    if target_widths is None:
        # Optimized responsive breakpoints for performance and bandwidth efficiency
        # Covers all major device categories with minimal variants for fast loading
        target_widths = [
            320,  # Mobile portrait (saves ~75% bandwidth vs desktop)
            480,  # Mobile landscape / small tablet
            640,  # Tablet portrait (good balance for mid-range devices)
            768,  # Large tablet / small desktop
            1024,
            1440,
        ]

    source_dir = output_dir if output_dir else os.path.dirname(source_image_path)
    base_name = os.path.splitext(os.path.basename(source_image_path))[0]
    _, file_extension = os.path.splitext(source_image_path)

    responsive_images = {}

    if not source_image_path or not os.path.exists(source_image_path):
        log_message("warning", f"Source image not found: {source_image_path}")
        return responsive_images

    if file_extension.lower() in EXCLUDED_EXTENSIONS:
        log_message(
            "info",
            f"Skipping responsive generation for excluded format: {file_extension}",
        )
        return {0: source_image_path}

    try:
        os.makedirs(source_dir, exist_ok=True)
    except Exception as dir_error:
        log_message(
            "error", f"Failed to create output directory {source_dir}: {dir_error}"
        )
        return responsive_images

    try:
        with Image.open(source_image_path) as img:
            img.load()

            img_copy = img.copy()

        original_width, original_height = img_copy.size
        aspect_ratio = original_height / original_width if original_width > 0 else 1

        if original_width <= 2560:
            responsive_images[original_width] = source_image_path

        log_message(
            "info",
            f"Generating responsive images for: {base_name} (original: {original_width}x{original_height})",
        )

        variants_created = 0

        if original_width >= 1920 and 1920 not in target_widths:
            target_widths = target_widths + [1920]

        for target_width in sorted(target_widths):
            if target_width > original_width:
                log_message(
                    "debug",
                    f"Skipping {target_width}w (larger than original {original_width}w)",
                )
                continue

            target_height = max(1, int(target_width * aspect_ratio))

            variant_filename = f"{base_name}-{target_width}w.webp"
            variant_path = os.path.join(source_dir, variant_filename)

            if os.path.exists(variant_path):
                try:
                    with Image.open(variant_path) as test_img:
                        test_img.verify()
                    responsive_images[target_width] = variant_path
                    log_message(
                        "debug",
                        f"Responsive variant already exists: {variant_filename}",
                    )
                    continue
                except Exception:
                    log_message(
                        "warning",
                        f"Existing variant {variant_filename} is corrupted, recreating",
                    )
                    try:
                        os.remove(variant_path)
                    except:
                        pass

            try:
                log_message(
                    "info",
                    f"Creating variant: {variant_filename} ({target_width}x{target_height})",
                )

                resized_img = img_copy.resize(
                    (target_width, target_height), resample=Image.LANCZOS
                )

                if resized_img.mode not in ("RGB", "RGBA"):
                    if resized_img.mode == "P":
                        resized_img = resized_img.convert(
                            "RGBA" if "transparency" in resized_img.info else "RGB"
                        )
                    else:
                        resized_img = resized_img.convert("RGB")

                # Optimize quality based on image size for better performance
                if target_width <= 480:
                    # Mobile images - prioritize smaller file sizes
                    quality = 82
                    method = 4  # Faster compression
                elif target_width <= 1024:
                    # Tablet/small desktop - balance quality and size
                    quality = 88
                    method = 5
                else:
                    # Large desktop - higher quality
                    quality = 92
                    method = 6

                resized_img.save(
                    variant_path,
                    format="WEBP",
                    quality=quality,
                    method=method,
                    optimize=True,
                    exact=False,  # Allow encoder flexibility for better compression
                )

                if os.path.exists(variant_path) and os.path.getsize(variant_path) > 0:
                    responsive_images[target_width] = variant_path
                    variants_created += 1
                    log_message(
                        "info",
                        f"✓ Created responsive variant: {variant_filename} ({target_width}x{target_height})",
                    )
                else:
                    log_message("error", f"Failed to create valid {variant_filename}")

                resized_img.close()

                # Generate ultra-low quality placeholder for fast initial loading (slow connections)
                if target_width == 320:  # Only for smallest size to minimize build time
                    try:
                        placeholder_width = 32
                        placeholder_height = max(
                            1, int(placeholder_width * aspect_ratio)
                        )
                        placeholder_img = img_copy.resize(
                            (placeholder_width, placeholder_height),
                            resample=Image.LANCZOS,
                        )

                        if placeholder_img.mode not in ("RGB", "RGBA"):
                            placeholder_img = placeholder_img.convert("RGB")

                        placeholder_path = os.path.join(
                            source_dir, f"{base_name}-placeholder.webp"
                        )

                        placeholder_img.save(
                            placeholder_path,
                            format="WEBP",
                            quality=30,  # Very low quality for tiny file size
                            method=1,  # Fastest compression
                            optimize=True,
                        )

                        placeholder_img.close()
                        log_message(
                            "info", f"Generated placeholder: {placeholder_path}"
                        )

                    except Exception as placeholder_error:
                        log_message(
                            "warning",
                            f"Failed to generate placeholder: {placeholder_error}",
                        )

            except Exception as resize_error:
                log_message(
                    "error", f"Failed to create {target_width}w variant: {resize_error}"
                )
                if os.path.exists(variant_path):
                    try:
                        os.remove(variant_path)
                    except:
                        pass

        img_copy.close()

        log_message(
            "info", f"Generated {variants_created} responsive variants for {base_name}"
        )

    except Exception as e:
        log_message(
            "error", f"Error generating responsive images for {source_image_path}: {e}"
        )
        import traceback

        log_message("debug", f"Traceback: {traceback.format_exc()}")

    return responsive_images


def convert_to_webp(source_image_path):
    source_image_filename = os.path.basename(source_image_path)
    webp_image_path = os.path.splitext(source_image_path)[0] + ".webp"

    if not os.path.exists(source_image_path):
        log_message("warning", f"Image file not found: {source_image_path}")
        return False, None

    _, file_extension = os.path.splitext(source_image_path)
    if file_extension.lower() not in SUPPORTED_FORMATS:
        log_message(
            "warning",
            f"Unsupported image format: {file_extension} for {source_image_path}",
        )
        return False, None

    if file_extension.lower() in EXCLUDED_EXTENSIONS:
        log_message(
            "info",
            "Skipping WebP conversion for excluded image format: {file_extension} for {source_image_path}",
            "general",
            "images",
        )
        return True, source_image_path

    if file_extension.lower() == ".webp":
        log_message("debug", f"Image is already in WebP format: {source_image_path}")
        return True, source_image_path

    if os.path.exists(webp_image_path):
        log_message("debug", f"WebP version already exists: {webp_image_path}")
        generate_responsive_images(webp_image_path)
        return True, webp_image_path

    try:
        with Image.open(source_image_path) as pil_image:
            original_width, original_height = pil_image.size
            original_mode = pil_image.mode

            webp_image = (
                pil_image
                if original_mode in ("RGB", "RGBA")
                else pil_image.convert("RGB")
            )

            is_banner_image = "banner" in str(source_image_path).lower()
            if is_banner_image:
                webp_image = _resize_image(
                    webp_image,
                    BANNER_DIMENSIONS[0],
                    BANNER_DIMENSIONS[1],
                    force_exact=True,
                    source_image_filename=source_image_filename,
                )
                log_message(
                    "info",
                    "Resized banner image to {BANNER_DIMENSIONS[0]}x{BANNER_DIMENSIONS[1]}: {source_image_filename}",
                    "general",
                    "images",
                )
            else:
                webp_image = _resize_content_image(
                    webp_image,
                    original_width,
                    original_height,
                    source_image_filename=source_image_filename,
                )
                if webp_image.size != (original_width, original_height):
                    new_width, new_height = webp_image.size
                    log_message(
                        "info",
                        "Resized image from {original_width}x{original_height} to {new_width}x{new_height}: {source_image_filename}",
                        "general",
                        "images",
                    )

            webp_image.save(
                webp_image_path, format="WEBP", quality=WEBP_QUALITY, method=WEBP_METHOD
            )

            log_message(
                "info",
                f"Created WebP version: {os.path.basename(webp_image_path)}",
                "general",
                "images",
            )

            generate_responsive_images(webp_image_path)

            return True, webp_image_path

    except Exception as webp_conversion_error:
        log_message("warning", f"Error creating WebP version: {webp_conversion_error}")
        if os.path.exists(webp_image_path):
            os.remove(webp_image_path)
        return False, None


def optimize_image(source_image_path, blog_thumbnail_filenames=None):
    source_image_filename = os.path.basename(source_image_path)
    backup_image_path = f"{source_image_path}.bak"
    webp_image_path = os.path.splitext(source_image_path)[0] + ".webp"

    if not _should_optimize_image(
        source_image_path, source_image_filename, blog_thumbnail_filenames
    ):
        return False, None

    if not _create_backup(source_image_path, backup_image_path):
        return False, None

    original_file_size = os.path.getsize(source_image_path)

    try:
        with Image.open(source_image_path) as pil_image:
            source_image_width, source_image_height = pil_image.size
            source_image_format = pil_image.format
            source_image_mode = pil_image.mode

            log_message(
                "debug",
                f"Image details: {source_image_filename}, Format: {source_image_format}, Mode: {source_image_mode}, Size: {source_image_width}x{source_image_height}",
            )

            if not _verify_image_integrity(
                pil_image, source_image_path, backup_image_path, source_image_filename
            ):
                return False, None

            if source_image_filename in PROBLEMATIC_IMAGES:
                success, webp_image_path = _handle_problematic_image(
                    pil_image,
                    source_image_path,
                    backup_image_path,
                    source_image_filename,
                )
                return success, webp_image_path

            optimized_image = _process_image(
                pil_image,
                source_image_path,
                source_image_mode,
                source_image_width,
                source_image_height,
                backup_image_path,
                source_image_filename,
            )
            if optimized_image is None:
                return False, None

            if not _save_optimized_image(
                optimized_image,
                source_image_path,
                backup_image_path,
                source_image_filename,
            ):
                return False, None

            webp_conversion_success = _create_webp_version(
                optimized_image, webp_image_path, source_image_path, original_file_size
            )

            if not _verify_and_check_size_reduction(
                source_image_path,
                backup_image_path,
                original_file_size,
                source_image_format,
                source_image_filename,
            ):
                pass

        if os.path.exists(backup_image_path):
            os.remove(backup_image_path)

        return True, webp_image_path if webp_conversion_success else None

    except Exception as optimize_error:
        log_message(
            "warning",
            f"Error optimizing image {source_image_filename}: {optimize_error}",
        )
        _restore_from_backup(
            backup_image_path, source_image_path, source_image_filename
        )
        WEBP_CONVERSION_STATISTICS["failed"] += 1
        return False, None


def _should_optimize_image(
    source_image_path, source_image_filename, blog_thumbnail_filenames
):
    if blog_thumbnail_filenames is not None:
        if (
            source_image_filename not in blog_thumbnail_filenames
            and source_image_filename.lower()
            not in [thumbnail.lower() for thumbnail in blog_thumbnail_filenames]
        ):
            log_message("debug", f"Skipping non-thumbnail image: {source_image_path}")
            return False

    if not os.path.exists(source_image_path):
        log_message("warning", f"Image file not found: {source_image_path}")
        return False

    _, file_extension = os.path.splitext(source_image_path)
    if file_extension.lower() not in SUPPORTED_FORMATS:
        log_message(
            "warning",
            f"Unsupported image format: {file_extension} for {source_image_path}",
        )
        return False

    return True


def _create_backup(source_image_path, backup_image_path):
    try:
        shutil.copy2(source_image_path, backup_image_path)
        return True
    except Exception as backup_error:
        log_message(
            "warning", f"Failed to create backup of {source_image_path}: {backup_error}"
        )
        return False


def _restore_from_backup(backup_image_path, source_image_path, source_image_filename):
    if os.path.exists(backup_image_path):
        log_message(
            "info",
            "Restoring original image from backup for {source_image_filename}",
            "general",
            "images",
        )
        try:
            shutil.copy2(backup_image_path, source_image_path)
            os.remove(backup_image_path)
        except Exception as restore_error:
            log_message("warning", f"Error restoring from backup: {restore_error}")


def _verify_image_integrity(
    pil_image, source_image_path, backup_image_path, source_image_filename
):
    try:
        pil_image.verify()
        return True
    except Exception as verify_error:
        log_message(
            "warning", f"Corrupted image detected: {source_image_path} - {verify_error}"
        )
        _restore_from_backup(
            backup_image_path, source_image_path, source_image_filename
        )
        return False


def _handle_problematic_image(
    pil_image, source_image_path, backup_image_path, source_image_filename
):
    log_message(
        "info",
        "Using conservative optimization for {source_image_filename}",
        "general",
        "images",
    )
    webp_image_path = os.path.splitext(source_image_path)[0] + ".webp"

    try:
        _, file_extension = os.path.splitext(source_image_path)
        file_extension = file_extension.lower()

        pil_image = Image.open(source_image_path)

        if file_extension in [".jpg", ".jpeg"]:
            pil_image.save(
                source_image_path, format="JPEG", **CONSERVATIVE_SETTINGS["JPEG"]
            )
        elif file_extension == ".png":
            pil_image.save(
                source_image_path, format="PNG", **CONSERVATIVE_SETTINGS["PNG"]
            )
        else:
            pil_image.save(source_image_path)

        webp_image = (
            pil_image if pil_image.mode in ("RGB", "RGBA") else pil_image.convert("RGB")
        )
        webp_image.save(webp_image_path, format="WEBP", **CONSERVATIVE_SETTINGS["WEBP"])

        WEBP_CONVERSION_STATISTICS["converted"] += 1
        WEBP_CONVERSION_STATISTICS["total_size_original"] += os.path.getsize(
            source_image_path
        )
        WEBP_CONVERSION_STATISTICS["total_size_webp"] += os.path.getsize(
            webp_image_path
        )

        log_message(
            "info",
            "Conservative optimization completed for {source_image_filename} with WebP version",
            "general",
            "images",
        )

        if os.path.exists(backup_image_path):
            os.remove(backup_image_path)

        return True, webp_image_path
    except Exception as conservative_error:
        log_message(
            "warning",
            f"Conservative optimization failed for {source_image_filename}: {conservative_error}",
        )
        _restore_from_backup(
            backup_image_path, source_image_path, source_image_filename
        )
        WEBP_CONVERSION_STATISTICS["failed"] += 1
        return False, None


def _create_webp_version(
    optimized_image, webp_image_path, original_image_path, original_file_size
):

    _, file_extension = os.path.splitext(original_image_path)
    file_extension = file_extension.lower()
    if file_extension in EXCLUDED_EXTENSIONS:
        log_message(
            "info",
            "Skipping WebP conversion for excluded image format: {file_extension} for {original_image_path}",
            "general",
            "images",
        )
        return False
    try:
        webp_image = (
            optimized_image
            if optimized_image.mode in ("RGB", "RGBA")
            else optimized_image.convert("RGB")
        )

        webp_image.save(
            webp_image_path, format="WEBP", quality=WEBP_QUALITY, method=WEBP_METHOD
        )

        webp_file_size = os.path.getsize(webp_image_path)
        size_reduction_percentage = (
            (1 - webp_file_size / original_file_size) * 100
            if original_file_size > 0
            else 0
        )

        if (
            webp_file_size >= original_file_size
            or size_reduction_percentage < MIN_SIZE_REDUCTION_PCT
        ):
            log_message(
                "info",
                f"WebP conversion not beneficial (size reduction: {size_reduction_percentage:.1f}%), skipping: {os.path.basename(webp_image_path)}",
                "general",
                "images",
            )

            if os.path.exists(webp_image_path):
                os.remove(webp_image_path)
            WEBP_CONVERSION_STATISTICS["skipped"] += 1
            return False

        WEBP_CONVERSION_STATISTICS["converted"] += 1
        WEBP_CONVERSION_STATISTICS["total_size_original"] += original_file_size
        WEBP_CONVERSION_STATISTICS["total_size_webp"] += os.path.getsize(
            webp_image_path
        )

        log_message(
            "info",
            f"Created WebP version: {os.path.basename(webp_image_path)}",
            "general",
            "images",
        )
        log_message(
            "info",
            f"Original: {original_file_size/1024:.1f}KB -> WebP: {os.path.getsize(webp_image_path)/1024:.1f}KB ({size_reduction_percentage:.1f}% reduction)",
            "general",
            "images",
        )

        return True

    except Exception as webp_conversion_error:
        log_message("warning", f"Error creating WebP version: {webp_conversion_error}")
        if os.path.exists(webp_image_path):
            os.remove(webp_image_path)
        WEBP_CONVERSION_STATISTICS["failed"] += 1
        return False


def _process_image(
    pil_image,
    source_image_path,
    source_image_mode,
    source_image_width,
    source_image_height,
    backup_image_path,
    source_image_filename,
):

    _, file_extension = os.path.splitext(source_image_path)
    file_extension = file_extension.lower()
    if file_extension in EXCLUDED_EXTENSIONS:
        log_message(
            "info",
            "Skipping optimization for excluded image format: {file_extension} for {source_image_path}",
            "general",
            "images",
        )
        return None
    try:
        image_data = list(pil_image.getdata())
        target_mode = "RGBA" if pil_image.mode in ("RGB", "RGBA") else "RGB"
        image_without_exif = Image.new(target_mode, pil_image.size)

        if source_image_mode != target_mode:
            pil_image = pil_image.convert(target_mode)
            image_data = list(pil_image.getdata())

        image_without_exif.putdata(image_data)

        is_banner_image = "banner" in str(source_image_path).lower()
        if is_banner_image:
            image_without_exif = _resize_image(
                image_without_exif,
                BANNER_DIMENSIONS[0],
                BANNER_DIMENSIONS[1],
                force_exact=True,
                source_image_filename=source_image_filename,
            )
        else:
            image_without_exif = _resize_content_image(
                image_without_exif,
                source_image_width,
                source_image_height,
                source_image_filename=source_image_filename,
            )

        return image_without_exif

    except Exception as process_error:
        log_message("warning", f"Error processing image: {process_error}")
        _restore_from_backup(
            backup_image_path, source_image_path, source_image_filename
        )
        return None


def _resize_image(
    pil_image,
    target_width,
    target_height,
    force_exact=False,
    source_image_filename=None,
):
    try:
        if force_exact:
            resized_image = pil_image.resize(
                (target_width, target_height), resample=Image.LANCZOS
            )
            if source_image_filename:
                log_message(
                    "debug",
                    f"Resized image to exact dimensions: {target_width}x{target_height}",
                )
            return resized_image
        return pil_image
    except Exception as resize_error:
        log_message("warning", f"Error resizing image: {resize_error}")
        return pil_image


def _resize_content_image(
    pil_image, source_image_width, source_image_height, source_image_filename=None
):
    max_width, max_height = CONTENT_MAX_DIMENSIONS

    if source_image_width <= max_width and source_image_height <= max_height:
        return pil_image

    if source_image_width > 0 and source_image_height > 0:
        scaling_factor = min(
            max_width / source_image_width, max_height / source_image_height
        )
        if scaling_factor < 1:
            new_width = int(source_image_width * scaling_factor)
            new_height = int(source_image_height * scaling_factor)
            try:
                resized_image = pil_image.resize(
                    (new_width, new_height), resample=Image.LANCZOS
                )
                if source_image_filename:
                    log_message(
                        "debug",
                        f"Resized image: {source_image_width}x{source_image_height} -> {new_width}x{new_height}",
                    )
                return resized_image
            except Exception as resize_error:
                log_message("warning", f"Error resizing content image: {resize_error}")

    return pil_image


def _save_optimized_image(
    optimized_image, optimized_image_path, backup_image_path, source_image_filename
):
    try:
        _, file_extension = os.path.splitext(optimized_image_path)
        file_extension = file_extension.lower()

        if file_extension in [".jpg", ".jpeg"]:
            optimized_image.save(
                optimized_image_path, format="JPEG", **FORMAT_SETTINGS["JPEG"]
            )
        elif file_extension == ".png":
            has_transparency = (
                "A" in optimized_image.mode or "transparency" in optimized_image.info
            )
            if has_transparency:
                optimized_image.save(
                    optimized_image_path, format="PNG", **FORMAT_SETTINGS["PNG"]
                )
            else:
                if optimized_image.mode != "RGB":
                    optimized_image = optimized_image.convert("RGB")
                optimized_image.save(
                    optimized_image_path, format="PNG", **FORMAT_SETTINGS["PNG"]
                )
        elif file_extension == ".webp":
            optimized_image.save(
                optimized_image_path, format="WEBP", **FORMAT_SETTINGS["WEBP"]
            )
        elif file_extension in EXCLUDED_EXTENSIONS:
            log_message(
                "info",
                "Skipping optimization for {source_image_filename}",
                "general",
                "images",
            )
        else:
            optimized_image.save(optimized_image_path)

        return True

    except Exception as save_error:
        log_message(
            "warning",
            f"Error saving optimized image {optimized_image_path}: {save_error}",
        )
        _restore_from_backup(
            backup_image_path, optimized_image_path, source_image_filename
        )
        return False


def _verify_and_check_size_reduction(
    optimized_image_path,
    backup_image_path,
    original_file_size,
    source_image_format,
    source_image_filename,
):
    try:
        with Image.open(optimized_image_path) as verify_image:
            verify_image.verify()
    except Exception as verify_error:
        log_message("warning", f"Optimized image verification failed: {verify_error}")
        _restore_from_backup(
            backup_image_path, optimized_image_path, source_image_filename
        )
        return False

    try:
        new_file_size = os.path.getsize(optimized_image_path)
        size_reduction_percentage = (
            (1 - new_file_size / original_file_size) * 100
            if original_file_size > 0
            else 0
        )

        if (
            new_file_size > original_file_size
            or size_reduction_percentage < MIN_SIZE_REDUCTION_PCT
        ):
            log_message(
                "info",
                f"Optimization not beneficial (size reduction: {size_reduction_percentage:.1f}%), reverting",
                "general",
                "images",
            )

            _restore_from_backup(
                backup_image_path, optimized_image_path, source_image_filename
            )
            return True

        log_message(
            "info",
            f"Optimized {source_image_filename}: {source_image_format} {original_file_size/1024:.1f}KB -> {new_file_size/1024:.1f}KB ({size_reduction_percentage:.1f}% reduction)",
            "general",
            "images",
        )

        return True

    except Exception as size_error:
        log_message("warning", f"Error calculating file size: {size_error}")
        _restore_from_backup(
            backup_image_path, optimized_image_path, source_image_filename
        )
        return False


def optimize_generic_image(sphinx_app=None):
    start_time = datetime.now()
    static_generic_image_path = os.path.join(
        os.path.dirname(os.path.dirname(__file__)),
        "static",
        "images",
        "generic.jpg",
    )

    if os.path.exists(static_generic_image_path):
        log_message(
            "info",
            "Optimizing generic image in static directory: {static_generic_image_path}",
            "general",
            "images",
        )
        optimization_success, webp_image_path = optimize_image(
            static_generic_image_path
        )
        if optimization_success and webp_image_path:
            log_message(
                "info",
                "Successfully optimized static generic image and created WebP version: {webp_image_path}",
                "general",
                "images",
            )
        else:
            log_message(
                "warning",
                f"Failed to optimize static generic image or create WebP version",
            )
    else:
        log_message(
            "warning",
            f"Generic image not found in static directory: {static_generic_image_path}",
        )

    if sphinx_app:
        try:
            rocm_blogs_instance = ROCmBlogs()
            blogs_directory = rocm_blogs_instance.find_blogs_directory(
                sphinx_app.srcdir
            )
            if blogs_directory:
                blogs_generic_image_path = os.path.join(
                    blogs_directory, "images", "generic.jpg"
                )
                if os.path.exists(blogs_generic_image_path):
                    log_message(
                        "info",
                        "Optimizing generic image in blogs directory: {blogs_generic_image_path}",
                        "general",
                        "images",
                    )
                    optimization_success, webp_image_path = optimize_image(
                        blogs_generic_image_path
                    )
                    if optimization_success and webp_image_path:
                        log_message(
                            "info",
                            "Successfully optimized blogs generic image and created WebP version: {webp_image_path}",
                            "general",
                            "images",
                        )
                    else:
                        log_message(
                            "warning",
                            f"Failed to optimize blogs generic image or create WebP version",
                        )
                else:
                    log_message(
                        "warning",
                        f"Generic image not found in blogs directory: {blogs_generic_image_path}",
                    )
        except Exception as generic_optimize_error:
            log_message(
                "warning",
                f"Error optimizing generic image in blogs directory: {generic_optimize_error}",
            )

    end_time = datetime.now()
    total_time = (end_time - start_time).total_seconds()
    total_original_kb = WEBP_CONVERSION_STATISTICS["total_size_original"] / 1024
    total_webp_kb = WEBP_CONVERSION_STATISTICS["total_size_webp"] / 1024
    size_saved_kb = total_original_kb - total_webp_kb

    log_message("info", "=" * 80, "general", "images")
    log_message("info", "IMAGE OPTIMIZATION SUMMARY", "general", "images")
    log_message("info", "-" * 80, "general", "images")
    log_message(
        "info",
        "Total WebP conversions: {WEBP_CONVERSION_STATISTICS['converted']}",
        "general",
        "images",
    )
    log_message(
        "info",
        "Total WebP conversions skipped: {WEBP_CONVERSION_STATISTICS['skipped']}",
        "general",
        "images",
    )
    log_message(
        "info",
        "Total WebP conversions failed: {WEBP_CONVERSION_STATISTICS['failed']}",
        "general",
        "images",
    )
    log_message(
        "info",
        "Total original image size: {total_original_kb:.1f} KB",
        "general",
        "images",
    )
    log_message(
        "info", f"Total WebP image size: {total_webp_kb:.1f} KB", "general", "images"
    )
    log_message(
        "info", f"Total size saved: {size_saved_kb:.1f} KB", "general", "images"
    )
    log_message(
        "info", f"Total time taken: {total_time:.2f} seconds", "general", "images"
    )
    log_message("info", "-" * 80, "general", "images")
    log_message("info", "END OF IMAGE OPTIMIZATION SUMMARY", "general", "images")
    log_message("info", "=" * 80, "general", "images")
