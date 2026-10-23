"""HTTP microservice for Ergonode Apps (Apps2)."""
from __future__ import annotations
import os, logging
from pathlib import Path
from urllib.parse import urlparse
from contextlib import asynccontextmanager
import jwt
from fastapi import FastAPI, Request, Header, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from . import storage
from .core import SUPPORTED_EVENTS, build_delta, build_sellasist_payload
from .sellasist import SellasistClient, validate_url

log=logging.getLogger('sellasist_connector')
ROOT=Path(__file__).resolve().parents[1]
ALGS=['HS256']

@asynccontextmanager
async def lifespan(app:FastAPI):
    storage.fernet()  # brak cichego działania bez szyfrowania
    storage.init()
    yield

app=FastAPI(title='Sellasist Connector for Ergonode',docs_url=None,redoc_url=None,lifespan=lifespan)

class Handshake(BaseModel):
    shared_secret:str


def validated_ergonode_url(url:str):
    u=urlparse(url)
    if u.scheme!='https' or not u.hostname or u.username or u.password or u.query or u.fragment or u.port not in (None,443):
        raise ValueError('api_url musi mieć publiczny HTTPS')
    allowed=os.getenv('ERGONODE_ALLOWED_HOSTS','').strip()
    if allowed and u.hostname not in set(x.strip() for x in allowed.split(',')):
        raise ValueError('api_url spoza listy zaufanych hostów')
    return url


def decode_unsafe(token):
    try:
        return jwt.decode(token,options={'verify_signature':False,'verify_exp':False})
    except jwt.PyJWTError:
        raise HTTPException(401,'Nieprawidłowy JWT')


def verify_token(token):
    if not token:
        raise HTTPException(401,'Brak X-APP-TOKEN')
    decoded=decode_unsafe(token)
    identifier=decoded.get('app_installation_id')
    if not isinstance(identifier,str) or not identifier:
        raise HTTPException(401,'Brak app_installation_id')
    install=storage.read_install(identifier)
    if not install:
        raise HTTPException(401,'Instalacja niezarejestrowana')
    try:
        claims=jwt.decode(token,install['secret'],algorithms=ALGS,options={'require':['iat','exp','app_installation_id']},leeway=30)
    except jwt.PyJWTError:
        raise HTTPException(401,'JWT podpisany nieprawidłowo lub wygasły')
    return identifier,claims,install


@app.get('/healthz')
def health():
    return {'status':'ok'}

@app.get('/manifest.json')
def manifest():
    return JSONResponse(__import__('json').loads((ROOT/'manifest.json').read_text(encoding='utf-8')))

@app.post('/handshake')
def handshake(body:Handshake,x_app_token:str|None=Header(default=None)):
    if not x_app_token:
        raise HTTPException(401,'Brak X-APP-TOKEN')
    try:
        claims=jwt.decode(x_app_token,body.shared_secret,algorithms=ALGS,options={'require':['iat','exp','app_installation_id','api_url']},leeway=30)
        installation=claims['app_installation_id']
        api_url=validated_ergonode_url(claims['api_url'])
        storage.register(installation,api_url,body.shared_secret)
    except (jwt.PyJWTError,ValueError,KeyError) as e:
        raise HTTPException(401,'Nieprawidłowe dane handshake') from e
    return {'status':'ok'}

@app.get('/configuration')
def get_configuration(x_app_token:str|None=Header(default=None)):
    ident,_,_=verify_token(x_app_token)
    return storage.get_steps(ident)

