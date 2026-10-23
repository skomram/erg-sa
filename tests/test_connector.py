import json,os,time
from pathlib import Path
import jwt
import pytest
from cryptography.fernet import Fernet
from fastapi.testclient import TestClient
from app.core import build_delta,build_sellasist_payload,parse_images

ROOT=Path(__file__).resolve().parents[1]

@pytest.fixture
def test_client(tmp_path,monkeypatch):
    monkeypatch.setenv('DB_PATH',str(tmp_path/'test.sqlite3'))
    monkeypatch.setenv('ENCRYPTION_KEY',Fernet.generate_key().decode())
    monkeypatch.setenv('ADMIN_TOKEN','test-admin-key')
    monkeypatch.setenv('ERGONODE_ALLOWED_HOSTS','example.ergonode.local')
    monkeypatch.setenv('ENABLE_LIVE_WRITES','false')
    from app.main import app
    with TestClient(app) as client:
        yield client

def app_token(secret='test-shared-secret-at-least-32-characters',extra=None):
    now=int(time.time())
    return jwt.encode({'app_installation_id':'install-1','api_url':'https://example.ergonode.local/api/graphql/','iat':now,'exp':now+600,**(extra or {})},secret,algorithm='HS256')

def register(client):
    token=app_token()
    r=client.post('/handshake',headers={'X-APP-TOKEN':token},json={'shared_secret':'test-shared-secret-at-least-32-characters'})
    assert r.status_code==200,r.text
    return {'X-APP-TOKEN':token}

def test_manifest(test_client):
    obj=test_client.get('/manifest.json').json()
    assert obj['name']=='Sellasist Connector'
    assert 'synchronization' in obj['features']
    assert obj['write_access'] is True
    assert obj['icon'].startswith('data:image/webp;base64,')

def test_handshake_verifies_signature(test_client):
    r=test_client.post('/handshake',headers={'X-APP-TOKEN':app_token()},json={'shared_secret':'WRONG-secret-at-least-32-characters'})
    assert r.status_code==401
    assert test_client.get('/configuration',headers={'X-APP-TOKEN':app_token()}).status_code==401

def test_config_and_custom_dictionary(test_client):
    h=register(test_client)
    assert test_client.get('/configuration',headers=h).json()==[{}, {}, {}]
    r=test_client.post('/configuration',headers=h,json={'index':0,'configuration':{'base_url':'https://my.sellasist.pl/api/v1','api_key':'sample-key','api_key_header':'apiKey'}})
    assert r.status_code==200,r.text
    assert test_client.get('/configuration',headers=h).json()[0]['api_key']=='sample-key'
    d=test_client.get('/dictionary/attributes',headers=h).json()
    assert any(item['id']=='images' for item in d['dictionary'])

def test_parse_ergonode_gallery():
    event={'synchronization':{'events':[{'type':'product_value_changed','payload':{'attribute_code':'gallery','attribute_type':'GALLERY','attribute_scope':'global','value':[{'url':'https://cdn.example.com/1.jpg','path':'a.jpg'},{'url':'https://cdn.example.com/2.jpg','path':'b.jpg'}]}}]}}
    d,t=build_delta(event,[{'ergonode':'gallery','app':'images'}])
    assert t and d['images']==['https://cdn.example.com/1.jpg','https://cdn.example.com/2.jpg']
    p=build_sellasist_payload(d,t,{'replace_images':True,'send_empty_gallery':False,'image_payload_format':'objects_url'})
    assert p['images_replacement_flag'] is True
    assert p['images'][0]=={'url':'https://cdn.example.com/1.jpg'}

def test_removed_gallery_protected():
    delta,t=build_delta({'synchronization':{'events':[{'type':'product_value_removed','payload':{'attribute_code':'gallery','attribute_type':'GALLERY'}}]}},[{'ergonode':'gallery','app':'images'}])
    with pytest.raises(ValueError,match='Pusta galeria'):
        build_sellasist_payload(delta,t,{'replace_images':True,'send_empty_gallery':False})

