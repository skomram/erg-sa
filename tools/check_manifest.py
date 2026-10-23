"""Walidator ograniczeń jawnie zapisanych w dokumentacji Apps2."""
import base64,json
from pathlib import Path
p=Path(__file__).resolve().parents[1]/'manifest.json'
m=json.loads(p.read_text(encoding='utf-8'))
assert 3<=len(m['name'])<=30
assert 20<=len(m['description'])<=200
assert m['version'] and m['compatible']
assert len(m['icon'].split(';base64,',1))==2
assert len(base64.b64decode(m['icon'].split(';base64,',1)[1]))<10000
assert set(m['features']) <= {'synchronization','synchronization_full','synchronization_scheduler'}
assert set(m['events']) <= {'app_installed','app_uninstalled','attribute_created','attribute_updated','attribute_deleted','category_created','category_updated','category_deleted','product_created','product_updated','product_deleted','synchronization_started','synchronization_ended'}
assert isinstance(m['write_access'],bool)
assert len(m['configuration_schema'])==3
print('Manifest spełnia sprawdzone ograniczenia Apps2')