@app.post('/configuration')
def update_configuration(body:dict,x_app_token:str|None=Header(default=None)):
    ident,_,_=verify_token(x_app_token)
    idx=body.get('index')
    cfg=body.get('configuration')
    if not isinstance(idx,int) or idx not in (0,1,2) or not isinstance(cfg,dict):
        raise HTTPException(422,'Nieprawidłowy indeks lub dane konfiguracji')
    try:
        if idx==0:
            validate_url(cfg.get('base_url',''))
            if not cfg.get('api_key') or cfg.get('api_key_header') not in ('apiKey','X-API-Key','Authorization'):
                raise ValueError('Niepoprawny klucz lub nagłówek')
        if idx==1:
            if not isinstance(cfg.get('mapping'),list) or not isinstance(cfg.get('preferred_language'),str):
                raise ValueError('Brak mapowania lub języka')
            if any(m.get('app') not in ('name','description','ean','images') for m in cfg['mapping']):
                raise ValueError('Nieznane pole docelowe')
        if idx==2:
            if cfg.get('write_mode') not in ('preview','live'):
                raise ValueError('Nieznany tryb zapisu')
            if cfg.get('image_payload_format') not in ('url_strings','objects_url'):
                raise ValueError('Nieznany format zdjęć')
            if not all(isinstance(cfg.get(x),bool) for x in ('replace_images','send_empty_gallery')):
                raise ValueError('Brak konfiguracji flag zdjęć')
    except (ValueError,AttributeError) as ex:
        raise HTTPException(422,{'title':'Form validation errors.','detail':str(ex),'violations':[]}) from ex
    storage.put_step(ident,idx,cfg)
    return {'status':'saved'}

@app.get('/dictionary/attributes')
def dictionary_attributes(x_app_token:str|None=Header(default=None)):
    verify_token(x_app_token)
    return {'dictionary':[
        {'id':'name','label':'Nazwa produktu','type':'TEXT|TEXT_AREA'},
        {'id':'description','label':'Opis produktu','type':'TEXT|TEXT_AREA'},
        {'id':'ean','label':'Kod EAN','type':'TEXT'},
        {'id':'images','label':'Galeria / zdjęcia','type':'IMAGE|GALLERY'},
    ]}

