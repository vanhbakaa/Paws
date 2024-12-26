import asyncio
import base64
import json
import sys
from time import time
from urllib.parse import unquote
import aiohttp
from aiocfscrape import CloudflareScraper
from aiohttp_proxy import ProxyConnector
from better_proxy import Proxy
from pyrogram import Client
from pyrogram.errors import Unauthorized, UserDeactivated, AuthKeyUnregistered, FloodWait
from pyrogram.raw.types import InputBotAppShortName
from pyrogram.raw.functions.messages import RequestAppWebView
from bot.core.agents import generate_random_user_agent, fetch_version
from bot.config import settings
import cloudscraper

from bot.utils import logger
from bot.exceptions import InvalidSession
from .headers import headers
from random import randint
import random
from bot.utils.ps import check_base_url
from aiofile import AIOFile
from bot.utils import launcher as lc

end_point = "https://api.paws.community/v1/"
auth_api = f"{end_point}user/auth"
quest_list = f"{end_point}quests/list"
complete_task = f"{end_point}quests/completed"
claim_task = f"{end_point}quests/claim"
link_wallet = f"{end_point}user/wallet"
grinch_api = f"{end_point}user/grinch"


class Tapper:
    def __init__(self, tg_client: Client, multi_thread: bool, wallet: str | None, wallet_memonic: str | None):
        self.tg_client = tg_client
        self.session_name = tg_client.name
        self.first_name = ''
        self.last_name = ''
        self.user_id = ''
        self.auth_token = ""
        self.multi_thread = multi_thread
        self.access_token = None
        self.balance = 0
        self.my_ref = get_("paws")
        self.new_account = False
        self.wallet = wallet
        self.wallet_connected = False
        self.wallet_memo = wallet_memonic
        self.black_list = ['6742a9559f3873c36978389d', "6742a9639f3873c36978389f", "6742a9499f3873c36978389b"]

    async def get_tg_web_data(self, proxy: str | None, ref_link, short_name, peer) -> str:
        logger.info(f"{self.session_name} | Opening {peer}...")
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
        # print(short_name, peer)
        self.tg_client.proxy = proxy_dict
        actual = random.choices([self.my_ref, ref_link], weights=[30, 70], k=1)

        try:
            if not self.tg_client.is_connected:
                try:
                    await self.tg_client.connect()
                    start_command_found = False
                    async for message in self.tg_client.get_chat_history(peer):
                        if (message.text and message.text.startswith('/start')) or (
                                message.caption and message.caption.startswith('/start')):
                            start_command_found = True
                            break
                    if not start_command_found:
                        await self.tg_client.send_message(peer, "/start")
                except (Unauthorized, UserDeactivated, AuthKeyUnregistered):
                    raise InvalidSession(self.session_name)

            while True:
                try:
                    peer = await self.tg_client.resolve_peer(peer)
                    break
                except FloodWait as fl:
                    fls = fl.value

                    logger.warning(f"<light-yellow>{self.session_name}</light-yellow> | FloodWait {fl}")
                    logger.info(f"<light-yellow>{self.session_name}</light-yellow> | Sleep {fls}s")

                    await asyncio.sleep(fls + 3)

            web_view = await self.tg_client.invoke(RequestAppWebView(
                peer=peer,
                app=InputBotAppShortName(bot_id=peer, short_name=short_name),
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

    async def add_icon(self):
        try:
            if not self.tg_client.is_connected:
                await self.tg_client.connect()

            me = await self.tg_client.get_me()
            name = randint(1, 2)
            if "▪️" not in f"{str(me.first_name)} {str(me.last_name)}":
                if name == 1:
                    if me.first_name is not None:
                        new_display_name = f"{me.first_name} 🐾"
                    else:
                        new_display_name = "▪️"
                    await self.tg_client.update_profile(first_name=new_display_name)
                else:
                    if me.last_name is not None:
                        new_display_name = f"{me.last_name} 🐾"
                    else:
                        new_display_name = "▪️"
                    await self.tg_client.update_profile(last_name=new_display_name)
                logger.success(f"{self.session_name} | 🟩 Display name updated to: {new_display_name}")

            if self.tg_client.is_connected:
                await self.tg_client.disconnect()

        except Exception as error:
            if self.tg_client.is_connected:
                await self.tg_client.disconnect()
            logger.error(f"{self.session_name} | 🟥 Error while changing username: {error}")
            await asyncio.sleep(delay=3)

    async def join_channel(self, channel_link):
        try:
            logger.info(f"{self.session_name} | Joining TG channel...")
            if not self.tg_client.is_connected:
                try:
                    await self.tg_client.connect()
                except (Unauthorized, UserDeactivated, AuthKeyUnregistered):
                    raise InvalidSession(self.session_name)
            while True:
                try:
                    await self.tg_client.join_chat(channel_link)
                    logger.success(f"{self.session_name} | <green>Joined channel successfully</green>")
                    break
                except Exception as e:
                    if "[420 FLOOD_WAIT_X]" in str(e):
                        logger.info("Floodwait encountered wait 10 seconds before continue...")
                        await asyncio.sleep(randint(10, 15))
                    elif "[400 USER_ALREADY_PARTICIPANT]" in str(e):
                        logger.info(f"{self.session_name} | Already joined this chat!")
                        return
                    else:
                        logger.error(f"{self.session_name} | <red>Join TG channel failed - Error: {e}</red>")
                        return
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

    async def get_task_2(self, http_client: cloudscraper.CloudScraper):
        try:
            logger.info(f"{self.session_name} | Getting christmas tasks...")
            tasks = http_client.get(f"{quest_list}?type=christmas")
            if tasks.status_code == 200:
                res = tasks.json()
                data = res['data']
                # print(res)
                return data
            else:
                logger.warning(f"{self.session_name} | <yellow>Failed to get christmas task: {tasks.status_code}</yellow>")
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
                # print(res)
                if "data" in list(res.keys()):
                    data = res['success']
                    if data:
                        try:
                            logger.success(
                                f"{self.session_name} | <green>Successfully claimed task: <cyan>{task['title']}</cyan> - Earned <cyan>{task['rewards'][0]['amount']}</cyan> paws</green>")
                        except:
                            logger.success(
                                f"{self.session_name} | <green>Successfully claimed task: {task['title']}</green>")
                        return True
                    else:
                        logger.info(f"{self.session_name} | Failed to claim task: {task['title']}, Retrying...")
                        await asyncio.sleep(random.randint(3, 5))
                        return await self.claim_task(task, http_client, attempt - 1)
                else:
                    if tasks.json().get("success"):
                        logger.success(f"{self.session_name} | <green>Successfully claimed task: {task['title']}</green>")
                        return True
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

    async def active_grinch(self, http_client: cloudscraper.CloudScraper):
        try:
            res = http_client.post(grinch_api)
            if res.status_code == 201 and res.json().get("success") is True:
                logger.success(f"{self.session_name} | <green>Grinch successfully actived!</green>")
                return True
            else:
                print(res.text)
                return False
        except Exception as e:
            logger.error(f"{self.session_name} | Unknown error while trying to active grinch: {e}")
            return False



    async def run(self, proxy: str | None, ua: str) -> None:
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
                        try:
                            if settings.REF_LINK == '':
                                ref_param = get_("paws")
                            else:
                                ref_param = settings.REF_LINK.split('=')[1]
                        except:
                            logger.warning(
                                "<yellow>INVAILD REF LINK PLEASE CHECK AGAIN! (PUT YOUR REF LINK NOT REF ID)</yellow>")
                            sys.exit()
                        self.my_ref = get_("paws")
                        tg_web_data = await self.get_tg_web_data(proxy=proxy, ref_link=ref_param, peer="PAWSOG_bot", short_name="PAWS")
                        self.auth_token = tg_web_data
                        access_token_created_time = time()
                        token_live_time = randint(5000, 7000)

                    a = await self.login(session)

                    if a:
                        http_client.headers['Authorization'] = f"Bearer {self.access_token}"
                        session.headers = http_client.headers.copy()
                        user = a[1]

                        # print(user)
                        ref_counts = user['referralData']['referralsCount']
                        grinch = user.get("grinchRemoved")

                        if grinch is None:
                            await self.active_grinch(session)
                            continue

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
                                    self.wallet_connected = True
                                    with open('used_wallets.json', 'w') as file:
                                        json.dump(wallets, file, indent=4)
                                else:
                                    logger.warning(
                                        f"{self.session_name} | <yellow>Failed to bind with wallet: {self.wallet}</yellow>")
                            else:
                                logger.info(f"{self.session_name} | Already bind with wallet: {wallet}")

                        if grinch is False:
                            tasks = await self.get_task_2(session)
                            for task in tasks:
                                if task['progress']['claimed'] is False:
                                    await self.proceed_task(task, session, 3, 3)
                                    await asyncio.sleep(random.randint(5, 10))

                            logger.success(f"{self.session_name} | <green>Completed all christmas tasks. Your paws is back!</green>")

                        if settings.AUTO_TASK:
                            task_list = await self.get_tasks(session)
                            if task_list:
                                for task in task_list:
                                    if task['_id'] in self.black_list:
                                        continue
                                    if task['code'] == "wallet" and self.wallet_connected is False:
                                        continue
                                    if task['code'] == "invite" and ref_counts < 10:
                                        continue
                                    if task['code'] in settings.IGNORE_TASKS:
                                        logger.info(f"{self.session_name} | Skipped {task['code']} task! ")
                                        continue
                                    if task['progress']['claimed'] is False:
                                        if task['code'] == "telegram" or task['code'] == "custom":
                                            if task['code'] == "emojiName":
                                                await self.add_icon()
                                                await asyncio.sleep(random.randint(1, 4))
                                            if task['code'] == "blum":
                                                if settings.DISABLE_JOIN_CHANNEL_TASKS:
                                                    continue
                                                await self.join_channel("blumcrypto")
                                            elif task['code'] == "telegram":
                                                if settings.DISABLE_JOIN_CHANNEL_TASKS:
                                                    continue
                                                channel = task['data'].split("/")[3]

                                                await self.join_channel(channel)
                                            elif task['type'] == "partner-channel" and task['action'] == "link":
                                                if settings.DISABLE_JOIN_CHANNEL_TASKS:
                                                    continue
                                                channel = task['data']
                                                # print(channel)
                                                await self.join_channel(channel)
                                            elif task['type'] == "partner-app" and task['action'] == "link":
                                                if settings.DISABLE_JOIN_CHANNEL_TASKS:
                                                    continue
                                                if task['title'] == "Explore Clayton App":
                                                    ref_param = get_("clay")
                                                    peer = "claytoncoinbot"
                                                    short_name = "game"
                                                    self.my_ref = get_("clay")
                                                elif task['title'] == "Explore DuckChain App":
                                                    ref_param = get_("duck")
                                                    peer = "DuckChain_bot"
                                                    short_name = "quack"
                                                    self.my_ref = get_("duck")
                                                elif task['title'] == "Explore BUMS App":
                                                    ref_param = get_("bums")
                                                    peer = "bums"
                                                    short_name = "app"
                                                    self.my_ref = get_("bums")
                                                else:
                                                    ref_param = get_("paws")
                                                    peer = "PAWSOG_bot"
                                                    short_name = "PAWS"
                                                    self.my_ref = get_("paws")
                                                await self.get_tg_web_data(proxy=proxy, ref_link=ref_param, peer=peer, short_name=short_name)
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
                # traceback.print_exc()
                logger.error(f"{self.session_name} | Unknown error: {error}")
                await asyncio.sleep(delay=randint(60, 120))


def get_(game):
    if game == "paws":
        abasdowiad = base64.b64decode("c2M5YkdhSHo=")
    elif game == "bums":
        abasdowiad = base64.b64decode("cmVmX1pXcDdQTHVR")
    elif game == "duck":
        abasdowiad = base64.b64decode("cENBbDlhdTY=")
    elif game == "clay":
        abasdowiad = base64.b64decode("NjQ5MzIxMTE1NQ==")
    waijdioajdioajwdwioajdoiajwodjawoidjaoiwjfoiajfoiajfojaowfjaowjfoajfojawofjoawjfioajwfoiajwfoiajwfadawoiaaiwjaijgaiowjfijawtext = abasdowiad.decode(
        "utf-8")

    return waijdioajdioajwdwioajdoiajwodjawoidjaoiwjfoiajfoiajfojaowfjaowjfoajfojawofjoawjfioajwfoiajwfoiajwfadawoiaaiwjaijgaiowjfijawtext


async def run_tapper(tg_client: Client, proxy: str | None, wallet: str | None, wallet_memonic: str | None, ua):
    try:
        sleep_ = randint(1, 15)
        logger.info(f"{tg_client.name} | start after {sleep_}s")
        await asyncio.sleep(sleep_)
        await Tapper(tg_client=tg_client, multi_thread=True, wallet=wallet, wallet_memonic=wallet_memonic).run(
            proxy=proxy, ua=ua)
    except InvalidSession:
        logger.error(f"{tg_client.name} | Invalid Session")


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


async def run_tapper1(tg_clients: list[Client], wallets):
    while True:
        if settings.AUTO_CONNECT_WALLET:
            wallets_list = list(wallets.keys())
            wallet_index = 0
            if len(wallets_list) < len(tg_clients):
                logger.warning(
                    f"<yellow>Wallet not enough for all accounts please generate <red>{len(tg_clients) - len(wallets_list)}</red> wallets more!</yellow>")
                await asyncio.sleep(3)

            for tg_client in tg_clients:
                if wallet_index >= len(wallets_list):
                    wallet_i = None
                    wallet_m = None
                else:
                    wallet_i = wallets_list[wallet_index]
                    wallet_m = wallets[wallet_i]
                    wallet_index += 1
                try:
                    await Tapper(tg_client=tg_client, multi_thread=False, wallet=wallet_i,
                                 wallet_memonic=wallet_m).run(proxy=await lc.get_proxy(tg_client.name),
                                                                       ua=await get_user_agent(tg_client.name))
                except InvalidSession:
                    logger.error(f"{tg_client.name} | Invalid Session")

                sleep_ = randint(settings.DELAY_EACH_ACCOUNT[0], settings.DELAY_EACH_ACCOUNT[1])
                logger.info(f"Sleep {sleep_}s...")
                await asyncio.sleep(sleep_)
        else:
            for tg_client in tg_clients:
                try:
                    await Tapper(tg_client=tg_client, multi_thread=False, wallet=None,
                                 wallet_memonic=None).run(proxy=await lc.get_proxy(tg_client.name),
                                                          ua=await get_user_agent(tg_client.name))
                except InvalidSession:
                    logger.error(f"{tg_client.name} | Invalid Session")

                sleep_ = randint(settings.DELAY_EACH_ACCOUNT[0], settings.DELAY_EACH_ACCOUNT[1])
                logger.info(f"Sleep {sleep_}s...")
                await asyncio.sleep(sleep_)

        break
