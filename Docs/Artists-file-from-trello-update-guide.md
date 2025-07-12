# How to update artists list after Trello board change

## For use by yt-dlp scripts

### General

When a name change is made in the Trello board (Greek or English name), the JSON file for youtube-download scripts should be updated.

### Steps

1. Navigate to the Trello board:
   [https://trello.com/b/52qtksd7/greek-music-artists](https://trello.com/b/52qtksd7/greek-music-artists)

2. Click on the '...', select '*Print, export, and share*'

3. Select JSON

4. Download the file

5. Replace the blob at the beginning with 'trello' (lowercase) - file name should be:
   - **trello - greek music artists.json**

6. Copy the file to **$HOME/PycharmProjects/youtube-download/Data**

7. In PyCharm project **youtube-download**, run this profile **get-artists-from-trello**

8. The updated JSON file will be saved in the **Data** directory in the project directory, called **artists.json**, size ~17KB