@app.put('/consume/{event_name}')
async def sync_event(event_name:str,request:Request,x_app_token:str|None=Header(default=None)):
    ident,claims,_=verify_token(x_app_token)
    if event_name not in SUPPORTED_EVENTS:
        raise HTTPException(404,'Nieobsługiwane zdarzenie')
    try:
        body=await request.json()
    except Exception:
        raise HTTPException(400,'Niepoprawny JSON')
    if body.get('name') != event_name:
        raise HTTPException(422,'Nazwa zdarzenia w URL i payload niezgodna')
    sync_id=claims.get('synchronization_id','non-sync')
    if event_name=='app_uninstalled':
        storage.uninstall(ident)
        return {'status':'uninstalled'}
    if event_name in ('app_installed','synchronization_started','synchronization_ended'):
        storage.log(ident,str(sync_id),event_name,'',{},'received')
        return {'status':'ok'}
    resource=body.get('resource_id') or {}
    sku=str(resource.get('id',''))
    if not sku:
        raise HTTPException(422,'Brak resource_id.id')
    if storage.logged(ident,str(sync_id),event_name,sku)=='sent':
        customs=(body.get('synchronization') or {}).get('resource_customs') or {}
        sid=customs.get('sellasist_product_id') or storage.get_link(ident,sku)
        return {'resource_customs':{'sellasist_product_id':str(sid)}} if sid else {'status':'duplicate'}
    if not event_name.startswith('product_'):
        storage.log(ident,str(sync_id),event_name,sku,body.get('synchronization',{}).get('events',[]),'observed')
        return {'status':'observed'}
    if event_name=='product_deleted':
        storage.log(ident,str(sync_id),event_name,sku,{},'skipped-delete')
        return {'status':'skipped-delete'}
    cfg=storage.get_steps(ident)
    mapping_cfg=cfg[1]
    options=cfg[2] or {'write_mode':'preview','replace_images':False,'send_empty_gallery':False,'image_payload_format':'url_strings'}
    try:
        delta,images_changed=build_delta(body,mapping_cfg.get('mapping',[]),mapping_cfg.get('preferred_language','pl_PL'))
        payload=build_sellasist_payload(delta,images_changed,options)
    except ValueError as e:
        raise HTTPException(422,str(e)) from e
    old_customs=(body.get('synchronization') or {}).get('resource_customs') or {}
    product_id=old_customs.get('sellasist_product_id') or storage.get_link(ident,sku)
    if not payload:
        storage.log(ident,str(sync_id),event_name,sku,{},'no-changes-mapped')
        return {'resource_customs':old_customs}
    if not product_id:
        storage.log(ident,str(sync_id),event_name,sku,payload,'missing-product-link')
        # Odrzucamy, nie potwierdzamy synchronizacji bez docelowego ID.
        raise HTTPException(422,f'Brak powiązania SKU={sku} z Sellasist ID. Użyj API administracyjnego /admin/links')
    if options.get('write_mode','preview')!='live':
        storage.log(ident,str(sync_id),event_name,sku,payload,'preview')
        return {'resource_customs':{'sellasist_product_id':str(product_id)}}
    connection=cfg[0]
    if not connection:
        raise HTTPException(422,'Brak konfiguracji połączenia')
    # W produkcji wymagamy operatorowego potwierdzenia, że payload sprawdzono z aktualnym OpenAPI Sellasist.
    if os.getenv('ENABLE_LIVE_WRITES','false').lower()!='true':
        raise HTTPException(403,'Zapis produkcyjny nieaktywny: ENABLE_LIVE_WRITES=true wymagane po testach kontraktowych')
    client=SellasistClient(connection)
    try:
        await client.put_product(str(product_id),payload)
    except Exception as e:
        log.exception('Błąd Sellasist SKU=%s',sku)
        storage.log(ident,str(sync_id),event_name,sku,payload,'api-error')
        raise HTTPException(502,'Sellasist API odrzuciło żądanie') from e
    finally:
        await client.close()
    storage.log(ident,str(sync_id),event_name,sku,payload,'sent')
    return {'resource_customs':{'sellasist_product_id':str(product_id)}}

# Events on installation/uninstallation use POST and no sync_id.
@app.post('/consume/app_installed')
@app.post('/consume/app_uninstalled')
async def app_lifecycle(request:Request,x_app_token:str|None=Header(default=None)):
    ident,_,_=verify_token(x_app_token)
    body=await request.json()
    if body.get('name')=='app_uninstalled':
        storage.uninstall(ident)
    return {'status':'ok'}

# Endpoint do masowego dostarczenia identyfikatorów produktów; samej synchronizacji nie wykonuje.
def admin_auth(key):
    expected=os.getenv('ADMIN_TOKEN','')
    import hmac
    if not expected or not key or not hmac.compare_digest(expected,key):
        raise HTTPException(401,'Brak dostępu')

@app.post('/admin/links')
def import_links(body:dict,x_admin_token:str|None=Header(default=None)):
    admin_auth(x_admin_token)
    ident=body.get('app_installation_id')
    items=body.get('products')
    if not storage.read_install(str(ident)) or not isinstance(items,list) or len(items)>10_000:
        raise HTTPException(422,'Nieznana instalacja lub niepoprawna lista')
    for item in items:
        if not isinstance(item,dict) or not item.get('sku') or not item.get('sellasist_id'):
            raise HTTPException(422,'Każdy element musi zawierać sku i sellasist_id')
    for item in items:
        storage.put_link(ident,str(item['sku']),str(item['sellasist_id']))
    return {'imported':len(items)}

@app.get('/admin/logs/{app_installation_id}')
def logs(app_installation_id:str,x_admin_token:str|None=Header(default=None)):
    admin_auth(x_admin_token)
    return {'entries':storage.last_logs(app_installation_id)}

