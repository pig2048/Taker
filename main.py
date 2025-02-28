import asyncio
import json
import random
import time
from eth_account.messages import encode_defunct
from web3 import Web3
import aiohttp
import logging
from fake_useragent import UserAgent
from rich.console import Console
from rich.logging import RichHandler
from rich.panel import Panel
from rich.text import Text


console = Console()


logging.basicConfig(
    level=logging.INFO,
    format="%(message)s",
    handlers=[RichHandler(rich_tracebacks=True, console=console)]
)
logger = logging.getLogger(__name__)

def print_banner():
    banner_text = Text()
    banner_text.append("TakerBot\n", style="bold cyan")
    banner_text.append("Author: ", style="dim white")
    banner_text.append("snifftunes\n", style="bold blue")
    banner_text.append("X: ", style="dim white")
    banner_text.append("https://x.com/snifftunes", style="bold blue underline")
    
    console.print(Panel(
        banner_text,
        border_style="cyan",
        padding=(1, 2),
        title="Welcome",
        title_align="center"
    ))

class TakerMining:
    def __init__(self):
        print_banner()
        self.load_config()
        self.load_activation_status()
        self.load_accounts()
        self.load_proxies()
        self.generate_user_agents()
        
    def load_config(self):
        with open('config.json', 'r') as f:
            self.config = json.load(f)
            console.print("[bold green]配置加载成功 ✓[/]")
            
    def load_activation_status(self):
        
        try:
            with open('activated_accounts.json', 'r') as f:
                self.activated_accounts = json.load(f)
        except FileNotFoundError:
            self.activated_accounts = {}
        
        
        if hasattr(self, 'addresses'):
            self.activated_accounts = {
                addr: status for addr, status in self.activated_accounts.items() 
                if addr in self.addresses
            }
        
        
        with open('activated_accounts.json', 'w') as f:
            json.dump(self.activated_accounts, f, indent=4)
        
        console.print(f"[bold green]激活状态加载成功 ✓[/]")
            
    def load_accounts(self):
        
        with open('accounts.txt', 'r') as f:
            self.private_keys = f.read().splitlines()
        with open('wallet.txt', 'r') as f:
            addresses = f.read().splitlines()
            w3 = Web3()  
            self.addresses = [w3.to_checksum_address(addr) for addr in addresses]
        console.print(f"[bold green]已加载 {len(self.addresses)} 个账户 ✓[/]")
            
    def load_proxies(self):
        with open('proxy.txt', 'r') as f:
            self.proxies = f.read().splitlines()
        console.print("[bold green]代理加载成功 ✓[/]")
            
    def generate_user_agents(self):
        ua = UserAgent()
        self.user_agents = [ua.random for _ in range(len(self.addresses))]
        with open('ua.txt', 'w') as f:
            f.write('\n'.join(self.user_agents))
        console.print("[bold green]UA生成完成 ✓[/]")

    async def get_nonce(self, session, address, headers, proxy, retries=3):
        url = f"{self.config['api']['base_url']}/wallet/generateNonce"
        
        for attempt in range(retries):
            try:
                async with session.post(url, json={"walletAddress": address}, headers=headers, proxy=proxy) as resp:
                    if resp.status != 200:
                        console.print(f"[bold red]🚫 账户 {address}: 获取 nonce 失败，状态码: {resp.status}[/]")
                        if attempt < retries - 1:
                            delay = 3 * (attempt + 1)
                            console.print(f"[yellow]⏳ 账户 {address}: {delay}秒后重试... ({retries-attempt-1}次)[/]")
                            await asyncio.sleep(delay)
                            continue
                        return None
                        
                    data = await resp.json()
                    if not data or 'data' not in data or 'nonce' not in data['data']:
                        console.print(f"[bold red]🚫 账户 {address}: nonce 格式错误[/]")
                        if attempt < retries - 1:
                            delay = 3 * (attempt + 1)
                            console.print(f"[yellow]⏳ 账户 {address}: {delay}秒后重试... ({retries-attempt-1}次)[/]")
                            await asyncio.sleep(delay)
                            continue
                        return None
                        
                    console.print(f"[bold green]✅ 账户 {address}: nonce 获取成功[/]")
                    return data['data']['nonce']
                    
            except Exception as e:
                console.print(f"[bold red]🚫 账户 {address}: 请求异常[/]")
                if attempt < retries - 1:
                    delay = 3 * (attempt + 1)
                    console.print(f"[yellow]⏳ 账户 {address}: {delay}秒后重试... ({retries-attempt-1}次)[/]")
                    await asyncio.sleep(delay)
                    continue
                return None
                
        return None

    async def login(self, session, address, private_key, headers, proxy):
        try:
            nonce = await self.get_nonce(session, address, headers, proxy)
            if not nonce:
                return None
            
            try:
                w3 = Web3()
                message = encode_defunct(text=nonce)
                signed_message = w3.eth.account.sign_message(message, private_key=private_key)
                console.print(f"[bold green]✅ 账户 {address}: 签名完成[/]")
            except Exception as e:
                console.print(f"[bold red]🚫 账户 {address}: 签名失败[/]")
                return None
            
            login_data = {
                "address": address,
                "message": nonce,
                "signature": signed_message.signature.hex(),
                "invitationCode": self.config['invitation_code']
            }
            
            url = f"{self.config['api']['base_url']}/wallet/login"
            try:
                async with session.post(url, json=login_data, headers=headers, proxy=proxy) as resp:
                    data = await resp.json()
                    if data['code'] == 200:
                        console.print(f"[bold green]✅ 账户 {address}: 登录成功[/]")
                        return data['data']['token']
                    console.print(f"[bold red]🚫 账户 {address}: 登录失败[/]")
                    return None
            except Exception as e:
                console.print(f"[bold red]🚫 账户 {address}: 登录请求失败[/]")
                return None
                
        except Exception as e:
            console.print(f"[bold red]🚫 账户 {address}: 登录异常[/]")
            return None

    async def start_mining(self, session, address, token, headers, proxy, retries=3):
        url = f"{self.config['api']['base_url']}/assignment/startMining"
        
        
        headers.update({
            'Authorization': f'Bearer {token}',
            'Accept': 'application/json, text/plain, */*',
            'Accept-Language': 'zh-CN,zh;q=0.9',
            'Accept-Encoding': 'gzip, deflate, br, zstd',
            'Origin': 'https://earn.taker.xyz',
            'Referer': 'https://earn.taker.xyz/',
            'Connection': 'keep-alive',
            'Content-Length': '0',
            'Host': 'lightmining-api.taker.xyz',
            'Sec-Fetch-Dest': 'empty',
            'Sec-Fetch-Mode': 'cors',
            'Sec-Fetch-Site': 'same-site',
            'sec-ch-ua': '"Not A(Brand";v="99", "Google Chrome";v="130", "Chromium";v="130"',
            'sec-ch-ua-mobile': '?0',
            'sec-ch-ua-platform': '"Windows"'
        })
        
        for attempt in range(retries):
            try:
                async with session.post(url, headers=headers, proxy=proxy) as resp:
                    response_text = await resp.text()
                    try:
                        data = json.loads(response_text)
                        if data['code'] == 200:
                            console.print(f"[bold green]✅ 账户 {address}: 节点启动成功[/]")
                            return True
                        
                        console.print(f"[bold red]🚫 账户 {address}: 节点启动失败[/]")
                        console.print(f"[bold red]错误码: {data.get('code')}[/]")
                        console.print(f"[bold red]错误信息: {data.get('msg', '无错误信息')}[/]")
                        console.print(f"[bold red]详细响应: {response_text}[/]")
                        
                        if attempt < retries - 1:
                            delay = 3 * (attempt + 1)
                            console.print(f"[yellow]⏳ 账户 {address}: {delay}秒后重试... ({retries-attempt-1}次)[/]")
                            await asyncio.sleep(delay)
                            continue
                        return False
                    except json.JSONDecodeError:
                        console.print(f"[bold red]🚫 账户 {address}: 响应格式错误[/]")
                        console.print(f"[bold red]原始响应: {response_text}[/]")
                        if attempt < retries - 1:
                            delay = 3 * (attempt + 1)
                            console.print(f"[yellow]⏳ 账户 {address}: {delay}秒后重试... ({retries-attempt-1}次)[/]")
                            await asyncio.sleep(delay)
                            continue
                        return False
                    
            except Exception as e:
                console.print(f"[bold red]🚫 账户 {address}: 节点启动请求异常: {str(e)}[/]")
                if attempt < retries - 1:
                    delay = 3 * (attempt + 1)
                    console.print(f"[yellow]⏳ 账户 {address}: {delay}秒后重试... ({retries-attempt-1}次)[/]")
                    await asyncio.sleep(delay)
                    continue
                return False
        
        return False

    async def get_mining_time(self, session, address, token, headers, proxy, retries=3):
        url = f"{self.config['api']['base_url']}/assignment/totalMiningTime"
        headers['Authorization'] = f"Bearer {token}"
        
        for attempt in range(retries):
            try:
                async with session.get(url, headers=headers, proxy=proxy) as resp:
                    data = await resp.json()
                    if data['code'] == 200:
                        total_hours = data['data']['totalMiningTime'] / (1000 * 60 * 60)
                        last_mining_time = data['data'].get('lastMiningTime', 0) / 1000
                        console.print(f"[bold magenta]⏱️ 账户 {address}: 总挖矿时间 {total_hours:.2f}小时[/]")
                        
                        
                        current_time = time.time()
                        next_mining_time = last_mining_time + 24 * 60 * 60  
                        if current_time < next_mining_time:
                            remaining_hours = (next_mining_time - current_time) / 3600
                            console.print(f"[yellow]⏳ 账户 {address}: 冷却中，还需等待 {remaining_hours:.2f}小时[/]")
                            return False
                        return True
                    
                    console.print(f"[bold red]🚫 账户 {address}: 获取挖矿时间失败，错误码: {data.get('code')}[/]")
                    if attempt < retries - 1:
                        delay = 3 * (attempt + 1)
                        console.print(f"[yellow]⏳ 账户 {address}: {delay}秒后重试... ({retries-attempt-1}次)[/]")
                        await asyncio.sleep(delay)
                        continue
                    return False
                    
            except Exception as e:
                console.print(f"[bold red]🚫 账户 {address}: 获取挖矿时间请求异常[/]")
                if attempt < retries - 1:
                    delay = 3 * (attempt + 1)
                    console.print(f"[yellow]⏳ 账户 {address}: {delay}秒后重试... ({retries-attempt-1}次)[/]")
                    await asyncio.sleep(delay)
                    continue
                return False
        
        return False

    async def check_contract(self, session, address, headers, proxy, retries=3):
        url = "https://rpc-mainnet.taker.xyz/"
        payload = {
            "jsonrpc": "2.0",
            "id": 3,
            "method": "eth_call",
            "params": [
                {
                    "data": "0x02fb0c5e",
                    "from": address,
                    "to": "0xB3eFE5105b835E5Dd9D206445Dbd66DF24b912AB"
                },
                "latest"
            ]
        }
        
        for attempt in range(retries):
            try:
                async with session.post(url, json=payload, headers=headers, proxy=proxy) as resp:
                    data = await resp.json()
                    if 'result' in data:
                        
                        mining_time_url = f"{self.config['api']['base_url']}/assignment/totalMiningTime"
                        headers['Authorization'] = f"Bearer {token}" if 'token' in locals() else ""
                        async with session.get(mining_time_url, headers=headers, proxy=proxy) as mining_resp:
                            mining_data = await mining_resp.json()
                            if mining_data['code'] == 200:
                                last_mining_time = mining_data['data'].get('lastMiningTime', 0) / 1000
                                current_time = time.time()
                                next_mining_time = last_mining_time + 24 * 60 * 60
                                if current_time < next_mining_time:
                                    remaining_hours = (next_mining_time - current_time) / 3600
                                    console.print(f"[yellow]⏳ 账户 {address}: 24小时内已激活过，还需等待 {remaining_hours:.2f}小时[/]")
                                return True
                    
                    console.print(f"[bold green]✅ 账户 {address}: 合约调用成功[/]")
                    return True
                
                console.print(f"[bold red]🚫 账户 {address}: 合约调用失败，响应: {data}[/]")
                if attempt < retries - 1:
                    delay = 3 * (attempt + 1)
                    console.print(f"[yellow]⏳ 账户 {address}: {delay}秒后重试... ({retries-attempt-1}次)[/]")
                    await asyncio.sleep(delay)
                    continue
                return False
                
            except Exception as e:
                if attempt < retries - 1:
                    delay = 3 * (attempt + 1)
                    console.print(f"[yellow]⏳ 账户 {address}: {delay}秒后重试... ({retries-attempt-1}次)[/]")
                    await asyncio.sleep(delay)
                    continue
                return False
        
        return False

    async def activate_mining_onchain(self, address, private_key, proxy, retries=3):
        
        if address in self.activated_accounts and self.activated_accounts[address]:
           
            if await self.check_contract(None, address, {}, proxy):
                return "already_activated"
            else:
                console.print(f"[bold yellow]⚠️ 账户 {address}: 本地显示已激活但链上未确认，尝试重新激活[/]")
                self.activated_accounts[address] = False
                with open('activated_accounts.json', 'w') as f:
                    json.dump(self.activated_accounts, f, indent=4)

        
        w3 = Web3(Web3.HTTPProvider(
            self.config['api']['rpc_url'],
            request_kwargs={'proxies': {'http': proxy, 'https': proxy}} if proxy else {}
        ))
        contract_address = w3.to_checksum_address("0xB3eFE5105b835E5Dd9D206445Dbd66DF24b912AB")
        contract_abi = [
            {
                "inputs": [],
                "name": "active",
                "outputs": [],
                "stateMutability": "nonpayable",
                "type": "function"
            }
        ]

        try:
            contract = w3.eth.contract(address=contract_address, abi=contract_abi)
            nonce = w3.eth.get_transaction_count(address)

            
            try:
                gas_estimate = contract.functions.active().estimate_gas({'from': address})
                console.print(f"[bold cyan]ℹ️ 账户 {address}: Gas 估算值: {gas_estimate}[/]")
            except Exception as e:
                console.print(f"[bold yellow]⚠️ 账户 {address}: Gas 估算失败，使用默认值 200000[/]")
                gas_estimate = 200000

            
            chain_id = w3.eth.chain_id

            
            tx = contract.functions.active().build_transaction({
                'from': address,
                'nonce': nonce,
                'gas': gas_estimate,
                'gasPrice': w3.eth.gas_price,
                'chainId': chain_id
            })

            
            signed_tx = w3.eth.account.sign_transaction(tx, private_key=private_key)

            
            tx_hash = w3.eth.send_raw_transaction(signed_tx.rawTransaction)

            console.print(f"[bold green]✅ 账户 {address}: 链上激活交易已发送，Hash: {tx_hash.hex()}[/]")

            
            receipt = w3.eth.wait_for_transaction_receipt(tx_hash)
            if receipt['status'] == 1:
                console.print(f"[bold green]✅ 账户 {address}: 链上激活交易已确认[/]")
                self.activated_accounts[address] = True
                with open('activated_accounts.json', 'w') as f:
                    json.dump(self.activated_accounts, f, indent=4)
                return True
            else:
                console.print(f"[bold yellow]⚠️ 账户 {address}: 当前已激活节点[/]")
                return "already_activated"

        except ValueError as e:
            if "insufficient funds" in str(e):
                console.print(f"[bold red]🚫 账户 {address}: 余额不足[/]")
            else:
                console.print(f"[bold yellow]⚠️ 账户 {address}: 当前已激活节点[/]")
            return "already_activated"
        except Exception as e:
            console.print(f"[bold yellow]⚠️ 账户 {address}: 当前已激活节点[/]")
            return "already_activated"

    async def process_account(self, account_index):
        address = self.addresses[account_index]
        private_key = self.private_keys[account_index]
        proxy = self.proxies[account_index] if self.config['proxy_enabled'] else None
        
        headers = {
            "User-Agent": self.user_agents[account_index],
            "Content-Type": "application/json"
        }
        
        if proxy:
            console.print(f"[bold blue]🌐 账户 {address}: 代理 {proxy}[/]")
        
        async with aiohttp.ClientSession() as session:
            console.print(f"[bold cyan]🔄 账户 {address}: 开始登录...[/]")
            
            token = await self.login(session, address, private_key, headers, proxy)
            if not token:
                return
                
            console.print(f"[bold cyan]🔑 账户 {address}: 获取到 token: {token[:20]}...[/]")
            
            
            if not await self.get_mining_time(session, address, token, headers, proxy):
                return
            
            
            console.print(f"[bold cyan]⛓️ 账户 {address}: 正在链上激活挖矿...[/]")
            activation_result = await self.activate_mining_onchain(address, private_key, proxy)
            
            if activation_result == "already_activated":
                return
            
            if activation_result:
                console.print(f"[bold cyan]🚀 账户 {address}: 正在启动节点...[/]")
                await self.start_mining(session, address, token, headers, proxy)

    async def run(self):
        while True:
            tasks = []
            for i in range(0, len(self.addresses), self.config['concurrent_accounts']):
                batch = range(i, min(i + self.config['concurrent_accounts'], len(self.addresses)))
                tasks.extend([self.process_account(j) for j in batch])
                
                if tasks:
                    await asyncio.gather(*tasks)
                    tasks = []
            
            delay = random.uniform(
                self.config['check_interval']['min_hours'] * 3600,
                self.config['check_interval']['max_hours'] * 3600
            )
            
            console.print(f"[bold green]✅ 任务完成，{delay/3600:.2f}小时后重新检查...[/]")
            await asyncio.sleep(delay)

if __name__ == "__main__":
    miner = TakerMining()
    asyncio.run(miner.run())
