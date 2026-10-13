from fastapi import FastAPI, File, Header, HTTPException, Request, UploadFile
from fastapi.encoders import jsonable_encoder
from fastapi.middleware.cors import CORSMiddleware
from fastapi.exceptions import RequestValidationError
from fastapi.responses import HTMLResponse, JSONResponse
from .services.analytics import MAX_BYTES, analyze_file
from .schemas.models import ApiError, DatasetResponse, QuestionRequest, QuestionResponse, TaskRequest, TaskResponse
from .agents.workflow import run_workflow
from .services.questions import answer_question
from .db import store
import html
import logging
import hashlib
import tempfile
import uuid
import json
import os
from pathlib import Path

logger = logging.getLogger(__name__)
app=FastAPI(title='Enterprise Intelligence OS',version='0.2.0')
# Configure explicit trusted frontend origins for local and deployed environments.
_configured_origins = os.getenv('EIOS_CORS_ORIGINS', 'http://localhost:3000,http://127.0.0.1:3000')
_allowed_origins = [origin.strip().rstrip('/') for origin in _configured_origins.split(',') if origin.strip()]
app.add_middleware(
 CORSMiddleware,
 allow_origins=_allowed_origins,
 allow_methods=['GET','POST','OPTIONS'],
 allow_headers=['Content-Type','Idempotency-Key','X-Request-ID'],
)
store.initialize()


def request_id(request: Request) -> str:
    return request.headers.get("X-Request-ID", uuid.uuid4().hex)


def error_response(request: Request, code: str, message: str, status_code: int) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content=ApiError(code=code, message=message, request_id=request_id(request)).model_dump(),
    )


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
    detail = exc.detail if isinstance(exc.detail, str) else "تعذر إكمال الطلب."
    return error_response(request, "request_failed", detail, exc.status_code)


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    logger.info("Request validation failed: %s", exc.errors())
    return error_response(request, "invalid_request", "الطلب غير صالح. راجع المدخلات وحاول مرة أخرى.", 422)


@app.exception_handler(Exception)
async def unexpected_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    logger.exception("Unhandled request failure")
    return error_response(request, "internal_error", "حدث خطأ غير متوقع. حاول مرة أخرى.", 500)

@app.get('/api/health')
def health():
 return {
  'status': 'ok',
  'service': 'enterprise-intelligence-os',
  'version': app.version,
  'mode': 'local-demo',
  'providers': {'gemini_configured': bool(os.getenv('GEMINI_API_KEY', '').strip())},
  'capabilities': {'file_upload': True, 'deterministic_analysis': True, 'report_export': True},
 }
@app.post('/api/datasets/upload',response_model=DatasetResponse)
async def upload(file:UploadFile=File(...)):
 temp_path: str | None = None
 try:
  if not file.filename:
   raise ValueError("A filename is required")
  suffix = file.filename.lower().rsplit(".", 1)[-1] if "." in file.filename else ""
  if suffix not in {"csv", "xlsx"}:
   raise ValueError("Only CSV and XLSX files are supported")
  digest = hashlib.sha256()
  total = 0
  with tempfile.NamedTemporaryFile(prefix="eios-upload-", suffix=f".{suffix}", delete=False) as target:
   temp_path = target.name
   while chunk := await file.read(1024 * 1024):
    total += len(chunk)
    if total > MAX_BYTES:
     raise ValueError("File exceeds the 5 MB upload limit")
    digest.update(chunk)
    target.write(chunk)
  result=analyze_file(temp_path,file.filename,digest.hexdigest())
 except ValueError as e: raise HTTPException(400,str(e))
 finally:
  await file.close()
  if temp_path:
   try:
    import os
    os.unlink(temp_path)
   except FileNotFoundError:
    pass
 payload=jsonable_encoder(result)
 duplicates = [
  item["id"] for item in store.list_datasets()
  if item.get("content_hash") == payload.get("content_hash")
 ]
 if duplicates:
  payload["duplicate_of"] = duplicates[0]
 store.save_dataset(result.id, payload); return payload
@app.post('/api/datasets/demo', response_model=DatasetResponse)
def create_demo_dataset():
 # Use a repository-owned fixture only; callers cannot choose a filesystem path.
 sample_path = Path(__file__).resolve().parents[2] / 'mock_data.csv'
 if not sample_path.is_file():
  raise HTTPException(503, 'The demo dataset is not available in this installation')
 content = sample_path.read_bytes()
 if not content or len(content) > MAX_BYTES:
  raise HTTPException(503, 'The demo dataset is invalid or exceeds the upload limit')
 digest = hashlib.sha256(content).hexdigest()
 result = analyze_file(str(sample_path), 'demo-sales.csv', digest)
 payload = jsonable_encoder(result)
 duplicates = [item['id'] for item in store.list_datasets() if item.get('content_hash') == digest]
 if duplicates:
  payload['duplicate_of'] = duplicates[0]
 store.save_dataset(result.id, payload)
 return payload


@app.get('/api/datasets',response_model=list[DatasetResponse])
def datasets(): return store.list_datasets()
@app.get('/api/datasets/{dataset_id}',response_model=DatasetResponse)
def dataset(dataset_id:str):
 result=store.get_dataset(dataset_id)
 if result is None: raise HTTPException(404,'Dataset not found')
 return result
