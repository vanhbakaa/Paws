import asyncio
import traceback
from itertools import cycle
from time import time
from urllib.parse import unquote
import aiohttp
import requests
from aiocfscrape import CloudflareScraper
from aiohttp_proxy import ProxyConnector
from better_proxy import Proxy
from pyrogram import Client
from pyrogram.errors import Unauthorized, UserDeactivated, AuthKeyUnregistered, FloodWait
from pyrogram.raw.types import InputBotAppShortName
from pyrogram.raw.functions.messages import RequestAppWebView
from bot.core.agents import generate_random_user_agent
from bot.config import settings
import cloudscraper

from bot.utils import logger
from bot.exceptions import InvalidSession
from .headers import headers
from random import randint
import random
from bot.utils.ps import check_base_url


end_point = "https://api.paws.community/v1/"
auth_api = f"{end_point}user/auth"
quest_list = f"{end_point}quests/list"
complete_task = f"{end_point}quests/completed"
claim_task = f"{end_point}quests/claim"


class Tapper:
    def __init__(self, tg_client: Client, multi_thread: bool):
        self.tg_client = tg_client
        self.session_name = tg_client.name
        self.first_name = ''
        self.last_name = ''
        self.user_id = ''
        self.auth_token = ""
        self.multi_thread = multi_thread
        self.access_token = None
        self.balance = 0
        self.my_ref = "sc9bGaHz"
        self.new_account = False

    async def get_tg_web_data(self, proxy: str | None) -> str:
        if settings.REF_LINK == '':
            ref_param = "sc9bGaHz"
        else:
            ref_param = settings.REF_LINK.split('=')[1]
        if proxy:
            proxy = Proxy.from_str(proxy)
            proxy_dict = dict(
                scheme=proxy.protocol,
                hostname=proxy.host,
                port=proxy.port,
                username=proxy.login,
                password=proxy.password
            )
        else:
            proxy_dict = None

        self.tg_client.proxy = proxy_dict
        actual = random.choices([self.my_ref, ref_param], weights=[30, 70], k=1)

        try:
            if not self.tg_client.is_connected:
                try:
                    await self.tg_client.connect()
                except (Unauthorized, UserDeactivated, AuthKeyUnregistered):
                    raise InvalidSession(self.session_name)

            while True:
                try:
                    peer = await self.tg_client.resolve_peer('PAWSOG_bot')
                    break
                except FloodWait as fl:
                    fls = fl.value

                    logger.warning(f"<light-yellow>{self.session_name}</light-yellow> | FloodWait {fl}")
                    logger.info(f"<light-yellow>{self.session_name}</light-yellow> | Sleep {fls}s")

                    await asyncio.sleep(fls + 3)

            web_view = await self.tg_client.invoke(RequestAppWebView(
                peer=peer,
                app=InputBotAppShortName(bot_id=peer, short_name="PAWS"),
                platform='android',
                write_allowed=True,
                start_param=actual[0]
            ))
            self.my_ref = actual[0]

            auth_url = web_view.url
            tg_web_data = unquote(string=auth_url.split('tgWebAppData=')[1].split('&tgWebAppVersion')[0])

            if self.tg_client.is_connected:
                await self.tg_client.disconnect()

            return tg_web_data

        except InvalidSession as error:
            raise error

        except Exception as error:
            logger.error(f"<light-yellow>{self.session_name}</light-yellow> | Unknown error during Authorization: "
                         f"{error}")
            await asyncio.sleep(delay=3)


    async def join_channel(self):
        try:
            logger.info(f"{self.session_name} | Joining TG channel...")
            if not self.tg_client.is_connected:
                try:
                    await self.tg_client.connect()
                except (Unauthorized, UserDeactivated, AuthKeyUnregistered):
                    raise InvalidSession(self.session_name)
            try:
                await self.tg_client.join_chat("pawsupfam")
                logger.success(f"{self.session_name} | <green>Joined channel successfully</green>")
            except Exception as e:
                logger.error(f"{self.session_name} | <red>Join TG channel failed - Error: {e}</red>")

            if self.tg_client.is_connected:
                await self.tg_client.disconnect()

            return

        except Exception as error:
            logger.error(f"<light-yellow>{self.session_name}</light-yellow> | Unknown error during Authorization: "
                         f"{error}")
            await asyncio.sleep(delay=3)
    async def check_proxy(self, http_client: aiohttp.ClientSession, proxy: Proxy) -> None:
        try:
            response = await http_client.get(url='https://ipinfo.io/json', timeout=aiohttp.ClientTimeout(20))
            response.raise_for_status()

            response_json = await response.json()
            ip = response_json.get('ip', 'NO')
            country = response_json.get('country', 'NO')

            logger.info(f"{self.session_name} |🟩 Logging in with proxy IP {ip} and country {country}")
        except Exception as error:
            logger.error(f"{self.session_name} | Proxy: {proxy} | Error: {error}")

    async def login(self, http_client: cloudscraper.CloudScraper):
        try:
            payload = {
                    "data": self.auth_token,
                    "referralCode": self.my_ref
                }
            login = http_client.post(auth_api, json=payload)
            if login.status_code == 201:
                res = login.json()
                data = res['data']
                # print(res)
                self.access_token = res['data'][0]
                logger.success(f"{self.session_name} | <green>Successfully logged in!</green>")
                return data
            else:
                print(login.text)
                logger.warning(f"{self.session_name} | <yellow>Failed to login: {login.status_code}</yellow>")
                return None
        except Exception as e:
            # traceback.print_exc()
            logger.error(f"{self.session_name} | Unknown error while trying to login: {e}")
            return None

    async def get_tasks(self, http_client: cloudscraper.CloudScraper):
        try:
            logger.info(f"{self.session_name} | Getting tasks list...")
            tasks = http_client.get(quest_list)
            if tasks.status_code == 200:
                res = tasks.json()
                data = res['data']
                # print(res)
                return data
            else:
                logger.warning(f"{self.session_name} | <yellow>Failed to get task: {tasks.status_code}</yellow>")
                return None
        except Exception as e:
            # traceback.print_exc()
            logger.error(f"{self.session_name} | Unknown error while trying to get tasks: {e}")
            return None

    async def claim_task(self, task, http_client: cloudscraper.CloudScraper, attempt=10):
        if attempt == 0:
            return False
        try:
            payload = {
                "questId": task['_id']
            }
            logger.info(
                f"{self.session_name} | Attempt <red>{10 - attempt + 1}</red> to complete task: <cyan>{task['title']}</cyan>")
            tasks = http_client.post(claim_task, json=payload)
            if tasks.status_code == 201:
                res = tasks.json()
                data = res['data']
                if data:
                    logger.success(f"{self.session_name} | <green>Successfully completed task: <cyan>{task['title']}</cyan> - Earned <cyan>{task['rewards'][0]['amount']}</cyan> paws</green>")
                    return True
                else:
                    logger.info(f"{self.session_name} | Failed to claim task: {task['title']}, Retrying...")
                    await asyncio.sleep(random.randint(3, 5))
                    return await self.claim_task(task, http_client, attempt - 1)
            else:
                logger.warning(
                    f"{self.session_name} | <yellow>Failed to complete {task['title']}: {tasks.status_code}</yellow>")
                return await self.claim_task(task, http_client, attempt - 1)
        except Exception as e:
            logger.error(f"{self.session_name} | Unknown error while trying to get tasks: {e}, Retrying...")
            await asyncio.sleep(random.randint(1, 3))
            return await self.claim_task(task, http_client, attempt - 1)

    async def proceed_task(self, task, http_client: cloudscraper.CloudScraper, maxattemp, attempt=10):
        if attempt == 0:
            return False
        try:
            payload = {
                "questId": task['_id']
            }
            logger.info(f"{self.session_name} | Attempt <red>{maxattemp-attempt+1}</red> to complete task: <cyan>{task['title']}</cyan>")
            tasks = http_client.post(complete_task, json=payload)
            if tasks.status_code == 201:
                res = tasks.json()
                data = res['data']
                # print(res)
                if data:
                    logger.success(f"{self.session_name} | <green>Successfully completed <cyan>{task['title']}</cyan></green>")
                    return await self.claim_task(task, http_client, 5)
                else:
                    logger.info(f"{self.session_name} | Waiting to complete task: <cyan>{task['title']}</cyan>...")
                    await asyncio.sleep(random.randint(5, 10))
                    return await self.proceed_task(task, http_client, maxattemp, attempt-1)
            else:
                logger.warning(f"{self.session_name} | <yellow>Failed to complete {task['title']}: {tasks.status_code}</yellow>")
                return await self.proceed_task(task, http_client, maxattemp, attempt-1)
        except Exception as e:
            logger.error(f"{self.session_name} | Unknown error while trying to get tasks: {e}, Retrying...")
            await asyncio.sleep(random.randint(1,3))
            return await self.proceed_task(task, http_client, maxattemp, attempt-1)


    async def run(self, proxy: str | None) -> None:
        access_token_created_time = 0
        proxy_conn = ProxyConnector().from_url(proxy) if proxy else None

        headers["User-Agent"] = generate_random_user_agent(device_type='android', browser_type='chrome')
        http_client = CloudflareScraper(headers=headers, connector=proxy_conn)
        session = cloudscraper.create_scraper()
        if proxy:
            proxy_check = await self.check_proxy(http_client=http_client, proxy=proxy)
            if proxy_check:
                proxy_type = proxy.split(':')[0]
                proxies = {
                    proxy_type: proxy
                }
                session.proxies.update(proxies)
                logger.info(f"{self.session_name} | bind with proxy ip: {proxy}")

        token_live_time = randint(5000, 7000)
        while True:
            can_run = True
            try:
                if check_base_url() is False:
                    can_run = False
                    if settings.ADVANCED_ANTI_DETECTION:
                        logger.warning(
                            "<yellow>Detected index js file change. Contact me to check if it's safe to continue: https://t.me/vanhbakaaa</yellow>")
                    else:
                        logger.warning(
                            "<yellow>Detected api change! Stopped the bot for safety. Contact me here to update the bot: https://t.me/vanhbakaaa</yellow>")

                if can_run:
                    if time() - access_token_created_time >= token_live_time:
                        tg_web_data = await self.get_tg_web_data(proxy=proxy)
                        self.auth_token = tg_web_data
                        access_token_created_time = time()
                        token_live_time = randint(5000, 7000)

                    a = await self.login(session)

                    if a:
                        http_client.headers['Authorization'] = f"Bearer {self.access_token}"
                        session.headers = http_client.headers.copy()
                        user = a[1]
                        ref_counts = user['referralData']['referralsCount']
                        all_info = f"""
                        ===<cyan>{self.session_name}</cyan>===
                        Referrals count: <cyan>{user['referralData']['referralsCount']}</cyan> referrals
                        Toltal paws: <cyan>{user['gameData']['balance']}</cyan> paws
                        Allocation data:
                            |
                            --Hamster: <cyan>{user['allocationData']['hamster']['converted']}</cyan> paws
                            |
                            --Telegram: <cyan>{user['allocationData']['telegram']['converted']}</cyan> paws
                            |
                            --Paws: <cyan>{user['allocationData']['paws']['converted']}</cyan> paws
                            |
                            --Dogs: <cyan>{user['allocationData']['dogs']['converted']}</cyan> paws
                            |
                            --Notcoin: <cyan>{user['allocationData']['notcoin']['converted']}</cyan> paws
                        """
                        logger.info(all_info)

                        await asyncio.sleep(random.randint(1,3))

                        if settings.AUTO_TASK:
                            task_list = await self.get_tasks(session)
                            if task_list:
                                for task in task_list:
                                    if task['code'] == "invite" and ref_counts < 10:
                                        continue
                                    if task['code'] in settings.IGNORE_TASKS:
                                        logger.info(f"{self.session_name} | Skipped {task['code']} task! ")
                                        continue
                                    if task['progress']['claimed'] is False:
                                        if task['code'] == "telegram":
                                            await self.join_channel()
                                            await self.proceed_task(task, session, 3, 3)
                                        else:
                                            await self.proceed_task(task, session, 5, 5)
                                        await asyncio.sleep(random.randint(5, 10))


                    logger.info(f"----<cyan>Completed {self.session_name}</cyan>----")
                    await http_client.close()
                    session.close()
                    return

            except InvalidSession as error:
                raise error

            except Exception as error:
                #traceback.print_exc()
                logger.error(f"{self.session_name} | Unknown error: {error}")
                await asyncio.sleep(delay=randint(60, 120))

async def run_tapper(tg_client: Client, proxy: str | None):
    try:
        sleep_ = randint(1, 15)
        logger.info(f"{tg_client.name} | start after {sleep_}s")
        await asyncio.sleep(sleep_)
        await Tapper(tg_client=tg_client, multi_thread=True).run(proxy=proxy)
    except InvalidSession:
        logger.error(f"{tg_client.name} | Invalid Session")

async def run_tapper1(tg_clients: list[Client], proxies):
    proxies_cycle = cycle(proxies) if proxies else None
    while True:
        for tg_client in tg_clients:
            try:
                await Tapper(tg_client=tg_client, multi_thread=False).run(next(proxies_cycle) if proxies_cycle else None)
            except InvalidSession:
                logger.error(f"{tg_client.name} | Invalid Session")

            sleep_ = randint(settings.DELAY_EACH_ACCOUNT[0], settings.DELAY_EACH_ACCOUNT[1])
            logger.info(f"Sleep {sleep_}s...")
            await asyncio.sleep(sleep_)

        break
