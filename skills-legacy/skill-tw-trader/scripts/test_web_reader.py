import asyncio
from web_reader import read_url

async def main():
    url = "https://example.com"
    print(f"Testing web-reader with URL: {url}...")
    result = await read_url(url)
    
    if result.success:
        print("✅ SUCCESS!")
        print(f"Title: {result.title}")
        print(f"Text Content (first 100 chars): {result.text[:100]}...")
    else:
        print("❌ FAILED!")
        print(f"Error: {result.error}")

if __name__ == "__main__":
    asyncio.run(main())
