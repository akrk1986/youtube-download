import yt_dlp
#import json


def is_playlist(url):
    ydl_opts = {
        'quiet': True,
        'no_warnings': True,
        'extract_flat': True,
    }

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        try:
            info = ydl.extract_info(url, download=False)
            return info.get('_type') == 'playlist'
        except Exception as e:
            print(f"Error: {e}")
            return False


def main():
    # Usage
    url = input("enter url: ")
    if is_playlist(url):
        print("It's a playlist")
    else:
        print("It's a single video")

if __name__ == "__main__":
    main()
