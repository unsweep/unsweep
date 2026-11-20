import asyncio, os, sys
from cdp import CdpClient
async def main():
    async with CdpClient(api_key_id=os.environ['CDP_API_KEY_ID'], api_key_secret=os.environ['CDP_API_KEY_SECRET']) as cdp:
        tx = await cdp.evm.request_faucet(address=sys.argv[1], network='base-sepolia', token='eth')
        print('faucet_tx', tx)
asyncio.run(main())
