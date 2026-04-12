import asyncio

from camoufox.async_api import AsyncCamoufox


async def main() -> None:
    url = "https://news.google.com/read/CBMivgFBVV95cUxPSmFwRzdvNDJwdXFsMktMYzZEU1ZOcDhWVldacUQ3a3VlQkY4NEpIZ21qeE9CaFk0aEFQaFFwVUxId2xuclZQemJrczlyQU4xVGlBWHc2UndaODBwaFBJRWoyOUlJZnNzWTd3dUZERkgwbVhfSWFNUlRsQkhxUnZRdjJtbG5vdmE5ckpIVnlYYS0tRlZBazF4TlJpSzRod0Q4bEZqT2liT0lVbG1Jd19zaDV6cGcyb2ZmQjNwcFRB0gHDAUFVX3lxTE56a0JvdEJLTmx5c291OHZPWWU1WnVDSU8zbXN4azZNZzFoTnkwLURNRnA2ZGhqdkdSX3ZmV05DdVJDRldHVW05bXlsYmR1Mk5KTHNtUjZZNGpkSEt0Q2hmR0dBSXdfUkgyb0l2ZWtTV1VQR0tLVmN4VGlhcE1TWEV2T1c2cExCc01rX1BGZ25KSVAyazliOWl1R2o0Y2JxSEhXUHZmMVFZRGU1UHZER09rMUlFaWlmWVVRTUJEMzBMLThzQQ?hl=en-CA&gl=CA&ceid=CA%3Aen"

    async with AsyncCamoufox(headless="virtual") as browser:
        page = await browser.new_page()
        response = await page.goto(url, wait_until="domcontentloaded", timeout=30000)
        print(f"Response URL: {response.url if response else 'N/A'}")
        print(f"Page URL:     {page.url}")
        await page.close()


if __name__ == "__main__":
    asyncio.run(main())
