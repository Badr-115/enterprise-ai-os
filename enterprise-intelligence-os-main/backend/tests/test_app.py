from io import BytesIO

from fastapi.testclient import TestClient
from openpyxl import Workbook
from app.main import app
client=TestClient(app)
CSV=b'date,revenue,cost,units\n2025-01-01,100,60,4\n2025-01-02,120,70,5\n2025-01-03,110,65,4\n2025-01-04,1000,50,6\n'
KNOWN_CSV=b'date,department,revenue,cost,units\n2026-01-01,Sales,100,60,1\n2026-01-02,Sales,200,120,2\n2026-01-03,Operations,300,150,3\n'
def test_health():
 response = client.get('/api/health')
 assert response.json()['status'] == 'ok'
 assert response.json()['version'] == '0.2.0'
 assert response.json()['capabilities']['deterministic_analysis'] is True
 assert 'gemini_configured' in response.json()['providers']
def test_upload_kpis_and_workflow():
 r=client.post('/api/datasets/upload',files={'file':('sample.csv',CSV,'text/csv')}); assert r.status_code==200; d=r.json(); assert d['kpis']['total_revenue']==1330.0; assert d['anomalies']
 t=client.post('/api/tasks',json={'dataset_id':d['id'],'prompt':'Review risk and data quality'}); assert t.status_code==200; body=t.json(); assert body['verification']['approved']
 assert {call['tool'] for call in body['tool_calls']} >= {'dataset_profile','profitability_check','quality_audit','anomaly_review'}
 assert body['workflow_metadata']['mode']=='bounded_deterministic_tools'
 grouped_dataset=client.post('/api/datasets/upload',files={'file':('grouped.csv',KNOWN_CSV,'text/csv')}).json()
 grouped=client.post('/api/tasks',json={'dataset_id':grouped_dataset['id'],'prompt':'Compare revenue by department'})
 assert grouped.status_code==200
 breakdown=next(call for call in grouped.json()['tool_calls'] if call['tool']=='category_breakdown')
 assert breakdown['ok'] is True
 assert breakdown['data']['group_by']=='department'
def test_rejections():
 assert client.post('/api/datasets/upload',files={'file':('a.txt',b'x','text/plain')}).json()['code']=='request_failed'
 assert client.post('/api/datasets/upload',files={'file':('a.csv',b'foo,bar\n1,2','text/csv')}).json()['code']=='request_failed'
 empty=client.post('/api/datasets/upload',files={'file':('empty.csv',b'','text/csv')}).json()
 assert empty['message']=='The uploaded file is empty'
 assert empty['request_id']
 assert client.post('/api/datasets/upload',files={'file':('bad.csv',b'date,revenue,cost,units\nnot-a-date,nope,nope,nope\n','text/csv')}).status_code==400
 assert client.post('/api/datasets/upload',files={'file':('empty.xlsx',b'PK\x03\x04','application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')}).status_code==400

def test_unicode_filename_and_arabic_content():
 content='date,revenue,cost,units\n2026-01-01,١٠٠,٥٠,٢\n'.encode('utf-8')
 response=client.post('/api/datasets/upload',files={'file':('بيانات.csv',content,'text/csv')})
 assert response.status_code==200
 assert response.json()['kpis']['total_revenue']==100.0

