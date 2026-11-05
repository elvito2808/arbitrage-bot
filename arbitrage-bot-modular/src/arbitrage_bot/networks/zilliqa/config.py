"""Zilliqa-specific RPC and token configuration from the original project."""

NETWORK_ID = "zilliqa"
RPC_NODES = ["https://public.moonlet.cloud/zilliqa"]

WZIL_ADDRESS = "0x94e18aE7dd5eE57B55f30c4B63E2760c09EFb192"
ZUSDC_ADDRESS = "0xe59f97Fac09ee00AEEF320485ee45D5CcfbBC1E9"
ZUSDT_ADDRESS = "0x2274005778063684fbB1BfA96a2b725dc37d75f9"
TOKEN_DECIMALS = {"WZIL": 18, "ZUSDC": 6, "ZUSDT": 6}

TOKEN_ABI = [
    {
        "inputs": [
            {"internalType": "address", "name": "owner", "type": "address"},
            {"internalType": "address", "name": "spender", "type": "address"},
        ],
        "name": "allowance",
        "outputs": [{"internalType": "uint256", "name": "", "type": "uint256"}],
        "stateMutability": "view",
        "type": "function",
    },
    {
        "inputs": [{"internalType": "address", "name": "account", "type": "address"}],
        "name": "balanceOf",
        "outputs": [{"internalType": "uint256", "name": "", "type": "uint256"}],
        "stateMutability": "view",
        "type": "function",
    },
    {
        "inputs": [
            {"internalType": "address", "name": "spender", "type": "address"},
            {"internalType": "uint256", "name": "value", "type": "uint256"},
        ],
        "name": "approve",
        "outputs": [{"internalType": "bool", "name": "", "type": "bool"}],
        "stateMutability": "nonpayable",
        "type": "function",
    },
]
