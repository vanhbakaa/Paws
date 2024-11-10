import asyncio
import base64
import json
import sys
from itertools import cycle
from time import time
import aiohttp
import cloudscraper
from aiocfscrape import CloudflareScraper
from aiofile import AIOFile
from aiohttp_proxy import ProxyConnector
from better_proxy import Proxy
from bot.core.agents import generate_random_user_agent, fetch_version
from bot.config import settings

from bot.utils import logger
from bot.exceptions import InvalidSession
from .headers import headers
from random import randint
import random
from bot.utils.ps import check_base_url
from urllib.parse import unquote



end_point = "https://api.paws.community/v1/"
auth_api = f"{end_point}user/auth"
quest_list = f"{end_point}quests/list"
complete_task = f"{end_point}quests/completed"
claim_task = f"{end_point}quests/claim"
link_wallet = f"{end_point}user/wallet"


class Tapper:
    def __init__(self, query: str, multi_thread: bool, wallet: str | None, wallet_memonic: str | None):
        self.query = query
        fetch_data = unquote(self.query).split("&user=")[1].split("&auth_date=")[0]
        json_data = json.loads(fetch_data)
        self.session_name = json_data['username']
        self.first_name = ''
        self.last_name = ''
        self.user_id = ''
        self.auth_token = ""
        self.multi_thread = multi_thread
        self.access_token = None
        self.balance = 0
        self.my_ref = get_()
        self.new_account = False
        self.wallet = wallet
        self.wallet_connected = False
        self.wallet_memo = wallet_memonic

    async def check_proxy(self, http_client: aiohttp.ClientSession, proxy: Proxy):
        try:
            response = await http_client.get(url='https://ipinfo.io/json', timeout=aiohttp.ClientTimeout(20))
            response.raise_for_status()

            response_json = await response.json()
            ip = response_json.get('ip', 'NO')
            country = response_json.get('country', 'NO')

            logger.info(f"{self.session_name} |🟩 Logging in with proxy IP {ip} and country {country}")
            return True
        except Exception as error:
            logger.error(f"{self.session_name} | Proxy: {proxy} | Error: {error}")
            return False

    async def login(self, http_client: cloudscraper.CloudScraper, retry=3):
        if retry == 0:
            return None
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
                logger.warning(
                    f"{self.session_name} | <yellow>Failed to login: {login.status_code}, retry in 3-5 seconds</yellow>")
                await asyncio.sleep(random.randint(3, 5))
                await self.login(http_client, retry - 1)
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

    async def claim_task(self, task, http_client: cloudscraper.CloudScraper, attempt=10, maxattempt=10):
        if attempt == 0:
            return False
        try:
            payload = {
                "questId": task['_id']
            }
            logger.info(
                f"{self.session_name} | Attempt <red>{maxattempt - attempt + 1}</red> to claim task: <cyan>{task['title']}</cyan>")
            tasks = http_client.post(claim_task, json=payload)
            if tasks.status_code == 201:
                res = tasks.json()
                data = res['data']
                if data:
                    logger.success(
                        f"{self.session_name} | <green>Successfully claimed task: <cyan>{task['title']}</cyan> - Earned <cyan>{task['rewards'][0]['amount']}</cyan> paws</green>")
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
            logger.error(f"{self.session_name} | Unknown error while trying to claim {task['title']}: {e}, Retrying...")
            await asyncio.sleep(random.randint(1, 3))
            return await self.claim_task(task, http_client, attempt - 1)

    async def proceed_task(self, task, http_client: cloudscraper.CloudScraper, maxattemp, attempt=10):
        if attempt == 0:
            return False
        try:
            payload = {
                "questId": task['_id']
            }
            logger.info(
                f"{self.session_name} | Attempt <red>{maxattemp - attempt + 1}</red> to complete task: <cyan>{task['title']}</cyan>")
            tasks = http_client.post(complete_task, json=payload)
            if tasks.status_code == 201:
                res = tasks.json()
                data = res['data']
                # print(res)
                if task['code'] == "wallet" and res.get('success'):
                    logger.success(
                        f"{self.session_name} | <green>Successfully completed <cyan>{task['title']}</cyan></green>")
                    return await self.claim_task(task, http_client, 5, 5)
                elif data:
                    logger.success(
                        f"{self.session_name} | <green>Successfully completed <cyan>{task['title']}</cyan></green>")
                    return await self.claim_task(task, http_client, 5, 5)
                else:
                    logger.info(f"{self.session_name} | Waiting to complete task: <cyan>{task['title']}</cyan>...")
                    await asyncio.sleep(random.randint(5, 10))
                    return await self.proceed_task(task, http_client, maxattemp, attempt - 1)
            else:
                logger.warning(
                    f"{self.session_name} | <yellow>Failed to complete {task['title']}: {tasks.status_code}</yellow>")
                return await self.proceed_task(task, http_client, maxattemp, attempt - 1)
        except Exception as e:
            logger.error(f"{self.session_name} | Unknown error while trying to get tasks: {e}, Retrying...")
            await asyncio.sleep(random.randint(1, 3))
            return await self.proceed_task(task, http_client, maxattemp, attempt - 1)

    async def bind_wallet(self, http_client: cloudscraper.CloudScraper):
        try:
            payload = {
                "wallet": self.wallet
            }
            res = http_client.post(link_wallet, json=payload)

            if res.status_code == 201 and res.json().get("success") is True:
                return True
            else:
                print(res.text)
                return False
        except Exception as e:
            logger.error(f"{self.session_name} | Unknown error while trying to connect wallet: {e}")
            return False

    async def run(self, proxy: str | None, ua:str) -> None:
        access_token_created_time = 0
        proxy_conn = ProxyConnector().from_url(proxy) if proxy else None

        headers["User-Agent"] = ua
        chrome_ver = fetch_version(headers['User-Agent'])
        headers['Sec-Ch-Ua'] = f'"Chromium";v="{chrome_ver}", "Android WebView";v="{chrome_ver}", "Not.A/Brand";v="99"'
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
            else:
                http_client._connector = None

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
                        tg_web_data = self.query
                        self.auth_token = tg_web_data
                        access_token_created_time = time()
                        token_live_time = randint(5000, 7000)

                    a = await self.login(session)

                    if a:
                        http_client.headers['Authorization'] = f"Bearer {self.access_token}"
                        session.headers = http_client.headers.copy()
                        user = a[1]
                        ref_counts = user['referralData']['referralsCount']
                        wallet = user['userData'].get("wallet")
                        if wallet is None:
                            wallet_text = "No wallet"
                        else:
                            self.wallet_connected = True
                            wallet_text = wallet
                        all_info = f"""
                            ===<cyan>{self.session_name}</cyan>===
                            Referrals count: <cyan>{user['referralData']['referralsCount']}</cyan> referrals
                            Wallet connected: <cyan>{wallet_text}</cyan>
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

                        await asyncio.sleep(random.randint(1, 3))

                        if settings.AUTO_CONNECT_WALLET and self.wallet is not None:
                            if wallet is None:
                                logger.info(
                                    f"{self.session_name} | Starting to connect with wallet <cyan>{self.wallet}</cyan>")
                                a = await self.bind_wallet(session)
                                if a:
                                    logger.success(
                                        f"{self.session_name} | <green>Successfully bind with wallet: <cyan>{self.wallet}</cyan></green>")
                                    with open('used_wallets.json', 'r') as file:
                                        wallets = json.load(file)
                                    wallets.update({
                                        self.wallet: {
                                            "memonic": self.wallet_memo,
                                            "used_for": self.session_name
                                        }
                                    })
                                    with open('used_wallets.json', 'w') as file:
                                        json.dump(wallets, file, indent=4)
                                else:
                                    logger.warning(
                                        f"{self.session_name} | <yellow>Failed to bind with wallet: {self.wallet}</yellow>")
                            else:
                                logger.info(f"{self.session_name} | Already bind with wallet: {wallet}")

                        if settings.AUTO_TASK:
                            task_list = await self.get_tasks(session)
                            if task_list:
                                for task in task_list:
                                    if task['code'] == "emojiName":
                                        logger.info(f"{self.session_name} | Can't do task <cyan>{task['title']}</cyan> in query mode!")
                                    if task['code'] == "wallet" and self.wallet_connected is False:
                                        continue
                                    if task['code'] == "invite" and ref_counts < 10:
                                        continue
                                    if task['code'] in settings.IGNORE_TASKS:
                                        logger.info(f"{self.session_name} | Skipped {task['code']} task! ")
                                        continue
                                    if task['progress']['claimed'] is False:
                                        if task['code'] == "telegram":
                                            logger.info("Skipped join channel task")
                                            continue
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
                # traceback.print_exc()
                logger.error(f"{self.session_name} | Unknown error: {error}")
                await asyncio.sleep(delay=randint(60, 120))

def get_():
    abasdowiad = base64.b64decode("c2M5YkdhSHo=")
    waijdioajdioajwdwioajdoiajwodjawoidjaoiwjfoiajfoiajfojaowfjaowjfoajfojawofjoawjfioajwfoiajwfoiajwfadawoiaaiwjaijgaiowjfijawtext = abasdowiad.decode("utf-8")

    return waijdioajdioajwdwioajdoiajwodjawoidjaoiwjfoiajfoiajfojaowfjaowjfoajfojawofjoawjfioajwfoiajwfoiajwfadawoiaaiwjaijgaiowjfijawtext


async def run_query_tapper(query: str, proxy: str | None, wallet: str | None, wallet_memonic: str | None, ua: str):
    try:
        sleep_ = randint(15, 60)
        logger.info(f" start after {sleep_}s")
        await asyncio.sleep(sleep_)
        await Tapper(query=query, multi_thread=False, wallet=wallet, wallet_memonic=wallet_memonic).run(proxy=proxy, ua=ua)
    except InvalidSession:
        logger.error(f"Invalid Query: {query}")

def fetch_username(query):
    try:
        fetch_data = unquote(query).split("&user=")[1].split("&auth_date=")[0]
        json_data = json.loads(fetch_data)
        return json_data['username']
    except:
        logger.warning(f"Invaild query: {query}")
        sys.exit()


async def get_user_agent(session_name):
    async with AIOFile('user_agents.json', 'r') as file:
        content = await file.read()
        user_agents = json.loads(content)

    if session_name not in list(user_agents.keys()):
        logger.info(f"{session_name} | Doesn't have user agent, Creating...")
        ua = generate_random_user_agent(device_type='android', browser_type='chrome')
        user_agents.update({session_name: ua})
        async with AIOFile('user_agents.json', 'w') as file:
            content = json.dumps(user_agents, indent=4)
            await file.write(content)
        return ua
    else:
        logger.info(f"{session_name} | Loading user agent from cache...")
        return user_agents[session_name]

async def run_query_tapper1(querys: list[str], proxies, wallets):
    proxies_cycle = cycle(proxies) if proxies else None

    while True:
        if settings.AUTO_CONNECT_WALLET:
            wallets_list = list(wallets.keys())
            wallet_index = 0
            if len(wallets_list) < len(querys):
                logger.warning(
                    f"<yellow>Wallet not enough for all accounts please generate <red>{len(querys) - len(wallets_list)}</red> wallets more!</yellow>")
                await asyncio.sleep(3)

            for query in querys:
                if wallet_index >= len(wallets_list):
                    wallet_i = None
                    wallet_memonic = None
                else:
                    wallet_i = wallets_list[wallet_index]
                    wallet_memonic = wallets[wallet_i]
                try:
                    await Tapper(query=query, multi_thread=False, wallet=wallet_i, wallet_memonic=wallet_memonic).run(next(proxies_cycle) if proxies_cycle else None,
                                                                                                                         ua=await get_user_agent(fetch_username(query)))
                except InvalidSession:
                    logger.error(f"{query} is Invalid ")

                sleep_ = randint(settings.DELAY_EACH_ACCOUNT[0], settings.DELAY_EACH_ACCOUNT[1])
                logger.info(f"Sleep {sleep_}s...")
                await asyncio.sleep(sleep_)
        else:
            for query in querys:
                try:
                    await Tapper(query=query, multi_thread=True, wallet=None, wallet_memonic=None).run(next(proxies_cycle) if proxies_cycle else None,
                                                                                                       ua=await get_user_agent(fetch_username(query)))
                except InvalidSession:
                    logger.error(f"Invalid Query: {query}")

                sleep_ = randint(settings.DELAY_EACH_ACCOUNT[0], settings.DELAY_EACH_ACCOUNT[1])
                logger.info(f"Sleep {sleep_}s...")
                await asyncio.sleep(sleep_)

        break

