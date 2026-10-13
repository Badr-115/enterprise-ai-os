const API=process.env.NEXT_PUBLIC_API_URL||'/api';
export type ApiError = { code:string; message:string; request_id:string };

export type HealthResponse = {
 status: 'ok' | 'degraded';
 service: string;
 version: string;
 mode: string;
 providers: { gemini_configured: boolean };
 capabilities: { file_upload: boolean; deterministic_analysis: boolean; report_export: boolean };
};
export async function health(): Promise<HealthResponse> {
 try {
  const response = await fetch(`${API}/health`, { cache: 'no-store' });
  if (!response.ok) throw await requestError(response, 'تعذر فحص حالة الخدمة.');
  return await response.json() as HealthResponse;
 } catch (error) {
  if (!isNetworkError(error)) throw error;
  throw new Error('تعذر الوصول إلى خادم التحليل. تحقق من تشغيل الخادم وإعداد عنوان API.');
 }
}

const arabicErrors: Record<string, string> = {
  'The uploaded file is empty': 'الملف المرفوع فارغ.',
  'Only CSV and XLSX files are supported': 'يُسمح برفع ملفات CSV وXLSX فقط.',
  'The file could not be parsed safely. Check that it is a valid UTF-8 CSV or XLSX file.': 'تعذر قراءة الملف. تأكد من أن CSV أو XLSX صالح وقابل للقراءة.',
  'The dataset could not be uploaded.': 'تعذر رفع مجموعة البيانات.',
  'The analysis could not be started.': 'تعذر بدء التحليل.',
  'Dataset not found': 'مجموعة البيانات غير موجودة.',
  'Task not found': 'المهمة غير موجودة.',
  'The datasets could not be loaded.': 'تعذر تحميل مجموعات البيانات.',
  'The task history could not be loaded.': 'تعذر تحميل سجل المهام.',
  'The task could not be loaded.': 'تعذر تحميل المهمة.',
  'The report could not be exported.': 'تعذر تصدير التقرير.',
};
function localizeError(message: string): string {
  const missing = message.match(/^Missing required columns: (.+)$/);
  if (missing) return `الأعمدة المطلوبة مفقودة: ${missing[1]}`;
  return arabicErrors[message] ?? message;
}
async function requestError(response:Response, fallback:string){
 const body = await response.json().catch(() => null) as Partial<ApiError> & { detail?: string } | null;
 const message = typeof body?.message === 'string' ? body.message : typeof body?.detail === 'string' ? body.detail : fallback;
 const error = new Error(localizeError(message));
 if (body?.request_id) error.name = `API request ${body.request_id}`;
 return error;
}
function isNetworkError(error:unknown): boolean { return error instanceof TypeError; }
async function request(responsePromise: Promise<Response>, fallback: string): Promise<Response> {
 const response = await responsePromise;
 if (response.ok) return response;
 if (response.status >= 500) throw new Error('الخدمة غير متاحة حاليًا. تأكد من تشغيل خادم التحليل ثم حاول مرة أخرى.');
 throw await requestError(response, fallback);
}
export async function upload(file:File): Promise<DatasetResponse> {
 const form=new FormData(); form.append('file',file);
 try{ const response=await request(fetch(`${API}/datasets/upload`,{method:'POST',body:form}),'The dataset could not be uploaded.'); return await response.json(); }
 catch(error){ if(!isNetworkError(error)) throw error; throw new Error('الخدمة غير متاحة. تأكد من تشغيل الخادم ثم حاول مرة أخرى.'); }
}
export async function createDemoDataset(): Promise<DatasetResponse> {
 try {
  const response = await fetch(`${API}/datasets/demo`, { method: 'POST' });
  if (!response.ok) throw await requestError(response, 'تعذر إنشاء مجموعة البيانات التجريبية.');
  return await response.json() as DatasetResponse;
 } catch (error) {
  if (!isNetworkError(error)) throw error;
  throw new Error('تعذر الوصول إلى خادم التحليل. تحقق من تشغيل الخادم ثم حاول مرة أخرى.');
 }
}
export async function datasets(): Promise<DatasetResponse[]> {
 try{ const response=await fetch(`${API}/datasets`); if(!response.ok) throw await requestError(response,'The datasets could not be loaded.'); return await response.json(); }
 catch(error){ if(!isNetworkError(error)) throw error; throw new Error('الخدمة غير متاحة. تأكد من تشغيل الخادم ثم حاول مرة أخرى.'); }
}
export async function getDataset(datasetId:string): Promise<DatasetResponse> {
 try{ const response=await fetch(`${API}/datasets/${datasetId}`); if(!response.ok) throw await requestError(response,'The dataset could not be loaded.'); return await response.json(); }
 catch(error){ if(!isNetworkError(error)) throw error; throw new Error('الخدمة غير متاحة. تأكد من تشغيل الخادم ثم حاول مرة أخرى.'); }
}
export type DatasetResponse = {
 id:string; name:string; rows:number; columns:string[];
 duplicate_of?:string|null; created_at?:string|null; content_hash?:string|null;
 kpis: { total_revenue:number|null; total_cost:number|null; total_units:number|null; gross_margin:number|null; margin_rate:number|null; daily_revenue?:Array<{date:string;value:number}> };
 warnings:string[]; anomalies:Array<{row:number;metric:string;value:number;reason:string;bounds?:number[]}>;
 summary:{date_range?:[string|null,string|null];numeric_columns?:string[]};
 preview:Array<Record<string,string|number|null>>;
 quality:{issues:Array<{type:'missing_values'|'duplicate_records'|'invalid_dates'|'invalid_numeric'|'inconsistent_categories'|'outlier'|'schema_problem';severity:'info'|'warning'|'error';message:string;columns:string[];rows:number[];count:number;details:string[]}>;issue_count:number;rows_affected:number;has_blocking_issues:boolean};
};
export type ReportResponse = { title:string; summary:string; findings:Array<{text:string;evidence:string[]}>; limitations:string[]; recommendations?:string[]; ai_insight?:string };
export type TaskResponse = { id:string; dataset_id:string; prompt:string; status:'completed'|'failed'|'running'; simulated:boolean; executions:Array<{agent:string;status:'completed'|'failed'|'running';output?:{findings?:Array<Record<string,unknown>>;warnings?:string[];[key:string]:unknown};error?:string}>; report?:ReportResponse; verification?:{approved:boolean;checked_at?:string;checked_claims?:Array<Record<string,unknown>>;notes?:string}; tool_calls?:Array<{tool:string;ok:boolean;summary:string;duration_ms:number;data:Record<string,unknown>}>; workflow_metadata?:{version?:string;mode?:string;max_tool_calls?:number} };
export type QuestionResponse = { id:string; dataset_id:string; question:string; status:'completed'|'unsupported'; intent:string; answer:string; calculations:string[]; evidence:Array<{row:number|null;field:string;value:unknown;explanation:string}>; assumptions:string[]; limitations:string[] };
export async function askQuestion(dataset_id:string, question:string): Promise<QuestionResponse> {
 try {
  const response=await fetch(`${API}/questions`,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({dataset_id,question})});
  if(!response.ok) throw await requestError(response,'The business question could not be answered.');
  return await response.json();
 } catch(error) { if(!isNetworkError(error)) throw error; throw new Error('الخدمة غير متاحة. تأكد من تشغيل الخادم ثم حاول مرة أخرى.'); }
}
export async function exportQuestion(questionId:string): Promise<void> {
 const response=await fetch(`${API}/questions/${questionId}/export`);
 if(!response.ok) throw await requestError(response,'The question result could not be exported.');
 const blob=await response.blob(); const link=document.createElement('a');
 const objectUrl=URL.createObjectURL(blob); link.href=objectUrl;
 link.download=`${questionId}-question.html`; link.click(); window.setTimeout(() => URL.revokeObjectURL(objectUrl), 1000);
}
export async function task(dataset_id:string, idempotencyKey?:string, prompt='Analyze business performance and risk'): Promise<TaskResponse> {
 try{
  const headers: HeadersInit = {'Content-Type':'application/json'};
  if (idempotencyKey) headers['Idempotency-Key'] = idempotencyKey;
  const response=await fetch(`${API}/tasks`,{method:'POST',headers,body:JSON.stringify({dataset_id,prompt})});
  if(!response.ok) throw await requestError(response,'The analysis could not be started.');
  return await response.json();
 }
 catch(error){ if(!isNetworkError(error)) throw error; throw new Error('الخدمة غير متاحة. تأكد من تشغيل الخادم ثم حاول مرة أخرى.'); }
}
export type TaskSummary = { id:string; dataset_id:string; prompt:string; status:TaskResponse['status']; simulated:boolean; report?:Pick<ReportResponse, 'title'|'summary'>; verification?:Pick<NonNullable<TaskResponse['verification']>, 'approved'> };
export async function tasks(): Promise<TaskSummary[]> {
 try{ const response=await fetch(`${API}/tasks`); if(!response.ok) throw await requestError(response,'The task history could not be loaded.'); return await response.json(); }
 catch(error){ if(!isNetworkError(error)) throw error; throw new Error('الخدمة غير متاحة. تأكد من تشغيل الخادم ثم حاول مرة أخرى.'); }
}
export async function getTask(taskId:string): Promise<TaskResponse> {
 try{ const response=await fetch(`${API}/tasks/${taskId}`); if(!response.ok) throw await requestError(response,'The task could not be loaded.'); return await response.json(); }
 catch(error){ if(!isNetworkError(error)) throw error; throw new Error('الخدمة غير متاحة. تأكد من تشغيل الخادم ثم حاول مرة أخرى.'); }
}
export async function exportTask(taskId:string): Promise<void> {
 const response=await fetch(`${API}/tasks/${taskId}/export`);
 if(!response.ok) throw await requestError(response,'The report could not be exported.');
 const blob=await response.blob(); const link=document.createElement('a');
 const objectUrl=URL.createObjectURL(blob);
 link.href=objectUrl; link.download=`${taskId}-report.html`; link.click();
 window.setTimeout(() => URL.revokeObjectURL(objectUrl), 0);
}
