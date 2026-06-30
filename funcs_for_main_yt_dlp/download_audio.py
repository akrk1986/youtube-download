"""Audio extraction functions using yt-dlp."""
import logging
import os
import subprocess
from pathlib import Path

from funcs_for_main_yt_dlp._download_common import (
    DownloadOptions,
    _append_common_flags,
    _build_output_template,
    _get_download_retries,
    _run_yt_dlp_subprocess,
)
from funcs_for_main_yt_dlp.file_organization import get_audio_dir_for_format
from funcs_utils import is_format_error, sanitize_url_for_subprocess, warn_if_auth_error
from funcs_video_info import extract_composer_from_description, get_timeout_for_url, get_video_info
from project_defs import DEFAULT_AUDIO_QUALITY

logger = logging.getLogger(__name__)


def extract_single_format(opts: DownloadOptions, output_folder: Path | str, format_type: str,
                          artist_pat: str | None = None, composer_pat: str | None = None) -> None:
    """Extract audio in a single format using yt-dlp."""
    # Security: Validate URL before passing to subprocess
    sanitized_url = sanitize_url_for_subprocess(url=opts.url)

    # Get appropriate timeout based on URL domain
    timeout = get_timeout_for_url(url=opts.url, video_download_timeout=opts.video_download_timeout)

    # Ensure output folder exists
    output_folder_path = Path(output_folder)
    output_folder_path.mkdir(parents=True, exist_ok=True)

    # For FLAC (lossless), use best quality (0); for lossy formats use default quality
    audio_quality = '0' if format_type == 'flac' else DEFAULT_AUDIO_QUALITY

    output_template, sanitized_title = _build_output_template(opts=opts, output_folder=output_folder)

    download_retries = _get_download_retries()
    yt_dlp_cmd: list[str | Path] = [
        opts.ytdlp_exe,
        '--no-warnings',  # Suppress yt-dlp warnings (format errors handled via retry)
        '--retries', download_retries,  # Retry on connection drops (default: 100)
        '-f', 'bestaudio/best',
        '--extract-audio',
        '--audio-format', format_type,
        '--audio-quality', audio_quality,
        '--embed-metadata',
        '--add-metadata',
        '--embed-thumbnail',
        '-o', output_template,
        sanitized_url
    ]

    # Add shared flags (cookies, playlist, progress, custom metadata). For M4A, place the moov atom
    # before mdat (faststart) via the SAME ffmpeg postprocessor-args entry as the custom metadata —
    # a separate '--postprocessor-args ffmpeg:...' would replace it and drop the custom artist/album.
    extra_ffmpeg_args = ['-movflags', '+faststart'] if format_type == 'm4a' else None
    _append_common_flags(cmd=yt_dlp_cmd, opts=opts, sanitized_title=sanitized_title,
                         extra_ffmpeg_args=extra_ffmpeg_args)

    # Add audio-specific flags. Only 'artist' is embedded; Album Artist is left
    # empty for the dupe staging workflow (see README-Dupes.md).
    if artist_pat:
        yt_dlp_cmd[1:1] = ['--parse-metadata', artist_pat]

    # Embed the composer parsed from the (Greek) description, if any.
    if composer_pat:
        yt_dlp_cmd[1:1] = ['--parse-metadata', composer_pat]

    # Force the Album Artist tag empty: yt-dlp's --embed-metadata otherwise carries
    # the source album_artist (YouTube derives it from the artist/uploader) into the
    # file. Album Artist is reserved for the dupe-staging workflow (see README-Dupes.md),
    # so override it to empty during metadata embedding.
    yt_dlp_cmd[1:1] = ['--parse-metadata', ':(?P<meta_album_artist>)']

    # (M4A faststart -movflags is added via _append_common_flags' extra_ffmpeg_args above, so it
    # shares the single 'ffmpeg:' postprocessor-args entry with the custom artist/album metadata.)

    # Optional ffmpeg audio filter from FFMPEG_OPTS env var (e.g. 'volume=2.0' or
    # 'loudnorm=I=-16:TP=-1.5:LRA=11'). Mirrors the losslesscut-csv FFMPEG_OPTS convention.
    # Scope to ExtractAudio only: a bare 'ffmpeg:' prefix would also apply the filter to
    # EmbedThumbnail / Metadata postprocessors, which use '-c copy' and would crash on '-af'.
    ffmpeg_opts = os.environ.get('FFMPEG_OPTS', '').strip()
    if ffmpeg_opts:
        yt_dlp_cmd.extend(['--postprocessor-args', f'ExtractAudio+ffmpeg:-af {ffmpeg_opts}'])
        logger.info(f"Applying FFMPEG_OPTS audio filter: '{ffmpeg_opts}'")

    logger.info(f'Downloading and extracting {format_type.upper()} audio with yt-dlp')
    logger.info(f'Using timeout of {timeout} seconds for {format_type.upper()} audio download')

    # Run download with error handling
    # Note: In playlists, some videos may be unavailable, which is not considered an error
    try:
        _run_yt_dlp_subprocess(cmd=yt_dlp_cmd, timeout=timeout,
                               show_progress=opts.show_progress,
                               label=f'{format_type.upper()} audio download',
                               url=opts.url)
    except subprocess.TimeoutExpired:
        logger.error(f"{format_type.upper()} audio download timed out after {timeout} seconds for URL '{opts.url}'")
        if not opts.is_it_playlist:
            raise RuntimeError(f"Audio download timed out for '{opts.url}'") from None
    except subprocess.CalledProcessError as e:
        # Check if this is a format error - suppress it, only log non-format errors
        error_output = (e.stderr or '') + (e.stdout or '')
        if is_format_error(error_output):
            # Format error - the bestaudio/best fallback should have worked, but didn't
            # This is unusual, log at debug level and continue
            logger.debug(f'{format_type.upper()} format not available for this video')
            if opts.is_it_playlist:
                logger.warning(f"Some videos in playlist '{opts.url}' may have failed, continuing...")
            return  # Don't raise for format errors - the format simply isn't available
        # Non-format error
        logger.error(f"{format_type.upper()} audio download failed for URL '{opts.url}' (exit code {e.returncode})")
        if e.stderr:
            logger.error(f'Error details: {e.stderr}')
        warn_if_auth_error(error_text=error_output)
        if opts.is_it_playlist:
            logger.warning(f"Some videos in playlist '{opts.url}' may have failed, continuing...")
        else:
            raise RuntimeError(f"Failed to download {format_type.upper()} audio from '{opts.url}': {e.stderr}") from e


