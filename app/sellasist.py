"""Minimalny klient udokumentowanych zasobów REST Sellasist.

Brak wywołań niepotwierdzonych endpointów. Kształt payloadów zapisu podlega walidacji kontraktowej na środowisku testowym.
"""
from urllib.parse import urlparse
import httpx

def validate_url(base_url):
    parsed=urlparse(base_url)
    if parsed.scheme!='https' or not parsed.hostname or parsed.username or parsed.password or parsed.query or parsed.fragment:
        raise ValueError('Sellasist API musi mieć poprawny adres https:// bez loginu i parametrów')
    if not parsed.path.rstrip('/').endswith('/api/v1'):
        raise ValueError('Podaj pełną ścieżkę Sellasist /api/v1')
    if parsed.port not in (None,443):
        raise ValueError('Niedozwolony port API')
    return base_url.rstrip('/')

class SellasistClient:
    def __init__(self,config,transport=None):
        self.base=validate_url(config['base_url'])
        header=config.get('api_key_header','apiKey')
        if header not in ('apiKey','X-API-Key','Authorization'):
            raise ValueError('Nagłówek autoryzacji spoza dozwolonej listy')
        token=config['api_key']
        self.client=httpx.AsyncClient(base_url=self.base+'/',headers={header:token,'Accept':'application/json'},timeout=30,follow_redirects=False,transport=transport)

    async def request(self,method,path,**kwargs):
        resp=await self.client.request(method,path.lstrip('/'),**kwargs)
        resp.raise_for_status()
        if not resp.content:
            return {}
        return resp.json()

    async def get_product(self,product_id):
        return await self.request('GET',f'products/{product_id}')

    async def put_product(self,product_id,payload):
        return await self.request('PUT',f'products/{product_id}',json=payload)

    async def get_images(self,product_id):
        return await self.request('GET',f'images/{product_id}')

    async def close(self):
        await self.client.aclose()