@app.post('/admin/import/sellasist-textareas')
async def import_sellasist_textareas(body:dict,x_admin_token:str|None=Header(default=None)):
    """Sellasist -> Ergonode przez zweryfikowaną mutację GraphQL typu TEXT_AREA.

    Wymaga jawnych ścieżek do wartości z odpowiedzi GET /products/{id}.
    Nie zgaduje schematu Sellasist ani nie tworzy niejawnych mapowań.
    """
    import json,time
    import httpx
    admin_auth(x_admin_token)
    ident=body.get('app_installation_id')
    inst=storage.read_install(str(ident))
    if not inst:
        raise HTTPException(404,'Brak instalacji')
    sku=body.get('sku','')
    product_id=body.get('sellasist_product_id')
    mappings=body.get('fields',[])
    if not sku or not product_id or not isinstance(mappings,list) or not 1<=len(mappings)<=10:
        raise HTTPException(422,'Wymagane: sku, sellasist_product_id, fields[1..10]')
    for item in mappings:
        if not isinstance(item,dict) or not all(isinstance(item.get(k),str) and item[k] for k in ('sellasist_path','ergonode_attribute_code','language')):
            raise HTTPException(422,'Brak sellasist_path, ergonode_attribute_code lub language')
    connection=storage.get_steps(ident)[0]
    if not connection:
        raise HTTPException(422,'Najpierw skonfiguruj połączenie Sellasist w Ergonode Apps')
    client=SellasistClient(connection)
    try:
        product=await client.get_product(str(product_id))
    finally:
        await client.close()
    def extract_path(obj,path):
        result=obj
        for chunk in path.split('.'):
            if not isinstance(result,dict) or chunk not in result:
                raise HTTPException(422,f'Brak wskazanego pola w odpowiedzi Sellasist: {path}')
            result=result[chunk]
        if not isinstance(result,str):
            raise HTTPException(422,f'Pole {path} nie zawiera tekstu')
        return result
    statements=[]
    for i,item in enumerate(mappings):
        value=extract_path(product,item['sellasist_path'])
        params=' '.join([
            f'sku: {json.dumps(sku)}',
            f'attributeCode: {json.dumps(item["ergonode_attribute_code"])}',
            f'translations: [{{value: {json.dumps(value)}, language: {json.dumps(item["language"])}}}]'
        ])
        statements.append(f'update{i}: productAddAttributeValueTranslationsTextarea(input: {{{params}}}) {{ __typename }}')
    query='mutation { '+' '.join(statements)+' }'
    if os.getenv('ENABLE_ERGONODE_IMPORTS','false').lower()!='true':
        return {'status':'preview','query':query,'source_product_id':str(product_id)}
    now=int(time.time())
    token=jwt.encode({'app_installation_id':ident,'nbf':now-5,'iat':now,'exp':now+120},inst['secret'],algorithm='HS256')
    try:
        async with httpx.AsyncClient(timeout=30,follow_redirects=False) as h:
            r=await h.post(inst['api_url'],json={'query':query},headers={'X-APP-TOKEN':token,'Accept':'application/json'})
            r.raise_for_status()
            response=r.json()
    except (httpx.HTTPError,ValueError) as e:
        raise HTTPException(502,'Błąd połączenia z API Ergonode') from e
    if response.get('errors'):
        raise HTTPException(422,{'graphql_errors':response['errors']})
    return {'status':'imported','result':response.get('data')}


@app.get('/admin/installations')
def installed_apps(x_admin_token:str|None=Header(default=None)):
    admin_auth(x_admin_token)
    return {'installations':storage.installations()}

@app.get('/admin/preview/{app_installation_id}/{sku}')
def show_preview(app_installation_id:str,sku:str,x_admin_token:str|None=Header(default=None)):
    admin_auth(x_admin_token)
    entry=storage.preview(app_installation_id,sku)
    if not entry:
        raise HTTPException(404,'Brak historii dla SKU')
    return entry
