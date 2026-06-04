"""Field/atom mapping and change records for copying audio tags into video files.

The tag container is common_av.tags.AudioTags and the atom names are common_av's MP4_*
constants; this module only adds the display-time field->atom->label table and the
per-field change record used by the dry-run report.
"""
from dataclasses import dataclass

from common_av.tags import MP4_ALBUM, MP4_ARTIST, MP4_COMMENT, MP4_COPYRIGHT, MP4_DATE, MP4_TITLE

# (AudioTags attribute, MP4 atom written to the video, human label) in display order.
# Composer is routed to MP4_COPYRIGHT (©cpy) to match common_av.write_mp4_video_tags, which
# puts it there so it shows in VLC's General tab (Copyright); reading the same atom keeps
# this dry-run display in agreement with what the writer actually writes.
FIELD_ATOM_LABELS: tuple[tuple[str, str, str], ...] = (
    ('title', MP4_TITLE, 'title'),
    ('artist', MP4_ARTIST, 'artist'),
    ('album', MP4_ALBUM, 'album (program)'),
    ('year', MP4_DATE, 'year'),
    ('composer', MP4_COPYRIGHT, 'composer (Copyright)'),
    ('comment', MP4_COMMENT, 'comment'),
)


@dataclass(frozen=True)
class FieldChange:
    """A single field's existing-vs-new transition on the target video file."""

    label: str
    atom: str
    old_value: str
    new_value: str

    @property
    def will_write(self) -> bool:
        """True when the new value is non-empty and differs from the existing one.

        An empty source value never clobbers a populated video field.
        """
        return bool(self.new_value) and self.new_value != self.old_value
