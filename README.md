# Taker Mining Bot

一个用于 Taker 挖矿的自动化工具。

## 功能特点

- 支持多账户管理
- 代理支持
- 随机ua
- 重试机制

## 安装

1. 克隆仓库

bash
git clone https://github.com/your-username/taker-mining-bot.git
cd taker-mining-bot

2. 创建虚拟环境

bash
python -m venv venv
source venv/bin/activate # Linux/Mac
venv\Scripts\activate # Windows

3. 安装依赖

bash
pip install -r requirements.txt

## 配置

1. 创建以下文件：
- `wallet.txt`: 每行一个钱包地址
- `accounts.txt`: 每行一个私钥
- `proxy.txt`: 每行一个代理地址（格式：http://ip:port）
- `ua.txt`: 每行一个 User-Agent

- `config.json`: 对应的是执行间隔和初始并发数,验证码

## 使用

运行程序：

bash
python main.py

## 注意事项

- 确保钱包中有足够的 gas 费用（等待首次的gas）
- 确保在执行前进行绑定推特