def test_xlsx_upload_is_parsed_and_persisted():
 workbook = Workbook()
 sheet = workbook.active
 sheet.append(['date', 'revenue', 'cost', 'units'])
 sheet.append(['2026-01-01', 250, 100, 3])
 content = BytesIO()
 workbook.save(content)
 response = client.post(
  '/api/datasets/upload',
  files={'file': ('operations.xlsx', content.getvalue(), 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')},
 )
 assert response.status_code == 200
 dataset = response.json()
 assert dataset['rows'] == 1
 assert dataset['kpis']['total_revenue'] == 250.0
 assert len(dataset['content_hash']) == 64
 assert client.get(f"/api/datasets/{dataset['id']}").json()['id'] == dataset['id']

def test_duplicate_content_is_recognized_without_merging_records():
 first=client.post('/api/datasets/upload',files={'file':('first.csv',CSV,'text/csv')}).json()
 second=client.post('/api/datasets/upload',files={'file':('second.csv',CSV,'text/csv')}).json()
 assert first['id'] != second['id']
 assert second['duplicate_of'] == first['id']

def test_arabic_column_names_are_normalized():
 content='التاريخ,الإيرادات,التكلفة,الوحدات\n2026-01-01,١٠٠,٥٠,٢\n'.encode('utf-8')
 response=client.post('/api/datasets/upload',files={'file':('بيانات-عربية.csv',content,'text/csv')})
 assert response.status_code==200
 dataset=response.json()
 assert dataset['columns']==['date','revenue','cost','units']
 assert dataset['kpis']['total_revenue']==100.0
 assert dataset['kpis']['total_cost']==50.0

def test_oversized_upload():
 response=client.post('/api/datasets/upload',files={'file':('large.csv',b'x'*(5*1024*1024+1),'text/csv')})
 assert response.status_code==400
 assert '5 MB' in response.json()['message']

def test_task_contract_and_idempotency():
 dataset=client.post('/api/datasets/upload',files={'file':('idempotent.csv',CSV,'text/csv')}).json()
 headers={'Idempotency-Key':'test-request-1','X-Request-ID':'request-1'}
 first=client.post('/api/tasks',json={'dataset_id':dataset['id'],'prompt':'Review performance'},headers=headers)
 second=client.post('/api/tasks',json={'dataset_id':dataset['id'],'prompt':'Review performance'},headers=headers)
 assert first.status_code==second.status_code==200
 assert first.json()['id']==second.json()['id']
 assert first.json()['dataset_id']==dataset['id']
 assert first.json()['verification']['checked_claims']

def test_missing_resources_use_error_contract():
 response=client.get('/api/datasets/missing-dataset')
 assert response.status_code==404
 assert response.json()['code']=='request_failed'
 assert response.json()['message']=='Dataset not found'
 assert response.json()['request_id']
 invalid=client.post('/api/tasks',json={'dataset_id':'','prompt':'x'})
 assert invalid.status_code==422
 assert invalid.json()['code']=='invalid_request'

def test_provider_failure_is_not_exposed(monkeypatch):
 from app.agents import workflow
 class FailingProvider:
  def __init__(self): pass
  def complete(self, prompt): raise RuntimeError('secret provider response')
 monkeypatch.setattr(workflow, 'GeminiProvider', FailingProvider)
 dataset=client.post('/api/datasets/upload',files={'file':('provider.csv',CSV,'text/csv')}).json()
 response=client.post('/api/tasks',json={'dataset_id':dataset['id'],'prompt':'Review performance'})
 assert response.status_code==200
 body=response.json()
 assert 'secret provider response' not in response.text
 assert any(item['status']=='failed' for item in body['executions'])

def test_upload_to_analysis_report():
 response=client.post('/api/datasets/upload',files={'file':('workflow.csv',CSV,'text/csv')})
 dataset=response.json()
 task_response=client.post('/api/tasks',json={'dataset_id':dataset['id'],'prompt':'Review performance'})
 body=task_response.json()
 assert task_response.status_code==200
 assert body['verification']['approved'] is True
 assert body['report']['findings']

def test_health_and_upload_api_contract():
 health=client.get('/api/health')
 assert health.status_code==200
 assert health.json()['mode']=='local-demo'
 upload=client.post('/api/datasets/upload',files={'file':('contract.csv',CSV,'text/csv')})
 assert upload.status_code==200
 assert {'id','name','rows','columns','kpis','warnings','anomalies','preview'} <= upload.json().keys()

def test_known_csv_is_retained_and_analyzed():
 response=client.post('/api/datasets/upload',files={'file':('known.csv',KNOWN_CSV,'text/csv')})
 assert response.status_code==200
 dataset=response.json()
 assert dataset['rows']==3
 assert dataset['preview'][2]['department']=='Operations'
 assert dataset['kpis']['total_revenue']==600.0
 assert dataset['kpis']['total_cost']==330.0
 assert dataset['kpis']['gross_margin']==270.0
 assert client.get(f"/api/datasets/{dataset['id']}").json()['id']==dataset['id']
 analysis=client.post('/api/tasks',json={'dataset_id':dataset['id'],'prompt':'Analyze known regression dataset'})
 assert analysis.status_code==200
 assert analysis.json()['verification']['approved'] is True
 assert analysis.json()['dataset_id']==dataset['id']
 assert client.get('/api/tasks').json()[0]['id']==analysis.json()['id']
 exported=client.get(f"/api/tasks/{analysis.json()['id']}/export")
 assert exported.status_code==200
 assert 'Content-Disposition' in exported.headers
 assert 'تقرير الذكاء الإداري' in exported.text

def test_sample_data_is_not_automatically_ingested():
 mock=client.get('/api/datasets').json()
 assert not any(item['name']=='mock_data.csv' for item in mock)

def test_business_question_is_grounded_in_selected_dataset():
 question_csv=b'date,department,revenue,cost,units\n2026-01-01,Sales,100,60,1\n2026-01-02,Sales,200,120,2\n2026-01-03,Operations,500,150,3\n'
 response=client.post('/api/datasets/upload',files={'file':('question.csv',question_csv,'text/csv')})
 dataset=response.json()
 question=client.post('/api/questions',json={'dataset_id':dataset['id'],'question':'Which department has the highest revenue?'})
 assert question.status_code==200
 body=question.json()
 assert body['status']=='completed'
 assert 'Operations' in body['answer']
 assert any(item['row']==4 for item in body['evidence'])

def test_revenue_change_orders_dates_not_file_rows():
 content=b'date,revenue,cost,units\n2026-01-03,300,100,3\n2026-01-01,100,50,1\n2026-01-02,200,75,2\n'
 dataset=client.post('/api/datasets/upload',files={'file':('unordered.csv',content,'text/csv')}).json()
 response=client.post('/api/questions',json={'dataset_id':dataset['id'],'question':'How did revenue change over time?'})
 assert response.status_code==200
 body=response.json()
 assert '100.00' in body['answer'] and '2026-01-01' in body['answer']
 assert body['evidence'][0]['row']==3
 assert body['evidence'][1]['row']==2

def test_upload_rejects_extension_without_reading_as_supported_content():
 response=client.post('/api/datasets/upload',files={'file':('data.json',b'{}','application/json')})
 assert response.status_code==400
 assert response.json()['message']=='Only CSV and XLSX files are supported'

def test_unsupported_business_question_is_explicit():
 response=client.post('/api/datasets/upload',files={'file':('unsupported.csv',CSV,'text/csv')})
 question=client.post('/api/questions',json={'dataset_id':response.json()['id'],'question':'Forecast next year'})
 assert question.status_code==200
 assert question.json()['status']=='unsupported'

def test_data_quality_center_reports_structured_issues_without_mutating_source():
 content=b'''date,department,revenue,cost,units
2026-01-01,Sales,100,60,1
2026-01-01,Sales,100,60,1
not-a-date,sales,120,70,2
2026-01-04,Operations,1000,50,3
2026-01-05,Sales,140,,4
'''
 response=client.post('/api/datasets/upload',files={'file':('quality.csv',content,'text/csv')})
 assert response.status_code==200
 body=response.json()
 quality=body['quality']
 types={issue['type'] for issue in quality['issues']}
 assert {'duplicate_records','invalid_dates','missing_values','outlier','inconsistent_categories'} <= types
 assert quality['issue_count'] >= 5
 assert quality['rows_affected'] > 0
 assert body['preview'][0]['revenue']==100
 assert body['preview'][0]['department']=='Sales'
 assert quality['has_blocking_issues'] is True

def test_deterministic_question_operations_and_history_deduplicate():
 content=b'date,department,revenue,cost,units\n2026-02-01,Sales,10,5,1\n2026-02-02,Sales,30,15,2\n2026-02-03,Operations,20,10,3\n'
 dataset=client.post('/api/datasets/upload',files={'file':('operations.csv',content,'text/csv')}).json()
 dataset_id=dataset['id']
 cases={
  'What is the total revenue?': ('total', '60.00'),
  'What is the average revenue?': ('average', '20.00'),
  'What is the minimum revenue?': ('minimum', '10.00'),
  'What is the maximum revenue?': ('maximum', '30.00'),
  'Show revenue by department': ('grouping', 'Sales=40.00'),
  'Compare revenue between Sales and Operations': ('comparison', 'Sales=40.00'),
 }
 for prompt, (intent, expected) in cases.items():
  response=client.post('/api/questions',json={'dataset_id':dataset_id,'question':prompt})
  assert response.status_code==200
  assert response.json()['intent']==intent
  assert expected in response.json()['answer']
 missing=client.post('/api/questions',json={'dataset_id':dataset_id,'question':'How many missing values are there?'})
 assert missing.json()['intent']=='data_quality'
 first=client.post('/api/questions',json={'dataset_id':dataset_id,'question':'What is the total revenue?'})
 second=client.post('/api/questions',json={'dataset_id':dataset_id,'question':' what is   the TOTAL revenue? '})
 assert first.json()['id']==second.json()['id']
 assert any(item['id']==first.json()['id'] for item in client.get('/api/questions/history').json())
 exported=client.get(f"/api/questions/{first.json()['id']}/export")
 assert exported.status_code==200
 assert 'What is the total revenue?' in exported.text
 assert 'صف' in exported.text
 assert 'Content-Disposition' in exported.headers

def test_export_contains_question_method_and_evidence():
 dataset=client.post('/api/datasets/upload',files={'file':('export.csv',CSV,'text/csv')}).json()
 result=client.post('/api/tasks',json={'dataset_id':dataset['id'],'prompt':'Which revenue result should leadership review?'})
 exported=client.get(f"/api/tasks/{result.json()['id']}/export")
 assert exported.status_code==200
 assert 'Which revenue result should leadership review?' in exported.text
 assert 'المنهج' in exported.text
 assert 'kpis.margin_rate' in exported.text


def test_demo_dataset_endpoint_creates_a_real_analyzable_dataset():
 response = client.post('/api/datasets/demo')
 assert response.status_code == 200
 dataset = response.json()
 assert dataset['name'] == 'demo-sales.csv'
 assert dataset['rows'] >= 20
 assert dataset['kpis']['total_revenue'] > 0
 assert client.get(f"/api/datasets/{dataset['id']}").status_code == 200
 analysis = client.post('/api/tasks', json={'dataset_id': dataset['id'], 'prompt': 'حلل الأداء والمخاطر وجودة البيانات'})
 assert analysis.status_code == 200
 assert analysis.json()['report']['findings']


def test_cors_allows_only_the_default_local_frontend_origins():
 allowed = client.options('/api/health', headers={
  'Origin': 'http://localhost:3000',
  'Access-Control-Request-Method': 'GET',
 })
 assert allowed.headers.get('access-control-allow-origin') == 'http://localhost:3000'
 rejected = client.options('/api/health', headers={
  'Origin': 'https://untrusted.example',
  'Access-Control-Request-Method': 'GET',
 })
 assert 'access-control-allow-origin' not in rejected.headers