def test_preview_and_links(test_client):
    h=register(test_client)
    for index,cfg in [
      (0,{'base_url':'https://my.sellasist.pl/api/v1','api_key':'key','api_key_header':'apiKey'}),
      (1,{'mapping':[{'ergonode':'gallery','app':'images'}],'preferred_language':'pl_PL'}),
      (2,{'write_mode':'preview','replace_images':True,'image_payload_format':'url_strings','send_empty_gallery':False})
    ]:
        r=test_client.post('/configuration',headers=h,json={'index':index,'configuration':cfg})
        assert r.status_code==200,r.text
    r=test_client.post('/admin/links',headers={'X-ADMIN-TOKEN':'test-admin-key'},json={'app_installation_id':'install-1','products':[{'sku':'SKU1','sellasist_id':123}]})
    assert r.status_code==200,r.text
    sync_h={'X-APP-TOKEN':app_token(extra={'synchronization_id':'sync-2026-1'})}
    payload={'name':'product_updated','resource_id':{'id':'SKU1','type':'sku'},'synchronization':{'resource_customs':None,'events':[{'type':'product_value_changed','payload':{'attribute_code':'gallery','attribute_type':'IMAGE','attribute_scope':'global','value':{'url':'https://cdn.example.com/a.jpg','path':'a.jpg'}}}]}}
    r=test_client.put('/consume/product_updated',headers=sync_h,json=payload)
    assert r.status_code==200,r.text
    assert r.json()['resource_customs']['sellasist_product_id']=='123'
    r=test_client.get('/admin/logs/install-1',headers={'X-ADMIN-TOKEN':'test-admin-key'})
    assert r.json()['entries'][0]['status']=='preview'

def test_rejects_unmapped_product(test_client):
    h=register(test_client)
    payload={'name':'product_updated','resource_id':{'id':'XX','type':'sku'},'synchronization':{'events':[{'type':'product_value_added','payload':{'attribute_code':'a','attribute_type':'TEXT','value':'b'}}]}}
    assert test_client.put('/consume/product_updated',headers=h,json=payload).status_code==200  # brak mapowania - bezpieczne pominięcie

def test_unsafe_urls():
    from app.sellasist import validate_url
    with pytest.raises(ValueError):validate_url('http://localhost/api/v1')
    assert validate_url('https://konto.sellasist.pl/api/v1')


def test_admin_is_protected(test_client):
    assert test_client.get('/admin/installations').status_code==401
    assert test_client.get('/admin/installations',headers={'X-ADMIN-TOKEN':'test-admin-key'}).json()=={'installations':[]}


def test_sellasist_http_client_mock():
    import asyncio,httpx
    from app.sellasist import SellasistClient
    observed=[]
    def handler(request):
        observed.append((request.method,str(request.url),request.headers.get('apiKey')))
        assert str(request.url)=='https://konto.sellasist.pl/api/v1/products/123'
        if request.method=='PUT':
            assert json.loads(request.content)['images_replacement_flag'] is True
        return httpx.Response(200,json={'id':123})
    async def run():
        client=SellasistClient({'base_url':'https://konto.sellasist.pl/api/v1','api_key':'secret','api_key_header':'apiKey'},transport=httpx.MockTransport(handler))
        try:
            assert (await client.get_product(123))['id']==123
            assert (await client.put_product(123,{'images':['https://cdn.example.com/a.jpg'],'images_replacement_flag':True}))['id']==123
        finally:
            await client.close()
    asyncio.run(run())
    assert len(observed)==2
    assert observed[0][2]=='secret'


def test_event_is_encrypted(test_client):
    h=register(test_client)
    payload={'name':'attribute_created','resource_id':{'id':'secret-attribute','type':'attribute_code'},'synchronization':{'events':[{'type':'attribute_created','payload':{'code':'secret-value-123','type':'TEXT','scope':'global','name':[]}}]}}
    response=test_client.put('/consume/attribute_created',headers=h,json=payload)
    assert response.status_code==200,response.text
    from app import storage
    raw=Path(os.environ['DB_PATH']).read_bytes()
    assert b'secret-value-123' not in raw
