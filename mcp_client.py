import asyncio
from fastmcp import Client
from fastmcp.client.transports import StreamableHttpTransport
from fastmcp.client.auth import OAuth

token = ''

transport = StreamableHttpTransport(
        url="http://0.0.0.0:8000/mcp",
        headers={"Authorization": f"Bearer {token}"}
    )

async def main():
    async with Client(
        transport=transport
    ) as client:
        tools = await client.list_tools()
        print([t.name for t in tools])


if __name__ == "__main__":
    asyncio.run(main())