def extract_audio_with_ytdlp(opts: DownloadOptions, audio_formats: list[str]) -> None:
    """Use yt-dlp to download and extract audio with metadata and thumbnail."""

    # For a single video, check if video has 'artist' or 'uploader' tags.
    # Use either to embed the 'artist' tag in the audio file (Album Artist is left
    # empty for the dupe staging workflow -- see README-Dupes.md).
    artist_pat = None
    composer_pat = None

    if opts.is_it_playlist:
        logger.info('URL is a playlist, cannot extract artist/uploader')
    else:
        video_info = get_video_info(yt_dlp_path=Path(opts.ytdlp_exe), url=opts.url,
                                    video_download_timeout=opts.video_download_timeout)
        artist = video_info.get('artist')
        uploader = video_info.get('uploader')
        have_artist = bool(artist and artist not in ('NA', ''))
        have_uploader = bool(uploader and uploader not in ('NA', ''))

        if have_artist:
            artist_pat = 'artist:%(artist)s'
            logger.info(f"Video has artist: '{artist}'")
        elif have_uploader:
            artist_pat = 'artist:%(uploader)s'

        # Parse the song composer from the (Greek) description, if credited.
        composer = extract_composer_from_description(description=video_info.get('description') or '')
        if composer:
            logger.info(f"Composer detected in description: '{composer}'")
            # FROM half of --parse-metadata is a yt-dlp output template, so a literal
            # '%' must be escaped to '%%'. TO captures the whole value into meta_composer.
            escaped_composer = composer.replace('%', '%%')
            composer_pat = f'{escaped_composer}:(?P<meta_composer>.+)'

    # Extract each requested audio format
    timeout = get_timeout_for_url(url=opts.url, video_download_timeout=opts.video_download_timeout)
    logger.info(f'Using timeout of {timeout} seconds for audio extraction')
    for audio_format in audio_formats:
        # Get the appropriate output directory for this format
        output_dir = Path(get_audio_dir_for_format(audio_format=audio_format)).resolve()
        extract_single_format(opts=opts, output_folder=output_dir, format_type=audio_format,
                              artist_pat=artist_pat, composer_pat=composer_pat)
