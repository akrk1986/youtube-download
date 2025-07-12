# Using yt-dlp, download all videos from YT playlist, and extract the MP3 files for them.
# Note: must be run from an admin PowerShell since it invokes an executable file.
param(
    [string]$PlaylistUrl,
    [switch]$audio,
    [switch]$subs
)

# Validate arguments: Only allow --audio, --subs (case-insensitive, exact spelling)
$allowedSwitches = @('audio', 'subs')
$actualSwitches = $MyInvocation.BoundParameters.Keys | Where-Object { $_ -ne 'PlaylistUrl' }
foreach ($switch in $actualSwitches) {
    if ($allowedSwitches -notcontains $switch.ToLower()) {
        Write-Error "Invalid option: -$switch. Only -audio and -subs are allowed."
        exit 1
    }
}

# Prompt for playlist URL if not provided
if (-not $PlaylistUrl) {
    $PlaylistUrl = Read-Host "Enter the YouTube playlist URL"
}
#Write-Error "options: -audio: $audio, -subs: $subs."
#exit 11

# Output folders
$videoFolder = "$PWD\yt-videos"
$audioFolder = "$PWD\yt-audio"

$ytDlpExe = "$HOME\Apps\yt-dlp\yt-dlp.exe"
$ffmpegExe = "$HOME\Apps\yt-dlp\ffmpeg.exe"

if (!(Test-Path $videoFolder)) { New-Item -ItemType Directory -Path $videoFolder | Out-Null }
if (!(Test-Path $audioFolder)) { New-Item -ItemType Directory -Path $audioFolder | Out-Null }

# Subtitle options
$subsOptions = @()
if ($subs) {
    $subsOptions = @(
        "--write-subs",
        "--sub-lang", "el,en,he",
        "--convert-subs", "srt"
    )
}

# 1. Always download video (with optional subtitles)
& "$ytDlpExe" `
    --yes-playlist `
    -f "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]" `
    --merge-output-format mp4 `
    @subsOptions `
    -o "$videoFolder/%(title)s.%(ext)s" `
    "$PlaylistUrl"

# 2. If --audio, extract audio from downloaded video files
if ($audio) {
    # Get all downloaded mp4 files
    $videoFiles = Get-ChildItem -Path $videoFolder -Filter *.mp4
    foreach ($file in $videoFiles) {
        $audioOut = Join-Path $audioFolder ([System.IO.Path]::GetFileNameWithoutExtension($file.Name) + ".mp3")
        # Only extract if the mp3 doesn't exist yet
        if (!(Test-Path $audioOut)) {
            & "$ffmpegExe" -hide_banner -loglevel info -i "$($file.FullName)" -vn -ab 192k -ar 44100 -y "$audioOut"
        }
    }
}
