import asyncio
import random
import aiohttp
import datetime
import functools
import pandas as pd
from uuid import uuid4
from sys import stderr
from loguru import logger
from eth_account.account import Account
from pyuseragents import random as random_ua
from eth_account.messages import encode_defunct

from settings import donors_wallets, amounts_follows, delay_follows, delay_wallets, retries, follow_from_exel, \
    module, percent_for_unfollow

logger.remove()
logger.add(stderr,
           format="<lm>{time:HH:mm:ss}</lm> | <level>{level}</level> | <blue>{function}:{line}</blue> "
                  "| <lw>{message}</lw>")


def retry_with_backoff(func):
    @functools.wraps(func)
    async def wrapped(*args, **kwargs):
        backoff_in_ms = 100
        x = 0
        while x <= retries:
            try:
                return await func(*args, **kwargs)
            except Exception as e:
                logger.info(f'Error - {e} | Try again...')
                sleep_ms = (backoff_in_ms * 2 ** x +
                            random.uniform(0, 1))
                await asyncio.sleep(sleep_ms / 1000)
                x += 1
        raise

    return wrapped


class ZoraFollower:
    def __init__(self, private_key: str, proxy: str, number_acc: int) -> None:
        self.account = Account().from_key(private_key=private_key)
        self.proxy: str = f"http://{proxy}" if proxy is not None else None
        self.id: int = number_acc
        self.client = None

    async def get_login_nonce(self) -> str:
        response: aiohttp.ClientResponse = await self.client.post(
            url=f'https://privy.zora.co/api/v1/siwe/init',
            json={
                'address': self.account.address,
            },
            proxy=self.proxy
        )
        response_json: dict = await response.json()

        if response_json.get('nonce'):
            return response_json['nonce']
        raise Exception(f'Get login nonce: response {response.text}')

    async def create_message(self) -> str:
        output_date: str = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"
        message: str = f'zora.co wants you to sign in with your Ethereum account:\n' \
                       f'{self.account.address}\n\n' \
                       f'By signing, you are proving you own this wallet and logging in. ' \
                       f'This does not initiate a transaction or cost any fees.\n\n' \
                       f'URI: https://zora.co\n' \
                       f'Version: 1\n' \
                       f'Chain ID: 1\n' \
                       f'Nonce: {await ZoraFollower.get_login_nonce(self)}\n' \
                       f'Issued At: {output_date}\n' \
                       f'Resources:\n' \
                       f'- https://privy.io'
        return message

    @retry_with_backoff
    async def login(self) -> bool:
        message: str = await ZoraFollower.create_message(self)
        await asyncio.sleep(random.uniform(4, 6))
        signature = self.account.sign_message(encode_defunct(text=message)).signature.hex()

        response: aiohttp.ClientResponse = await self.client.post(
            url=f'https://privy.zora.co/api/v1/siwe/authenticate',
            json={
                'message': message,
                'signature': f'0x{signature}',
                'chainId': 'eip155:1',
                'walletClientType': 'metamask',
                'connectorType': 'injected',
            },
            proxy=self.proxy
        )
        if response.status == 200:
            logger.success(f'{self.account.address} | Success login')
            response_json: dict = await response.json()
            self.client.headers['authorization'] = f'Bearer {response_json["token"]}'
            return True
        raise Exception(f'Login: response {response.text}')

    @retry_with_backoff
    async def r_follow(self, address_follow: str) -> None:
        response: aiohttp.ClientResponse = await self.client.post(
            url=f'https://api.zora.co/discover/follow/{address_follow}',
            proxy=self.proxy
        )
        if response.status == 200:
            logger.success(f'Success follow to {address_follow}'
                           if module == 1 else f'Success unfollow from {address_follow}')
            return
        raise Exception(f'Request follow/unfollow : response {response.text}')

    @retry_with_backoff
    async def get_wallet(self) -> str:
        donor_wallet = random.choice(donors_wallets)
        cursor = [
            '620bd45ecda50_66cf1432dfa58dff33a84f5f',  # 50-100
            '620e4804b0768_66d1a6555390b694ffd1933a',  # 100-150
            '6209991da5ce0_66ccbd310111b2450d874b8c',  # 150-200
            '6205a711f63e0_66c89a159eae70dd9a6f3593',  # 200-250
            '6203818a7cee0_66c659dc9eae70dd9a3d08be',  # 250-300
            '62019186701b8_66c451bf9eae70dd9a710271',  # 300-350
            '61fa3e5e9fb98_66bca3819eae70dd9afc9641',  # 350-400
            '61f7a11436ab0_66b9e5b49eae70dd9a5dcc5a',  # 400-450
            '61f2b3adc12e0_66b4bb07aefac3373bc43a97',  # 450-500
        ]
        params = {
            'limit': '50',
            'sort_direction': 'DESC',
        }
        if module == 1:
            params['cursor'] = random.choice(cursor)
        await asyncio.sleep(random.uniform(2, 3))
        response: aiohttp.ClientResponse = await self.client.get(
            f'https://api.zora.co/discover/followers/{donor_wallet}',
            params=params,
            proxy=self.proxy
        )
        if response.status == 200:
            response_json: dict = await response.json()
            if len(response_json['data']) == 0 and module == 1:
                raise Exception(f'Donor wallet - {donor_wallet} have a <500 number of subscribers')
            return random.choice(response_json['data'])['address']
        raise Exception(f'Get wallet: response {response.text}')

    async def follow_unfollow(self) -> None:
        async with aiohttp.ClientSession(headers={
            'accept': 'application/json, text/plain, * / * ',
            'origin': 'https://zora.co',
            'accept-language': 'en-US,en;q=0.9',
            'content-type': 'application/json',
            'sec-ch-ua': '"Not_A Brand";v="8", "Chromium";v="120", "Google Chrome";v="120"',
            'sec-ch-ua-mobile': '?0',
            'sec-ch-ua-platform': '"macOS"',
            'sec-fetch-dest': 'empty',
            'sec-fetch-mode': 'cors',
            'sec-fetch-site': 'same-origin',
            'user-agent': random_ua(),
            'privy-app-id': 'clpgf04wn04hnkw0fv1m11mnb',
            'privy-ca-id': str(uuid4()),
            'privy-client': 'react-auth:1.78.0',
            'privy-client-id': 'client-WY2f8mnC65aGnM2LmXpwBU5GqK3kxYqJoV7pSNRJLWrp6',
            'referer': 'https://zora.co/',
        }) as client:
            self.client = client
            if await ZoraFollower.login(self):
                await asyncio.sleep(random.uniform(4, 6))

                if module == 1:
                    random.shuffle(addresses_for_follow)
                    for follow in range(random.randint(amounts_follows[0], amounts_follows[1])):
                        await ZoraFollower.r_follow(self, addresses_for_follow[follow]) if follow_from_exel else \
                            await ZoraFollower.r_follow(self, await ZoraFollower.get_wallet(self))
                        await asyncio.sleep(random.randint(delay_follows[0], delay_follows[1]))

                else:
                    response: aiohttp.ClientResponse = await self.client.get(
                        f'https://api.zora.co/discover/followers/{self.account.address}',
                        params={
                            'limit': '50',
                            'sort_direction': 'DESC',
                        },
                        proxy=self.proxy
                    )
                    if response.status == 200:
                        response_json: dict = await response.json()
                        amount_followers = response_json['total']
                        for i in range(int(amount_followers * percent_for_unfollow / 100)):
                            await ZoraFollower.r_follow(self, await ZoraFollower.get_wallet(self))
                            await asyncio.sleep(random.randint(delay_follows[0], delay_follows[1]))

    async def get_stat(self):
        async with aiohttp.ClientSession(headers={
            'sec-ch-ua': '"Chromium";v="128", "Not;A=Brand";v="24", "Google Chrome";v="128"',
            'Referer': 'https://zora.co/@deadbeat_blkrtz',
            'baggage': 'sentry-environment=vercel-production,sentry-release=e86be1657d8cb0c14f752ba1d197c103fcd86504,'
                       'sentry-public_key=b47d15718a5343f497259a10c33fd9e2,'
                       'sentry-trace_id=e88658ecf1544387ac4dd97fab407fe8,sentry-sample_rate=0.0075,'
                       'sentry-transaction=%2F%5Buser%5D,sentry-sampled=false',
            'sec-ch-ua-mobile': '?0',
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) '
                          'Chrome/128.0.0.0 Safari/537.36',
            'sentry-trace': 'e88658ecf1544387ac4dd97fab407fe8-9e6e9477402f88c0-0',
            'sec-ch-ua-platform': '"Windows"',
        }) as client:
            response: aiohttp.ClientResponse = await client.get(
                url=f'https://zora.co/api/profiles/{self.account.address}', proxy=self.proxy)
            if response.status == 200:
                response_json: dict = await response.json()
                totalFollowers, totalFollowing = response_json['totalFollowers'], response_json['totalFollowing']
                with open('accounts_data.xlsx', 'rb') as f:
                    e = pd.read_excel(f)
                e.loc[(self.id - 1), 'totalFollowers'] = int(totalFollowers)
                e.loc[(self.id - 1), 'totalFollowing'] = int(totalFollowing)
                e.to_excel('accounts_data.xlsx', header=True, index=False)
                logger.success(f'{self.account.address} Success record stat to file')


