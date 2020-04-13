import asyncio
import json
import logging
import sys
import time
import urllib

import discord  # discord.py
import requests

GFYCAT_QUERY = "https://api.gfycat.com/v1/gfycats/"
GFYCAT_CHECK = "https://api.gfycat.com/v1/gfycats/fetch/status/"
GFYCAT_GET_TOKEN = "https://api.gfycat.com/v1/oauth/token/"

logging.basicConfig(stream=sys.stdout)
log = logging.getLogger(__name__)
log.setLevel(logging.INFO)

with open("credentials.json") as credentialsFile:
    credentials = json.load(credentialsFile)
    discord_token = credentials["discord_token"]
    gfycat_id = credentials["gfycat_id"]
    gfycat_secret = credentials["gfycat_secret"]

with open("supported_websites.json") as f:
    supported_websites = json.load(f)


class UrlUtils:
    @staticmethod
    def is_supported(link):
        try:
            url = urllib.parse.urlparse(link)
            if "youtu.be" in url.hostname:
                return UrlUtils.__youtu(url)
            if "youtube.com" in url.hostname:
                return UrlUtils.__youtube(url)
            if "twitch.tv" in url.hostname:
                return UrlUtils.__twitch(url)
            return False
        except:
            return False

    @staticmethod
    def __youtu(url):
        return not url.path == ""

    @staticmethod
    def __youtube(url):
        return "watch" in url.path

    @staticmethod
    def __twitch(url):
        return "/clip/" in url.path

    @staticmethod
    def get_starting_time(link):
        # TODO: currently only supports youtube format. Add more if other websites are supported.
        try:
            url = urllib.parse.urlparse(link)
            for param in url.query.split("&"):
                if "t=" in param:
                    return int(param[2:])
        except:
            # just start from beginning if something fails
            return 0


class MyClient(discord.Client):
    gfycat_grant = ""
    start_time = 0
    end_time = 0

    async def on_ready(self):
        log.info("Logged in as self {0}.".format(self.user))

    async def on_message(self, message):
        try:
            msg_arr = message.content.strip().split()
            for msg in msg_arr:
                if UrlUtils.is_supported(msg):
                    webm_url = await self.get_gfycat(msg)
                    await self.write_link(message.channel, webm_url)

            await self.check_if_close(message.content)

        except CriticalError as e:
            log.critical(f"critical error. killing service. exception: {repr(e)}")
            await self.close()

        except Exception as e:
            log.error(f"could not process message. exception: {repr(e)}")

    async def check_if_close(self, content):
        if "close" in content.lower() and self.bot_mentioned(content):
            await self.close()

    def bot_mentioned(self, content):
        return f"<@!{str(self.user.id)}>" in content

    async def get_gfycat(self, link):
        retry_max = 3
        for retry in range(retry_max):
            try:
                gfy_name = self.upload_to_gfycat(link)
                await self.check_upload_status_gfycat(gfy_name)
                return self.get_uploaded_webm_gfycat(gfy_name)
            except RetryableError:
                log.warning(
                    f"failed to retrieve gif. currently on retry number {str(retry+1)}"
                )

        raise NonRetryableError(
            f"could not retrieve gif {link} after {str(retry_max)} attempts"
        )

    def upload_to_gfycat(self, link):
        try:
            self.check_gfycat_grant()
            start = UrlUtils.get_starting_time(link)
            headers = {"Authorization": f"Bearer {self.gfycat_grant}"}
            cut = {"cut": {"duration": 15, "start": start}}
            link = {"fetchUrl": link}
            data = {**cut, **link}
            req = requests.post(GFYCAT_QUERY, data=json.dumps(data), headers=headers)
            if req.status_code == 200:
                return req.json()["gfyname"]

            log.warning(
                f"for upload request of {link}, received response {req.status_code}: {req.json()}. retrying"
            )
            raise RetryableError()

        except Exception as e:
            raise NonRetryableError(
                f"caught exception while uploading to gfycat. exception: {repr(e)})"
            )

    async def check_upload_status_gfycat(self, name):
        max_wait_seconds = 600
        sleep_length = 30

        # get new grant if grant is old
        self.check_gfycat_grant()

        for wait in range(max_wait_seconds // sleep_length):
            req = requests.get(GFYCAT_CHECK + name)
            req_js = req.json()
            log.info(f"checking if gfy {name} is created. Response: {req_js}")
            if req_js["task"] == "complete":
                return req_js
            elif req_js["task"] == "encoding":
                pass
            else:
                raise RetryableError("failed to retrieve video")
            await asyncio.sleep(sleep_length)

        raise NonRetryableError(
            f"timed out while Gfycat was encoding. video was probably too large. request link: {GFYCAT_CHECK + name}"
        )

    def get_uploaded_webm_gfycat(self, name):
        self.check_gfycat_grant()
        req = requests.get(GFYCAT_QUERY + name)
        return req.json()["gfyItem"]["webmUrl"]

    async def write_link(self, channel, link):
        await channel.send(link)

    def get_gfycat_grant(self):
        retry_max = 3
        req = ""
        for retry in range(retry_max):
            try:
                data = {
                    "grant_type": "client_credentials",
                    "client_id": gfycat_id,
                    "client_secret": gfycat_secret,
                }
                req = requests.post(GFYCAT_GET_TOKEN, data=json.dumps(data))
                if req.status_code == 200:
                    self.start_time = time.time()
                    self.end_time = self.start_time + int(req.json()["expires_in"]) - 5
                    self.gfycat_grant = req.json()["access_token"]
                    return
            except:
                # retry if status code wasn't 200 or if an exception occurred
                pass

        # kill bot if 3 tries all fail
        raise CriticalError(
            "could not retrieve auth token. "
            f"status code: {req.status_code}, response: {req.json()}"
        )

    def check_gfycat_grant(self):
        if time.time() > self.end_time:
            self.get_gfycat_grant()


class RetryableError(Exception):
    pass


class NonRetryableError(Exception):
    pass


class CriticalError(Exception):
    pass


client = MyClient()

client.run(discord_token)
