"""Images uploaded into lesson rich text.

Files live under ``lesson_rich_text/`` with a generated name. That prefix is
deliberately absent from ``core.views.PUBLIC_MEDIA_PREFIXES``, so media stays
behind the same login gate as the lesson itself. This module owns validation,
the size cap, the draft-clone copy and the cleanup of files no lesson body
still references.
"""

from __future__ import annotations

import re
from io import BytesIO
from pathlib import PurePosixPath
from uuid import uuid4

from django.core.files.base import ContentFile

from .models import ContentBlock, RichTextImage

MAX_UPLOAD_BYTES = 2 * 1024 * 1024
MAX_EDGE = 1600
# The format Pillow detected decides the stored extension, so no client filename is trusted.
FORMAT_EXTENSIONS = {"JPEG": "jpg", "PNG": "png", "WEBP": "webp", "GIF": "gif"}
_SRC = re.compile(r'src="(?P<url>[^"]+)"')


def _open_image(upload):
    from PIL import Image, UnidentifiedImageError

    if upload.size > MAX_UPLOAD_BYTES:
        raise ValueError("That image is larger than 2 MB.")
    upload.seek(0)
    try:
        image = Image.open(upload)
    except (UnidentifiedImageError, OSError):
        raise ValueError("Upload a JPEG, PNG, WebP or GIF image.") from None
    image.load()
    return image


def store_image(lesson, upload, created_by=None) -> RichTextImage:
    """Validate, downscale and store one uploaded image for this lesson."""
    from PIL import Image

    image = _open_image(upload)
    extension = FORMAT_EXTENSIONS.get(image.format)
    if extension is None:
        raise ValueError("Upload a JPEG, PNG, WebP or GIF image.")
    if max(image.size) > MAX_EDGE:
        image.thumbnail((MAX_EDGE, MAX_EDGE))
    payload = BytesIO()
    if extension == "jpg" and image.mode not in ("RGB", "L"):
        image = image.convert("RGB")
    image.save(payload, format=image.format)
    record = RichTextImage(lesson=lesson, created_by=created_by)
    # A generated name keeps any client-supplied filename out of the storage path.
    record.file.save(f"{uuid4().hex}.{extension}", ContentFile(payload.getvalue()), save=True)
    return record


def pixel_size(record: RichTextImage) -> tuple[int, int]:
    """Width and height of a stored image, so the editor can reserve its box."""
    from PIL import Image

    with record.file.open("rb") as handle:
        with Image.open(handle) as source:
            return source.size


def media_names(*bodies: str) -> set[str]:
    """Return the media-relative paths referenced by ``src`` attributes in these bodies."""
    from django.conf import settings

    prefix = settings.MEDIA_URL
    names = set()
    for body in bodies:
        for match in _SRC.finditer(body or ""):
            url = match.group("url")
            if url.startswith(prefix):
                names.add(url[len(prefix):].split("?", 1)[0])
    return names


def is_referenced(name: str) -> bool:
    """True when any lesson body still points at this media file, in any edition."""
    return ContentBlock.objects.filter(body__contains=name).exists()


def prune_lesson(lesson) -> int:
    """Delete this lesson's uploaded images that no lesson body references any more.

    The reference check spans every block, so a file shared with a published
    edition or another lesson is never removed.
    """
    removed = 0
    for image in lesson.rich_text_images.all():
        name = image.file.name
        if name and not is_referenced(name):
            image.file.delete(save=False)
            image.delete()
            removed += 1
    return removed


def clone_lesson_images(source, target, copies) -> None:
    """Give a cloned lesson its own image files and point its sections at them.

    A new edition must survive edits to the edition it was copied from, including
    deletion of the source lesson's images. ``copies`` is the draft-clone map that
    already knows which row was copied from which source row.
    """
    replacements = {}
    for image in source.rich_text_images.all():
        copy_pk = copies.target(RichTextImage, image.pk)
        if copy_pk is None or not image.file:
            continue
        copy = RichTextImage.objects.get(pk=copy_pk)
        if not copy.file or copy.file.name == image.file.name:
            # Read and close before writing so no handle is left on the source file.
            with image.file.open("rb") as handle:
                data = handle.read()
            # Re-uploading through the field gives the copy its own path under the new lesson.
            copy.file = ContentFile(data, name=PurePosixPath(image.file.name).name)
            copy.save()
        if copy.file.name != image.file.name:
            replacements[image.file.name] = copy.file.name
    if not replacements:
        return
    for block in target.blocks.all():
        body = block.body
        for old, new in replacements.items():
            body = body.replace(old, new)
        if body != block.body:
            block.body = body
            block.save()
