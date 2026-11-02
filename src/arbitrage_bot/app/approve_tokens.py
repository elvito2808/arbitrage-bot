#!/usr/bin/env python3
"""
اسکریپت مستقل برای اپرووال توکن‌های WZIL, zUSDC, zUSDT به روتر PlunderSwap
مقادیر اپرووال:
- WZIL: 1,000,000 واحد (با 18 رقم اعشار)
- zUSDC: 10,000 واحد (با 6 رقم اعشار)
- zUSDT: 10,000 واحد (با 6 رقم اعشار)
"""

import asyncio
import sys
import os
import json
from web3 import Web3
from dotenv import load_dotenv

# ============= تنظیمات =============
SMART_ROUTER_ADDRESS = "0xe30161F32A019d876F082d9FF13ed451a03A2086"
WZIL_ADDRESS = "0x94e18aE7dd5eE57B55f30c4B63E2760c09EFb192"
ZUSDC_ADDRESS = "0xe59f97Fac09ee00AEEF320485ee45D5CcfbBC1E9"
ZUSDT_ADDRESS = "0x2274005778063684fbB1BfA96a2b725dc37d75f9"

# مقادیر اپرووال (با احتساب decimals)
APPROVE_WZIL = int(1_000_000 * 10**18)      # 1,000,000 WZIL
APPROVE_ZUSDC = int(10_000 * 10**6)         # 10,000 zUSDC
APPROVE_ZUSDT = int(10_000 * 10**6)         # 10,000 zUSDT

RPC_NODES = [
    "https://api.zilliqa.com",
    "https://api.zq2-mainnet.zilliqa.com",
    "https://ssn.zilpay.io"
]

# ABI استاندارد ERC20 (برای approve, allowance, balanceOf)
TOKEN_ABI = [
    {
        "constant": True,
        "inputs": [{"name": "_owner", "type": "address"}],
        "name": "balanceOf",
        "outputs": [{"name": "balance", "type": "uint256"}],
        "type": "function"
    },
    {
        "constant": False,
        "inputs": [
            {"name": "_spender", "type": "address"},
            {"name": "_value", "type": "uint256"}
        ],
        "name": "approve",
        "outputs": [{"name": "", "type": "bool"}],
        "type": "function"
    },
    {
        "constant": True,
        "inputs": [
            {"name": "_owner", "type": "address"},
            {"name": "_spender", "type": "address"}
        ],
        "name": "allowance",
        "outputs": [{"name": "", "type": "uint256"}],
        "type": "function"
    }
]

# ============= توابع کمکی =============
def load_environment():
    load_dotenv()
    private_key = os.getenv("METAMASK_PRIVATE_KEY")
    if not private_key:
        raise Exception("METAMASK_PRIVATE_KEY not found in .env file")
    return private_key

async def connect_to_zilliqa():
    for node in RPC_NODES:
        try:
            w3 = Web3(Web3.HTTPProvider(node, request_kwargs={"timeout": 30}))
            if w3.is_connected():
                print(f"✅ Connected to {node}")
                return w3
        except Exception as e:
            print(f"Failed to connect to {node}: {e}")
    raise Exception("Could not connect to any Zilliqa node")

async def approve_token(w3, token_address, spender, amount, token_name, decimals, private_key, wallet):
    token_contract = w3.eth.contract(address=token_address, abi=TOKEN_ABI)
    # بررسی allowance فعلی
    allowance = await asyncio.to_thread(token_contract.functions.allowance(wallet, spender).call)
    required = amount
    if allowance >= required:
        print(f"✅ {token_name} already approved: {allowance / 10**decimals:.2f} >= {required / 10**decimals:.2f}")
        return True
    print(f"⚠️  {token_name} allowance is {allowance / 10**decimals:.2f}, need {required / 10**decimals:.2f}. Sending approval...")
    nonce = await asyncio.to_thread(w3.eth.get_transaction_count, wallet, 'pending')
    gas_price = w3.eth.gas_price
    txn = token_contract.functions.approve(spender, required).build_transaction({
        "from": wallet,
        "gas": 100000,
        "gasPrice": gas_price,
        "nonce": nonce,
        "chainId": w3.eth.chain_id
    })
    signed = w3.eth.account.sign_transaction(txn, private_key)
    tx_hash = w3.eth.send_raw_transaction(signed.raw_transaction)
    print(f"🟡 Transaction sent: {tx_hash.hex()}")
    receipt = w3.eth.wait_for_transaction_receipt(tx_hash, timeout=60)
    if receipt["status"] == 1:
        print(f"✅ Approval for {token_name} successful!")
        return True
    else:
        print(f"❌ Approval for {token_name} failed!")
        return False

async def main():
    try:
        private_key = load_environment()
        w3 = await connect_to_zilliqa()
        # تبدیل آدرس‌ها به Checksum
        router = w3.to_checksum_address(SMART_ROUTER_ADDRESS)
        wzil = w3.to_checksum_address(WZIL_ADDRESS)
        zusdc = w3.to_checksum_address(ZUSDC_ADDRESS)
        zusdt = w3.to_checksum_address(ZUSDT_ADDRESS)
        account = w3.eth.account.from_key(private_key)
        wallet = w3.to_checksum_address(account.address)
        print(f"Wallet: {wallet}")
        print(f"Router: {router}")
        print("\n--- Approving WZIL ---")
        await approve_token(w3, wzil, router, APPROVE_WZIL, "WZIL", 18, private_key, wallet)
        print("\n--- Approving zUSDC ---")
        await approve_token(w3, zusdc, router, APPROVE_ZUSDC, "zUSDC", 6, private_key, wallet)
        print("\n--- Approving zUSDT ---")
        await approve_token(w3, zusdt, router, APPROVE_ZUSDT, "zUSDT", 6, private_key, wallet)
        print("\n✅ All approvals processed.")
    except Exception as e:
        print(f"❌ Error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main())