async def start_follow(account: list, id_acc: int, semaphore) -> None:
    async with semaphore:
        acc = ZoraFollower(private_key=account[0], proxy=account[1], number_acc=id_acc)

        try:

            await acc.get_stat() if module == 2 else await acc.follow_unfollow()

        except Exception as e:
            logger.error(f'{id_acc} Failed: {str(e)}')

        if module != 2:
            sleep_time = random.randint(delay_wallets[0], delay_wallets[1])
            logger.info(f'Sleep {sleep_time} sec...')
            await asyncio.sleep(sleep_time)


async def main() -> None:
    semaphore: asyncio.Semaphore = asyncio.Semaphore(1)

    tasks: list[asyncio.Task] = [
        asyncio.create_task(coro=start_follow(account=account, id_acc=idx, semaphore=semaphore))
        for idx, account in enumerate(accounts, start=1)
    ]
    await asyncio.gather(*tasks)


if __name__ == '__main__':
    with open('accounts_data.xlsx', 'rb') as file:
        exel = pd.read_excel(file)

    accounts: list[list] = [
        [
            row["Private Key"], row["Proxy"] if isinstance(row["Proxy"], str) else None
        ]
        for index, row in exel.iterrows()
    ]

    addresses_for_follow: list[str] = [
        row["Addresses For Follow"] if isinstance(row["Addresses For Follow"], str) else None
        for index, row in exel.iterrows()
    ]

    addresses_for_follow = [address for address in addresses_for_follow if address is not None]

    logger.info(f'My channel: https://t.me/CryptoMindYep')
    logger.info(f'Total wallets: {len(accounts)}\n')

    asyncio.run(main())

    logger.success('The work completed')
    logger.info('Thx for donat: 0x5AfFeb5fcD283816ab4e926F380F9D0CBBA04d0e')
