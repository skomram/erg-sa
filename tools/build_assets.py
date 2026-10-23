import base64, io, json
from pathlib import Path
from PIL import Image, ImageDraw
root = Path(__file__).resolve().parents[1]
# Znak inspirowany kolorystyką i geometrycznym symbolem marki, bez podszywania się pod oficjalny plik identyfikacji.
S=128
im=Image.new('RGBA',(S,S),(255,255,255,255))
d=ImageDraw.Draw(im)
d.polygon([(15,15),(64,15),(111,42),(64,68)],fill='#ff8c2e')
d.polygon([(15,15),(64,68),(15,98)],fill='#ffc335')
d.polygon([(15,98),(64,68),(111,97),(64,119)],fill='#ffae32')
d.polygon([(15,98),(64,119),(15,119)],fill='#f2d447')
d.polygon([(64,15),(111,42),(64,68)],fill='#ff9227')
b=io.BytesIO();im.save(b,format='WEBP',quality=85,method=6)
raw=b.getvalue()
assert len(raw)<7_000
(root/'assets'/'brand-inspired-icon.webp').write_bytes(raw)
icon='data:image/webp;base64,'+base64.b64encode(raw).decode()
manifest={
 'name':'Sellasist Connector',
 'description':'Dwukierunkowy most danych Ergonode i Sellasist: synchronizacja produktów, mapowanie pól i galerii, z kontrolą zmian i trybem podglądu.',
 'version':'0.1.0', 'compatible':'0.1.0',
 'features':['synchronization','synchronization_full','synchronization_scheduler'],
 'events':['app_installed','app_uninstalled','attribute_created','attribute_updated','attribute_deleted','category_created','category_updated','category_deleted','product_created','product_updated','product_deleted','synchronization_started','synchronization_ended'],
 'write_access':True,
 'configuration_schema':[
  {'title':'Połączenie Sellasist','type':'object','properties':{
   'base_url':{'type':'string','title':'Adres Sellasist API, np. https://konto.sellasist.pl/api/v1','propertyOrder':1},
   'api_key':{'type':'string','title':'Klucz API Sellasist','widget':'password','propertyOrder':2},
   'api_key_header':{'type':'string','title':'Nagłówek klucza API (zgodny z kontem)','enum':['apiKey','X-API-Key','Authorization'], 'propertyOrder':3}
   },'required':['base_url','api_key','api_key_header']},
  {'title':'Mapowanie danych produktu','type':'object','properties':{
   'mapping':{'type':'array','title':'Powiązania atrybutów','items':{'title':'Wiersz mapowania','type':'object','properties':{'ergonode':{'type':'string','title':'Ergonode','propertyOrder':1},'app':{'type':'string','title':'Sellasist','propertyOrder':2}},'required':['ergonode','app']},'widget':{'type':'mapper','options':{'ergonodeDictionary':'ergonode:attributes','appDictionary':'app:attributes'}},'propertyOrder':1},
   'preferred_language':{'type':'string','title':'Język atrybutów, np. pl_PL','propertyOrder':2}
  },'required':['mapping','preferred_language']},
  {'title':'Sterowanie synchronizacją','type':'object','properties':{
   'write_mode':{'type':'string','title':'Tryb wysyłki','enum':['preview','live'],'options':{'enum_titles':['Podgląd - bez zapisu','Produkcyjny - zapis do Sellasist']},'propertyOrder':1},
   'replace_images':{'type':'boolean','title':'Zastępuj całe galerie zdjęć','propertyOrder':2},
   'image_payload_format':{'type':'string','title':'Format elementów images (potwierdź według OpenAPI)','enum':['url_strings','objects_url'],'propertyOrder':3},
   'send_empty_gallery':{'type':'boolean','title':'Zezwól na wyczyszczenie galerii (ryzykowne)','propertyOrder':4}
  },'required':['write_mode','replace_images','image_payload_format','send_empty_gallery']}
 ], 'icon': icon
}
assert 3<=len(manifest['name'])<=30
assert 20<=len(manifest['description'])<=200
assert len(raw)<10_000
(root/'manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print('Zapisano manifest; rozmiar ikony:',len(raw),'B')
