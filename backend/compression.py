import gzip
from typing import Optional
from fastapi import FastAPI
from starlette.types import ASGIApp, Scope, Receive, Send
from starlette.datastructures import Headers
from backend.config import settings
from backend.logging_config import logger

try:
    import brotli
    HAS_BROTLI = True
except ImportError:
    brotli = None
    HAS_BROTLI = False


class AdvancedCompressionMiddleware:
    """
    Custom ASGI middleware providing GZip and Brotli (if available) response compression.
    Supports configurable minimum size thresholds for API responses, JSON payloads, reports, and exports.
    """
    def __init__(
        self,
        app: ASGIApp,
        minimum_size: int = 500,
        brotli_quality: int = 4,
        gzip_level: int = 6
    ):
        self.app = app
        self.minimum_size = minimum_size
        self.brotli_quality = brotli_quality
        self.gzip_level = gzip_level

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        headers = Headers(scope=scope)
        accept_encoding = headers.get("accept-encoding", "").lower()

        # Determine compression preference: Brotli ('br') > GZip ('gzip')
        use_br = HAS_BROTLI and ("br" in accept_encoding)
        use_gzip = ("gzip" in accept_encoding) and not use_br

        if not (use_br or use_gzip):
            await self.app(scope, receive, send)
            return

        initial_message = None
        started = False

        async def custom_send(message: dict) -> None:
            nonlocal initial_message, started
            if message["type"] == "http.response.start":
                initial_message = message
                return
            elif message["type"] == "http.response.body":
                body = message.get("body", b"")
                more_body = message.get("more_body", False)

                # Compress single-chunk or non-streaming response body if size >= threshold
                if not started and not more_body and len(body) >= self.minimum_size:
                    try:
                        if use_br and brotli is not None:
                            compressed_body = brotli.compress(body, quality=self.brotli_quality)
                            encoding_header = b"br"
                        else:
                            compressed_body = gzip.compress(body, compresslevel=self.gzip_level)
                            encoding_header = b"gzip"

                        # Rebuild headers with new Content-Encoding and Content-Length
                        raw_headers = initial_message.get("headers", [])
                        new_headers = [
                            (k, v) for k, v in raw_headers
                            if k.lower() not in (b"content-length", b"content-encoding")
                        ]
                        new_headers.append((b"content-encoding", encoding_header))
                        new_headers.append((b"content-length", str(len(compressed_body)).encode("latin-1")))
                        initial_message["headers"] = new_headers

                        await send(initial_message)
                        started = True
                        await send({"type": "http.response.body", "body": compressed_body, "more_body": False})
                        return
                    except Exception as exc:
                        logger.warning(f"Error compressing HTTP response payload: {exc}")

                if not started and initial_message:
                    await send(initial_message)
                    started = True
                await send(message)

        await self.app(scope, receive, custom_send)


def setup_compression_middleware(app: FastAPI) -> None:
    """
    Configures and attaches response compression middleware to the FastAPI app.
    Uses AdvancedCompressionMiddleware for Brotli and GZip compression with threshold limits.
    """
    if not getattr(settings, "COMPRESSION_ENABLED", True):
        logger.info("HTTP response compression is disabled in settings.")
        return

    min_size = getattr(settings, "COMPRESSION_MINIMUM_SIZE", 500)
    brotli_quality = getattr(settings, "COMPRESSION_BROTLI_QUALITY", 4)
    gzip_level = getattr(settings, "COMPRESSION_GZIP_LEVEL", 6)

    app.add_middleware(
        AdvancedCompressionMiddleware,
        minimum_size=min_size,
        brotli_quality=brotli_quality,
        gzip_level=gzip_level
    )
    logger.info(
        f"Attached AdvancedCompressionMiddleware (minimum_size={min_size}B, "
        f"brotli_available={HAS_BROTLI}, brotli_quality={brotli_quality}, gzip_level={gzip_level})"
    )