@app.post('/api/questions', response_model=QuestionResponse)
def question(req: QuestionRequest):
 dataset_result = store.get_dataset(req.dataset_id)
 if dataset_result is None:
  raise HTTPException(404, 'Dataset not found')
 fingerprint = hashlib.sha256(json.dumps(
  {"dataset_id": req.dataset_id, "question": " ".join(req.question.casefold().split())},
  sort_keys=True,
 ).encode()).hexdigest()
 previous = store.get_question_by_fingerprint(fingerprint)
 if previous is not None:
  return previous
 return store.save_question(answer_question(dataset_result, req.question), fingerprint)

@app.get('/api/questions/history', response_model=list[QuestionResponse])
def question_history():
 return store.list_questions()
@app.get('/api/questions/{question_id}/export', response_class=HTMLResponse)
def export_question(question_id: str):
 questions = [item for item in store.list_questions() if item.get("id") == question_id]
 if not questions:
  raise HTTPException(404, 'Question result not found')
 result = questions[0]
 evidence = ''.join(
  f'<li><strong>{html.escape(str(item.get("field", "")))}'
  f'{" · الصف " + str(item.get("row")) if item.get("row") else ""}</strong>: '
  f'{html.escape(str(item.get("explanation", "")))} · '
  f'{html.escape(str(item.get("value", "—")))}</li>'
  for item in result.get("evidence", [])
 )
 calculations = ''.join(f'<li>{html.escape(str(item))}</li>' for item in result.get("calculations", []))
 limitations = ''.join(f'<li>{html.escape(str(item))}</li>' for item in result.get("limitations", []))
 document = (
  '<!doctype html><html lang="ar" dir="rtl"><head><meta charset="utf-8">'
  '<title>نتيجة سؤال أعمال</title><style>body{font:16px system-ui;max-width:800px;'
  'margin:48px auto;color:#17202b;direction:rtl;text-align:right}li{margin:10px 0}'
  '</style></head><body><p>نظام ذكاء المؤسسة · نتيجة موثقة</p>'
  f'<h1>{html.escape(str(result.get("answer", "")))}</h1>'
  f'<h2>السؤال</h2><p>{html.escape(str(result.get("question", "")))}</p>'
  '<h2>المنهج والحساب</h2><ul>'
  f'{calculations}</ul><h2>الأدلة</h2><ul>{evidence}</ul>'
  f'<h2>الحدود</h2><ul>{limitations}</ul></body></html>'
 )
 return HTMLResponse(
  document,
  headers={"Content-Disposition": f'attachment; filename="{question_id}-question.html"'},
 )
@app.post('/api/tasks',response_model=TaskResponse)
def task(req:TaskRequest, idempotency_key: str | None = Header(default=None, alias="Idempotency-Key")):
 dataset_result=store.get_dataset(req.dataset_id)
 if dataset_result is None: raise HTTPException(404,'Dataset not found')
 if idempotency_key:
  if len(idempotency_key) > 200: raise HTTPException(400, 'Idempotency-Key is too long')
  previous = store.get_task_by_idempotency_key(idempotency_key)
  if previous is not None: return previous
 result=run_workflow(type('StoredDataset', (), dataset_result)(),req.prompt)
 item={'id':uuid.uuid4().hex,'dataset_id':req.dataset_id,'prompt':req.prompt,'status':result['status'],**result}
 inserted = store.save_task(item['id'], req.dataset_id, item, idempotency_key)
 if not inserted and idempotency_key:
  return store.get_task_by_idempotency_key(idempotency_key) or item
 return store.get_task(item['id']) or item
@app.get('/api/tasks',response_model=list[TaskResponse])
def tasks(): return store.list_tasks()
@app.get('/api/tasks/{task_id}',response_model=TaskResponse)
def get_task(task_id:str):
 result=store.get_task(task_id)
 if result is None: raise HTTPException(404,'Task not found')
 return result
@app.get('/api/tasks/{task_id}/export', response_class=HTMLResponse)
def export_task(task_id:str):
 item=store.get_task(task_id)
 if item is None: raise HTTPException(404,'Task not found')
 report=item.get('report') or {}
 prompt=html.escape(str(item.get('prompt', '')))
 method=html.escape('حسابات حتمية من المصدر المحفوظ، مع تحقق الادعاءات مقابل مؤشرات المجموعة.')
 limitations=''.join(f'<li>{html.escape(str(value))}</li>' for value in report.get('limitations', []))
 findings=''.join(f'<li><strong>{html.escape(str(finding.get("text", "")))}</strong><br><small>الدليل: {html.escape(", ".join(finding.get("evidence", [])))}</small></li>' for finding in report.get('findings', []))
 document=f"""<!doctype html><html lang="ar" dir="rtl"><head><meta charset="utf-8"><title>تقرير الذكاء الإداري</title><style>body{{font:16px system-ui;max-width:800px;margin:48px auto;color:#17202b;direction:rtl;text-align:right}}h1{{font-family:Tahoma,system-ui,sans-serif}}li{{margin:14px 0}}small{{color:#0e7c73}}</style></head><body><p>نظام ذكاء المؤسسة · تقرير محلي موثق</p><h1>تقرير الذكاء الإداري</h1><h2>السؤال</h2><p>{prompt}</p><h2>النتيجة</h2><p>{html.escape(str(report.get('summary', '')))}</p><h2>المنهج</h2><p>{method}</p><h2>النتائج والأدلة</h2><ul>{findings}</ul><h2>الحدود</h2><ul>{limitations}</ul></body></html>"""
 return HTMLResponse(document, headers={"Content-Disposition": f'attachment; filename="{task_id}-report.html"'})
