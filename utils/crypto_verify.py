"""
Verifies a user-submitted transaction hash against a public block explorer,
free tier, no paid node required:

  BTC / LTC   -> Blockchair public API (no key)
  SOL         -> Solana public JSON-RPC (no key)
  USDT_TRC20  -> Tronscan public API (no key)
  ETH         -> Etherscan API (free key from etherscan.io/apis)

This is the "submit your tx hash, bot checks it landed" pattern - it does NOT
generate a unique deposit address per user (that needs an HD wallet / node),
so cryptopay uses one shared address per coin and matches by amount + memo.
"""

import aiohttp

import config

TIMEOUT = aiohttp.ClientTimeout(total=15)


async def _get_json(url: str, **kwargs):
    async with aiohttp.ClientSession(timeout=TIMEOUT) as session:
        async with session.get(url, **kwargs) as resp:
            return resp.status, await resp.json()


async def _post_json(url: str, json_body: dict):
    async with aiohttp.ClientSession(timeout=TIMEOUT) as session:
        async with session.post(url, json=json_body) as resp:
            return resp.status, await resp.json()


async def verify_btc(tx_hash: str) -> dict:
    status, data = await _get_json(f"https://api.blockchair.com/bitcoin/dashboards/transaction/{tx_hash}")
    return _parse_blockchair(status, data, tx_hash, decimals=8)


async def verify_ltc(tx_hash: str) -> dict:
    status, data = await _get_json(f"https://api.blockchair.com/litecoin/dashboards/transaction/{tx_hash}")
    return _parse_blockchair(status, data, tx_hash, decimals=8)


def _parse_blockchair(status: int, data: dict, tx_hash: str, decimals: int) -> dict:
    if status != 200 or not data.get("data", {}).get(tx_hash):
        return {"success": False, "error": "Transaction not found"}
    outputs = data["data"][tx_hash].get("outputs", [])
    # report the largest output as the likely payment (change outputs are usually smaller)
    if not outputs:
        return {"success": False, "error": "No outputs on transaction"}
    best = max(outputs, key=lambda o: o.get("value", 0))
    return {
        "success": True,
        "to_address": best.get("recipient"),
        "amount": best.get("value", 0) / (10 ** decimals),
    }


async def verify_sol(tx_hash: str) -> dict:
    body = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "getTransaction",
        "params": [tx_hash, {"encoding": "jsonParsed", "maxSupportedTransactionVersion": 0}],
    }
    status, data = await _post_json("https://api.mainnet-beta.solana.com", body)
    result = data.get("result") if status == 200 else None
    if not result:
        return {"success": False, "error": "Transaction not found"}
    try:
        meta = result["meta"]
        keys = result["transaction"]["message"]["accountKeys"]
        pre, post = meta["preBalances"], meta["postBalances"]
        # find the account whose balance increased the most (the recipient)
        deltas = [post[i] - pre[i] for i in range(len(pre))]
        idx = max(range(len(deltas)), key=lambda i: deltas[i])
        to_address = keys[idx]["pubkey"] if isinstance(keys[idx], dict) else keys[idx]
        return {"success": True, "to_address": to_address, "amount": deltas[idx] / 1e9}
    except (KeyError, IndexError, TypeError):
        return {"success": False, "error": "Could not parse transaction"}


async def verify_usdt_trc20(tx_hash: str) -> dict:
    status, data = await _get_json(f"https://apilist.tronscanapi.com/api/transaction-info?hash={tx_hash}")
    if status != 200 or not data:
        return {"success": False, "error": "Transaction not found"}
    transfers = data.get("tokenTransferInfo") or data.get("trc20TransferInfo") or []
    if isinstance(transfers, dict):
        transfers = [transfers]
    for t in transfers:
        if t.get("symbol", "").upper() == "USDT":
            decimals = int(t.get("decimals", 6))
            return {
                "success": True,
                "to_address": t.get("to_address"),
                "amount": int(t.get("amount_str", 0)) / (10 ** decimals),
            }
    return {"success": False, "error": "No USDT transfer found in that transaction"}


async def verify_eth(tx_hash: str) -> dict:
    if not config.ETHERSCAN_API_KEY:
        return {"success": False, "error": "ETHERSCAN_API_KEY not configured"}
    url = (
        "https://api.etherscan.io/api?module=proxy&action=eth_getTransactionByHash"
        f"&txhash={tx_hash}&apikey={config.ETHERSCAN_API_KEY}"
    )
    status, data = await _get_json(url)
    result = data.get("result") if status == 200 else None
    if not result or not result.get("to"):
        return {"success": False, "error": "Transaction not found"}
    return {
        "success": True,
        "to_address": result["to"],
        "amount": int(result.get("value", "0x0"), 16) / 1e18,
    }


VERIFIERS = {
    "BTC": verify_btc,
    "LTC": verify_ltc,
    "SOL": verify_sol,
    "USDT_TRC20": verify_usdt_trc20,
    "ETH": verify_eth,
}


async def verify_transaction(coin: str, tx_hash: str) -> dict:
    coin = coin.upper()
    if coin not in VERIFIERS:
        return {"success": False, "error": f"Unsupported coin: {coin}"}
    try:
        return await VERIFIERS[coin](tx_hash)
    except Exception as e:
        return {"success": False, "error": str(e)}
