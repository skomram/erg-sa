"""Pure functions: interpretacja udokumentowanych zdarzeń Ergonode Apps."""
from __future__ import annotations
from typing import Any

SUPPORTED_EVENTS = frozenset({
    'app_installed','app_uninstalled',
    'attribute_created','attribute_updated','attribute_deleted',
    'category_created','category_updated','category_deleted',
    'product_created','product_updated','product_deleted',
    'synchronization_started','synchronization_ended',
})

TARGET_FIELDS = {'name','description','ean','images'}

def pick_language(value: Any, preferred: str) -> Any:
    # W dokumentacji przykład używa translation, a schemat value.
    if isinstance(value, list) and value and all(isinstance(x, dict) and 'language' in x for x in value):
        entry = next((x for x in value if x['language'] == preferred), value[0])
        return entry.get('value', entry.get('translation'))
    return value

def parse_images(value: Any, preferred_language: str = 'pl_PL') -> list[str]:
    value = pick_language(value, preferred_language)
    if isinstance(value, dict):
        value = [value]
    if not isinstance(value, list):
        raise ValueError('Zdjęcia IMAGE/GALLERY muszą zawierać obiekt lub listę obiektów z URL')
    urls=[]
    for element in value:
        if not isinstance(element, dict) or not isinstance(element.get('url'), str):
            raise ValueError('Brak właściwości url w elemencie galerii')
        url=element['url'].strip()
        if not url.startswith('https://'):
            raise ValueError('Wymagane adresy HTTPS do zdjęć')
        if url not in urls:
            urls.append(url)
    return urls

def build_delta(event: dict, mapping: list[dict], language: str = 'pl_PL') -> tuple[dict, bool]:
    """Zwraca tylko pola zmienione; nie usuwa całej galerii przy zwykłych zmianach produktu."""
    out: dict[str, Any] = {}
    gallery_touched=False
    allowed={m['ergonode']:m['app'] for m in mapping if isinstance(m,dict) and m.get('ergonode') and m.get('app') in TARGET_FIELDS}
    for item in event.get('synchronization',{}).get('events',[]):
        kind=item.get('type'); payload=item.get('payload') or {}
        src=payload.get('attribute_code'); target=allowed.get(src)
        if not target:
            continue
        if kind in ('product_value_added','product_value_changed'):
            if target=='images':
                if payload.get('attribute_type') not in ('IMAGE','GALLERY'):
                    raise ValueError('Atrybut zdjęć musi mieć typ IMAGE lub GALLERY')
                out[target]=parse_images(payload.get('value'),language)
                gallery_touched=True
            else:
                if payload.get('attribute_type') in ('FILE','IMAGE','GALLERY','PRODUCT_RELATION'):
                    raise ValueError(f'Nieprawidłowy typ pola tekstowego {target}')
                out[target]=pick_language(payload.get('value'),language)
        elif kind=='product_value_removed':
            # Brak automatycznego niszczenia danych - atrybut zdjęć wymaga osobnego opt-in.
            if target=='images':
                out['images']=[]
                gallery_touched=True
    return out,gallery_touched

def build_sellasist_payload(delta: dict, gallery_touched:bool, settings:dict) -> dict:
    payload={k:v for k,v in delta.items() if k!='images' and v is not None}
    if gallery_touched and settings.get('replace_images',False):
        urls=delta['images']
        if not urls and not settings.get('send_empty_gallery',False):
            raise ValueError('Pusta galeria: blokada bezpieczeństwa przed usunięciem zdjęć')
        format_=settings.get('image_payload_format','url_strings')
        if format_=='objects_url':
            payload['images']=[{'url':u} for u in urls]
        elif format_=='url_strings':
            payload['images']=urls
        else:
            raise ValueError('Nieznany format galerii Sellasist')
        payload['images_replacement_flag']=True
    return payload
