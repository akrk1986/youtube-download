"""Compute tag changes and write them into a target .mp4 video.

Diffs (for the dry-run report) are computed locally against the existing MP4 atoms; the
actual write delegates to common_av.tags.write_mp4_video_tags so the same shared code that
losslesscut-csv uses stamps the video.
"""
import logging
from pathlib import Path

from common_av.tags import AudioTags, write_mp4_video_tags
from mutagen.mp4 import MP4

from funcs_copy_tags_to_video.tag_set import FIELD_ATOM_LABELS, FieldChange

logger = logging.getLogger(__name__)


def _changes_from_atoms(reader: MP4, tags: AudioTags) -> list[FieldChange]:
    """Build the existing-vs-new change list for all six fields.

    Args:
        reader: An mutagen MP4 (or any object exposing .get(atom)) for the target video.
        tags: The values to copy from the audio source.

    Returns:
        list[FieldChange]: One entry per field, in display order.
    """
    changes: list[FieldChange] = []
    for field, atom, label in FIELD_ATOM_LABELS:
        new_value = getattr(tags, field) or ''
        existing = reader.get(atom)
        old_value = str(existing[0]) if existing else ''
        changes.append(FieldChange(label=label, atom=atom, old_value=old_value, new_value=new_value))
    return changes


def compute_changes(video_path: Path, tags: AudioTags) -> list[FieldChange]:
    """Return the planned field changes for a video without modifying it.

    Args:
        video_path: Path to the target .mp4 video.
        tags: The values to copy from the audio source.

    Returns:
        list[FieldChange]: One entry per field, in display order.
    """
    return _changes_from_atoms(reader=MP4(video_path), tags=tags)


def apply_tags_to_video(video_path: Path, tags: AudioTags, dry_run: bool) -> list[FieldChange]:
    """Write the audio tags into the video's MP4 atoms (unless dry_run).

    When dry_run is True the file is left untouched. Otherwise, if at least one field
    would change, the tags are written via common_av.tags.write_mp4_video_tags.

    Args:
        video_path: Path to the target .mp4 video.
        tags: The values to copy from the audio source.
        dry_run: When True, compute changes but do not write.

    Returns:
        list[FieldChange]: One entry per field, in display order.
    """
    changes = compute_changes(video_path=video_path, tags=tags)
    if dry_run:
        return changes

    if any(change.will_write for change in changes):
        write_mp4_video_tags(video_path=video_path, tags=tags)
        logger.debug('Wrote tags to %s', video_path.name)
    return changes
