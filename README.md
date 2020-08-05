
# VideoToGifForDiscord

VideoToGifForDiscord is a Python app that takes a monitors a discord channel, triggers when finds a video link, makes a short snippet gif through Gfycat, and uploads it to the same channel. 

This was a weekend project so it's pretty rough around the edges, but I had fun.

## Usage

Install third party libraries:

```
pip install discord.py
pip install requests
```

Pull this repo to your local. 

Request for your personal tokens. 
- Gfycat: https://developers.gfycat.com/
- Discord: https://discordapp.com/developers/applications

Set personal tokens as environment variables.

Run the code. Invite your bot to your channels. I used this guide if you're completely new like I was: https://youtu.be/nW8c7vT6Hl4

## Supported Videos
- YouTube (youtube.com, youtu.be)
- Twitch clips

