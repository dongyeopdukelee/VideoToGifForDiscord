import asyncio
import discord
import json
import requests
import time
import logging
import sys
import urllib

GFYCAT_UPLOAD_URL = "https://api.gfycat.com/v1/gfycats"
GFYCAT_CHECK_URL = "https://api.gfycat.com/v1/gfycats/fetch/status/"
GFYCAT_GET_URL = "https://api.gfycat.com/v1/gfycats/"
GFYCAT_GET_TOKEN = "https://api.gfycat.com/v1/oauth/token"

logging.basicConfig(stream=sys.stdout)
log = logging.getLogger(__name__)
log.setLevel(logging.INFO)

with open('credentials.json') as credentialsFile:
    creds = json.load(credentialsFile)
    discordToken = creds['discordToken']
    gfycatGrant = creds['gfycatGrant']
    gfycatId = creds['gfycatId']
    gfycatSecret = creds['gfycatSecret']

with open('supported_websites.json') as f:
    supportedWebsites = json.load(f)

class UrlUtils:

    @staticmethod
    def isSupported(link):
        try:
            url = urllib.parse.urlparse(link)
            if 'youtu.be' in url.hostname:
                return UrlUtils.youtu(url)
            if 'youtube.com' in url.hostname:
                return UrlUtils.youtube(url)
            if 'twitch.tv' in url.hostname:
                return UrlUtils.twitch(url)
            return False
        except:
            return False

    @staticmethod
    def youtu(url):
        return not url.path == ''

    @staticmethod
    def youtube(url):
        return 'watch' in url.path

    @staticmethod
    def twitch(url):
        return '/clip/' in url.path

    @staticmethod
    def getStartingTime(link):
        try:
            url = urllib.parse.urlparse(link)
            for param in url.query.split('&'):
                if 't=' in param:
                    return int(param[2:])
        except:
            return 0

class MyClient(discord.Client):
    gfycatGrant = ''
    startTime = 0
    endTime = 0

    async def on_ready(self):
        log.info('Logged in as self {0}.'.format(self.user))

    async def on_message(self, message):
        try:
            msgArr = message.content.strip().split()
            for msg in msgArr:
                if UrlUtils.isSupported(msg):
                    webmUrl = await self.getGfycatParent(msg)
                    await self.writeLink(message.channel, webmUrl)
            
            await self.checkIfClose(message.content)

        except NonRetryableError as e:
            log.critical('critical error: killing service.')
            log.critical(repr(e))
            await self.close()
        except Exception as e:
            log.error(repr(e))

    async def checkIfClose(self, content):
        log.info(self.botMentioned(content))
        if 'close' in content.lower() and self.botMentioned(content):
            await self.close()

    def botMentioned(self, content):
        return f'<@!{str(self.user.id)}>' in content

    async def getGfycatParent(self, link):
        retryMax = 3
        for retry in range(retryMax):
            try:
                uploadResponse = self.toGfycat(link)
                await self.checkGfycat(uploadResponse)
                return self.getGfycat(uploadResponse)
            except RetryableError:
                log.warn(f'failed to retrieve gif. currently on retry number {str(retry+1)}')
        raise Exception(f'could not retrieve gif {link} after {str(retryMax)} attempts')

    def toGfycat(self, link):
        self.checkGfycatGrant()
        start = UrlUtils.getStartingTime(link)
        headers = {
            'Authorization': f'Bearer {self.gfycatGrant}'
        }
        cut = {
            "cut":  {
                'duration': 15,
                'start': start
            }
        }
        link = {
            'fetchUrl': link
        }
        data = {**cut, **link}
        req = requests.post(GFYCAT_UPLOAD_URL, data = json.dumps(data), headers = headers)
        return req.json()['gfyname']

    async def checkGfycat(self, name):
        self.checkGfycatGrant()
        for wait in range(40): # 10 min
            req = requests.get(GFYCAT_CHECK_URL + name)
            reqjs = req.json()
            log.info(f'checking if gfy {name} is created. Response: {reqjs}')
            if reqjs['task'] == 'complete':
                return reqjs
            elif reqjs['task'] == 'encoding':
                pass
            else:
                raise RetryableError('failed to retrieve video')
            await asyncio.sleep(15)
        raise Exception('timed out while Gfycat was encoding. video was probably too large. request link: '
                       f'{GFYCAT_CHECK_URL + name}')


    def getGfycat(self, name):
        self.checkGfycatGrant()
        req = requests.get(GFYCAT_GET_URL + name)
        return req.json()['gfyItem']['webmUrl']

    async def writeLink(self, channel, link):
        await channel.send(link)

    def getGfycatGrant(self):
        retryMax = 3
        req = ''
        for retry in range(retryMax):
            try:
                data = {
                    'grant_type': 'client_credentials',
                    'client_id': gfycatId,
                    'client_secret': gfycatSecret
                }
                req = requests.post(GFYCAT_GET_TOKEN, data=json.dumps(data))
                if req.status_code == 200:
                    self.startTime = time.time()
                    self.endTime = self.startTime + int(req.json()['expires_in']) - 5
                    self.gfycatGrant = req.json()['access_token']
                    return
            except:
                pass
        
        raise NonRetryableError('could not retrieve auth token. '
                               f'status code: {req.status_code}, response: {req.json()}')
            

    def checkGfycatGrant(self):
        if time.time() > self.endTime:
            self.getGfycatGrant()
            
class RetryableError(Exception):
    pass

class NonRetryableError(Exception):
    pass

client = MyClient()

client.run(discordToken)
