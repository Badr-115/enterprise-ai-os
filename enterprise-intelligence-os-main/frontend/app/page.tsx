'use client';

import { DragEvent, useEffect, useMemo, useRef, useState } from 'react';
import { askQuestion, createDemoDataset, datasets, DatasetResponse, exportQuestion, exportTask, getDataset, getTask, health, HealthResponse, QuestionResponse, ReportResponse, task, tasks, TaskResponse, TaskSummary, upload } from '../lib/api';

type Dataset = DatasetResponse;
type Analysis = TaskResponse & { report: ReportResponse; verification: NonNullable<TaskResponse['verification']> };
type View = 'overview' | 'workspace' | 'intelligence' | 'reports' | 'history' | 'operations' | 'settings';

const nav: Array<{ id: View; label: string; caption: string; icon: string }> = [
  { id: 'overview', label: 'نظرة عامة', caption: 'الرؤية التنفيذية', icon: '⌂' },
  { id: 'workspace', label: 'مساحة البيانات', caption: 'استيراد وفحص', icon: '▦' },
  { id: 'intelligence', label: 'الذكاء', caption: 'تشغيل تحليل', icon: '✦' },
  { id: 'reports', label: 'مركز التقارير', caption: 'الأدلة والقرارات', icon: '▤' },
];
const secondaryNav: Array<{ id: View; label: string; icon: string }> = [
  { id: 'history', label: 'سجل المهام', icon: '◷' },
  { id: 'operations', label: 'تشغيل الوكلاء', icon: '◌' },
  { id: 'settings', label: 'الإعدادات', icon: '⚙' },
];
function money(value: number | null | undefined) { return value == null ? '—' : `${value.toLocaleString('ar-SA', { maximumFractionDigits: 0 })} ر.س`; }
function shortDate(value: string | null | undefined) { return value ? new Date(`${value}T00:00:00`).toLocaleDateString('ar-SA', { month: 'short', day: 'numeric' }) : '—'; }
const qualityLabels: Record<string, string> = {
  missing_values: 'قيم مفقودة',
  duplicate_records: 'سجلات مكررة',
  invalid_dates: 'تواريخ غير صالحة',
  invalid_numeric: 'أرقام غير صالحة',
  inconsistent_categories: 'تصنيفات غير متسقة',
  outlier: 'قيم شاذة',
  schema_problem: 'مشكلة في البنية',
};
const qualitySeverityLabels: Record<string, string> = { info: 'معلومة', warning: 'مراجعة', error: 'حاجز' };

function TrendChart({ points }: { points: Array<{ date: string; value: number }> }) {
  if (!points.length) return <div className="chart-empty">لا توجد ملاحظات إيرادات مؤرخة في مجموعة البيانات.</div>;
  const max = Math.max(...points.map((point) => point.value), 1);
  const width = 680; const height = 190; const pad = 22;
  const coords = points.map((point, index) => {
    const x = pad + (index / Math.max(points.length - 1, 1)) * (width - pad * 2);
    const y = height - pad - (point.value / max) * (height - pad * 2);
    return { ...point, x, y };
  });
  return <div className="chart-wrap">
    <svg viewBox={`0 0 ${width} ${height}`} role="img" aria-label="اتجاه الإيرادات اليومية" style={{ direction: 'ltr' }}>
      <line x1={pad} x2={width - pad} y1={height - pad} y2={height - pad} className="chart-axis" />
      <polyline points={coords.map((point) => `${point.x},${point.y}`).join(' ')} className="chart-line" />
      {coords.map((point) => <g key={point.date}><circle cx={point.x} cy={point.y} r="4" className="chart-dot"><title>{`${point.date}: ${money(point.value)}`}</title></circle></g>)}
    </svg>
    <div className="chart-labels"><span>{shortDate(points[0].date)}</span><span>{shortDate(points[points.length - 1].date)}</span></div>
  </div>;
}
function EmptyWorkspace({ onNavigate }: { onNavigate: (view: View) => void }) {
  return <section className="empty-workspace">
    <div className="empty-mark">◎</div>
    <p className="eyebrow">بداية واضحة ومدروسة</p>
    <h2>حوّل بيانات التشغيل إلى رؤية قابلة للقرار.</h2>
    <p>ارفع ملف CSV أو XLSX منظمًا لإنشاء مجموعة بيانات موثوقة، وحساب مؤشرات الأداء، وإتاحة تحليل قائم على الأدلة لفريقك.</p>
    <button className="button primary" onClick={() => onNavigate('workspace')}>افتح مساحة البيانات <span>←</span></button>
    <div className="empty-notes"><span><b>01</b> تحقق من الصفوف</span><span><b>02</b> اكتشف الإشارات</span><span><b>03</b> افهم الأسباب</span></div>
  </section>;
}

export default function Home() {
  const [view, setView] = useState<View>('overview');
  const [dataset, setDataset] = useState<Dataset | null>(null);
  const [availableDatasets, setAvailableDatasets] = useState<Dataset[]>([]);
  const [analysis, setAnalysis] = useState<Analysis | null>(null);
  const [questionResult, setQuestionResult] = useState<QuestionResponse | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const [dragging, setDragging] = useState(false);
  const [search, setSearch] = useState('');
  const [page, setPage] = useState(1);
  const [history, setHistory] = useState<TaskSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [serviceHealth, setServiceHealth] = useState<HealthResponse | null>(null);
  const runRequestKey = useRef<string | null>(null);
  const fileRef = useRef<HTMLInputElement>(null);

  async function handleFile(file?: File) {
    if (!file || busy) return;
    setBusy(true); setError(''); setAnalysis(null);
    try {
      const uploadedDataset = await upload(file);
      setDataset(uploadedDataset);
      setQuestionResult(null);
      setAvailableDatasets((current) => [
        uploadedDataset,
        ...current.filter((item) => item.id !== uploadedDataset.id),
      ]);
      setPage(1);
      setView('workspace');
    }
    catch (reason) { setError(reason instanceof Error ? reason.message : 'The dataset could not be uploaded and analyzed.'); }
    finally { setBusy(false); if (fileRef.current) fileRef.current.value = ''; }
  }
  async function onFile(event: React.ChangeEvent<HTMLInputElement>) { await handleFile(event.target.files?.[0]); }
  async function handleDemoData() {
    if (busy) return;
    setBusy(true); setError(''); setNotice(''); setAnalysis(null); setQuestionResult(null);
    try {
      const sample = await createDemoDataset();
      setDataset(sample);
      setAvailableDatasets((current) => [sample, ...current.filter((item) => item.id !== sample.id)]);
      setSearch(''); setPage(1); setView('workspace');
      setNotice('تم تجهيز مجموعة بيانات تجريبية حقيقية؛ يمكنك الآن فحصها وتشغيل التحليل.');
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : 'تعذر تحميل البيانات التجريبية.');
    } finally { setBusy(false); }
  }
  async function runAnalysis(prompt: string) {
    if (!dataset || busy) return;
    setBusy(true); setError('');
    const requestKey = runRequestKey.current ?? crypto.randomUUID();
    runRequestKey.current = requestKey;
    try {
      const completed = await task(dataset.id, requestKey, prompt);
      if (!completed.report || !completed.verification) throw new Error('استجابة التحليل غير مكتملة.');
      setAnalysis(completed as Analysis);
      try { setHistory(await tasks()); }
      catch (reason) { setError(reason instanceof Error ? reason.message : 'تعذر تحديث سجل المهام.'); }
      runRequestKey.current = null;
      setView('reports');
    }
    catch (reason) { setError(reason instanceof Error ? reason.message : 'The analysis could not be started.'); }
    finally { setBusy(false); }
  }
  async function runQuestion(question: string) {
    if (!dataset || busy) return;
    setBusy(true); setError('');
    try { setQuestionResult(await askQuestion(dataset.id, question)); }
    catch (reason) { setError(reason instanceof Error ? reason.message : 'تعذر الإجابة عن السؤال.'); }
    finally { setBusy(false); }
  }
  function onDrop(event: DragEvent<HTMLDivElement>) { event.preventDefault(); setDragging(false); void handleFile(event.dataTransfer.files[0]); }
  function selectDataset(datasetId: string) {
    const selected = availableDatasets.find((item) => item.id === datasetId);
    if (!selected || selected.id === dataset?.id) return;
    setDataset(selected);
    setAnalysis(null);
    setQuestionResult(null);
    setSearch('');
    setPage(1);
    setError('');
    setView('workspace');
  }
  async function refreshWorkspace(showConfirmation = false) {
    setRefreshing(true);
    setNotice('');
    try {
      const [nextDatasets, nextTasks, nextHealth] = await Promise.all([datasets(), tasks(), health()]);
      setAvailableDatasets(nextDatasets);
      setHistory(nextTasks);
      setServiceHealth(nextHealth);
      setDataset((current) => current
        ? nextDatasets.find((item) => item.id === current.id) ?? nextDatasets[0] ?? null
        : nextDatasets[0] ?? null);
      setError('');
      if (showConfirmation) setNotice('تم تحديث حالة الخدمة ومجموعات البيانات وسجل المهام.');
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : 'تعذر تحديث مساحة العمل.');
    } finally {
      setRefreshing(false);
    }
  }

  useEffect(() => {
    let active = true;
    Promise.allSettled([tasks(), datasets(), health()]).then(async ([historyResult, datasetResult, healthResult]) => {
      if (!active) return;
      if (historyResult.status === 'fulfilled') setHistory(historyResult.value);
      if (datasetResult.status === 'fulfilled') {
        setAvailableDatasets(datasetResult.value);
        if (datasetResult.value[0]) setDataset(datasetResult.value[0] as Dataset);
      }
      if (healthResult.status === 'fulfilled') setServiceHealth(healthResult.value);
      if (historyResult.status === 'fulfilled' && historyResult.value[0]) {
        try {
          const saved = await getTask(historyResult.value[0].id);
          const savedDataset = datasetResult.status === 'fulfilled'
            ? datasetResult.value.find((item) => item.id === saved.dataset_id)
            : undefined;
          if (savedDataset && saved.report && saved.verification && active) {
            setDataset(savedDataset);
            setAnalysis(saved as Analysis);
          }
        } catch {
          if (active) setError('تعذر استعادة آخر تقرير محفوظ. افتح سجل المهام للمحاولة مرة أخرى.');
        }
      }
      const failure = [historyResult, datasetResult, healthResult].find((result) => result.status === 'rejected');
      if (failure?.status === 'rejected') setError(failure.reason instanceof Error ? failure.reason.message : 'تعذر تحميل مساحة العمل.');
    }).finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, []);

  const filteredRows = useMemo(() => dataset?.preview.filter((row) => !search || Object.values(row).some((value) => String(value ?? '').toLowerCase().includes(search.toLowerCase()))) ?? [], [dataset, search]);
  const visibleRows = filteredRows.slice((page - 1) * 5, page * 5);
  const navigate = (next: View) => { setView(next); setError(''); };
  const title = nav.find((item) => item.id === view)?.label ?? secondaryNav.find((item) => item.id === view)?.label ?? 'نظرة عامة';

  return <div className="app-shell">
    <aside className="sidebar">
      <div className="brand"><div className="brand-symbol">E</div><div><strong>المؤسسة</strong><span>نظام الذكاء</span></div></div>
      <div className="workspace-switcher"><span className="workspace-avatar">ن</span><span><b>مساحة محلية</b><small>لا توجد هوية شركة متصلة</small></span></div>
      <nav aria-label="التنقل الرئيسي" className="main-nav">
        <p className="nav-label">مساحة العمل</p>
        {nav.map((item) => <button key={item.id} className={`nav-item ${view === item.id ? 'active' : ''}`} aria-current={view === item.id ? 'page' : undefined} onClick={() => navigate(item.id)}><span className="nav-icon">{item.icon}</span><span><b>{item.label}</b><small>{item.caption}</small></span></button>)}
        <p className="nav-label nav-label-lower">النظام</p>
        {secondaryNav.map((item) => <button key={item.id} className={`nav-item ${view === item.id ? 'active' : ''}`} aria-current={view === item.id ? 'page' : undefined} onClick={() => navigate(item.id)}><span className="nav-icon">{item.icon}</span><span><b>{item.label}</b></span></button>)}
      </nav>
      <div className="sidebar-foot"><span className="live-dot" /> خدمة التحليل المحلية <span className="help-mark" title="لا توجد خدمة خارجية متصلة">؟</span></div>
    </aside>

    <main className="content">
      <header className="topbar"><div className="breadcrumbs"><span>مساحة محلية</span><b>/</b><strong>{title}</strong></div><div className="top-actions"><span className={`system-pill ${serviceHealth?.status === 'ok' ? 'service-online' : 'service-unknown'}`}><i /> {serviceHealth?.status === 'ok' ? 'الخادم متصل' : 'حالة الخادم غير مؤكدة'}</span><button className="icon-action" onClick={() => void refreshWorkspace(true)} disabled={refreshing} aria-label="تحديث حالة النظام والبيانات" title="تحديث الحالة والبيانات">{refreshing ? '…' : '↻'}</button><button className="avatar-button" onClick={() => navigate('settings')} aria-label="فتح إعدادات النظام" title="إعدادات النظام">ن</button></div></header>
      <div className="page-body">
        {notice && <div className="notice-banner" role="status"><span>✓</span>{notice}<button onClick={() => setNotice('')} aria-label="إغلاق إشعار النجاح">×</button></div>}
        {error && <div className="alert" role="alert"><span className="alert-icon">!</span><div><strong>تعذر إكمال العملية</strong><span>{error}</span></div><button onClick={() => setError('')} aria-label="إغلاق التنبيه">×</button></div>}
        {loading ? <LoadingState /> : view === 'overview' && <Overview dataset={dataset} analysis={analysis} onNavigate={navigate} />}
        {view === 'workspace' && <Workspace dataset={dataset} availableDatasets={availableDatasets} onSelectDataset={selectDataset} onDemoData={handleDemoData} busy={busy} dragging={dragging} setDragging={setDragging} onDrop={onDrop} onFile={onFile} fileRef={fileRef} search={search} setSearch={setSearch} page={page} setPage={setPage} filteredRows={filteredRows} visibleRows={visibleRows} />}
        {view === 'intelligence' && <Intelligence dataset={dataset} analysis={analysis} questionResult={questionResult} busy={busy} onRun={runAnalysis} onAsk={runQuestion} onNavigate={navigate} />}
        {view === 'reports' && <Reports dataset={dataset} analysis={analysis} onNavigate={navigate} />}
        {view === 'history' && <History history={history} onNavigate={navigate} onOpen={async (id) => {
          setBusy(true); setError('');
          try {
            const saved = await getTask(id);
            if (saved.dataset_id) setDataset(await getDataset(saved.dataset_id) as Dataset);
            if (!saved.report || !saved.verification) throw new Error('استجابة التقرير غير مكتملة.');
            setAnalysis(saved as Analysis);
            setView('reports');
          }
          catch (reason) { setError(reason instanceof Error ? reason.message : 'تعذر فتح المهمة.'); }
          finally { setBusy(false); }
        }} />}
        {view === 'operations' && <Operations analysis={analysis} health={serviceHealth} onRefresh={() => void refreshWorkspace()} refreshing={refreshing} />}
        {view === 'settings' && <Settings health={serviceHealth} refreshing={refreshing} onRefresh={() => void refreshWorkspace()} />}
      </div>
    </main>
  </div>;
}

function PageIntro({ eyebrow, title, children, action }: { eyebrow: string; title: string; children: React.ReactNode; action?: React.ReactNode }) {
  return <div className="page-intro"><div><p className="eyebrow">{eyebrow}</p><h1>{title}</h1><p className="intro-copy">{children}</p></div>{action}</div>;
}

function LoadingState() {
  return <section className="loading-state" aria-live="polite">
    <span className="loading-spinner" aria-hidden="true" />
    <strong>جارٍ تجهيز مساحة العمل</strong>
    <p>نستعيد مجموعات البيانات وسجل المهام المحفوظ.</p>
  </section>;
}

function Overview({ dataset, analysis, onNavigate }: { dataset: Dataset | null; analysis: Analysis | null; onNavigate: (view: View) => void }) {
  if (!dataset) return <><PageIntro eyebrow="ذكاء القرار / نظرة عامة" title="اعرف ما يستحق انتباهك.">رؤية تشغيلية مركزة للفرق التي تريد مؤشرات يمكن تتبعها حتى مصدر البيانات.</PageIntro><EmptyWorkspace onNavigate={onNavigate} /></>;
  const kpis = dataset.kpis;
  return <><PageIntro eyebrow="ذكاء القرار / نظرة عامة" title="بيانات التشغيل الحالية." action={<button className="button primary" onClick={() => onNavigate('intelligence')}>شغّل التحليل <span>←</span></button>}>مجموعة البيانات المحفوظة جاهزة للمراجعة. ابدأ بالإشارة، ثم تتبع الدليل.</PageIntro>
    <div className="dataset-strip"><span className="dataset-status">● مجموعة نشطة</span><strong>{dataset.name}</strong><span>{dataset.rows.toLocaleString('ar-SA')} صفًا</span><span>محفوظة محليًا</span><button onClick={() => onNavigate('workspace')}>عرض مساحة البيانات ←</button></div>
    <section className="overview-grid">
      <div className="primary-card"><div className="card-heading"><div><p className="eyebrow">ملخص الأداء</p><h2>حركة الإيرادات</h2></div><span className="verified-label">✓ مصدر موثوق</span></div><div className="hero-number">{money(kpis.total_revenue)}<small>إجمالي الإيرادات</small></div><TrendChart points={kpis.daily_revenue ?? []} /></div>
      <div className="metric-stack"><Metric label="الهامش الإجمالي" value={money(kpis.gross_margin)} note={`${kpis.margin_rate ?? '—'}٪ نسبة الهامش`} tone="green" /><Metric label="تكلفة التشغيل" value={money(kpis.total_cost)} note="من الصفوف الصالحة" /><Metric label="جودة البيانات" value={dataset.warnings.length ? `${dataset.warnings.length} تنبيهات` : 'نظيفة'} note={`${dataset.anomalies.length} قيم شاذة في الإيرادات`} tone={dataset.warnings.length ? 'amber' : 'green'} /></div>
    </section>
    <section className="overview-bottom"><div className="panel"><div className="panel-heading"><div><p className="eyebrow">الخطوة التالية</p><h3>{analysis ? 'راجع التقرير الموثوق' : 'شغّل أول مراجعة ذكية'}</h3></div><span className="step-count">{analysis ? '04' : '03'} / 04</span></div><p className="panel-copy">{analysis ? analysis.report.summary : 'سيقارن سير التحليل المحلي الأداء، ويرصد القيم الشاذة، ويتحقق من الادعاءات، وينتج ملخصًا تنفيذيًا.'}</p><button className="text-button" onClick={() => onNavigate(analysis ? 'reports' : 'intelligence')}>{analysis ? 'افتح مركز التقارير' : 'إعداد التحليل'} <span>←</span></button></div><div className="panel quality-panel"><div className="panel-heading"><div><p className="eyebrow">جودة البيانات</p><h3>تحقق قبل القرار</h3></div><span className={`status-tag ${dataset.warnings.length ? 'warning' : 'success'}`}>{dataset.warnings.length ? 'تحتاج مراجعة' : 'موثقة'}</span></div>{dataset.warnings.length ? dataset.warnings.map((warning) => <p className="quality-alert" key={warning}>! {warning}</p>) : <p className="panel-copy">الحقول المطلوبة مكتملة والمقاييس الرقمية جاهزة للتحليل.</p>}<button className="text-button" onClick={() => onNavigate('workspace')}>فحص بيانات المصدر <span>←</span></button></div></section>
  </>;
}

function Metric({ label, value, note, tone }: { label: string; value: string; note: string; tone?: string }) { return <div className={`metric ${tone ?? ''}`}><span>{label}</span><strong>{value}</strong><small>{note}</small></div>; }

function Workspace({ dataset, availableDatasets, onSelectDataset, onDemoData, busy, dragging, setDragging, onDrop, onFile, fileRef, search, setSearch, page, setPage, filteredRows, visibleRows }: { dataset: Dataset | null; availableDatasets: Dataset[]; onSelectDataset: (datasetId: string) => void; onDemoData: () => void; busy: boolean; dragging: boolean; setDragging: (value: boolean) => void; onDrop: (event: DragEvent<HTMLDivElement>) => void; onFile: (event: React.ChangeEvent<HTMLInputElement>) => void; fileRef: React.RefObject<HTMLInputElement | null>; search: string; setSearch: (value: string) => void; page: number; setPage: (value: number) => void; filteredRows: Array<Record<string, string | number | null>>; visibleRows: Array<Record<string, string | number | null>> }) {
  return <><PageIntro eyebrow="مساحة البيانات / المصدر" title="رؤية واضحة لمصدر البيانات.">استورد بيانات التشغيل وافحص جودتها قبل أن تطلب منها تفسير الأداء.</PageIntro>
    <div className={`drop-zone ${dragging ? 'dragging' : ''}`} onDragOver={(event) => { event.preventDefault(); setDragging(true); }} onDragLeave={() => setDragging(false)} onDrop={onDrop}><div className="drop-icon">↑</div><div className="drop-copy"><h2>{busy ? 'جارٍ التحقق والتحليل…' : 'اسحب ملف CSV أو XLSX إلى هنا'}</h2><p>ملفات حتى 5 MB · 10,000 صف · لا يتغير الملف الأصلي</p></div><div className="upload-actions"><button className="button secondary" onClick={() => fileRef.current?.click()} disabled={busy}>{busy ? 'جارٍ التجهيز…' : 'اختر ملفًا'}</button><button className="button tertiary" onClick={() => void onDemoData()} disabled={busy}>{busy ? 'جارٍ التجهيز…' : 'جرّب بيانات نموذجية'}</button></div><input ref={fileRef} type="file" accept=".csv,.xlsx,text/csv,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet" onChange={onFile} disabled={busy} className="visually-hidden" /></div>
    {!dataset ? <div className="empty-panel"><span className="empty-mark small">▦</span><h2>لم يُحمّل مصدر بعد</h2><p>بعد الاستيراد سيظهر ملف البيانات ومعاينته هنا.</p></div> : <><div className="workspace-summary"><div><p className="eyebrow">المصدر الحالي</p><h2>{dataset.name}</h2><p>{dataset.rows.toLocaleString('ar-SA')} صف · {dataset.columns.length} أعمدة · {dataset.summary.date_range?.join(' — ')}</p>{dataset.duplicate_of && <p className="quality-alert">هذا الملف مطابق لمصدر محفوظ سابقًا؛ تم الاحتفاظ به كسجل مستقل.</p>}</div><div className="summary-numbers"><span><b>{dataset.quality.issue_count}</b> ملاحظات جودة</span><span><b>{dataset.quality.rows_affected}</b> صفوف متأثرة</span></div></div>{availableDatasets.length > 1 && <label className="dataset-select">اختيار مصدر محفوظ<select value={dataset.id} onChange={(event) => onSelectDataset(event.target.value)} aria-label="اختيار مجموعة البيانات">{availableDatasets.map((item) => <option value={item.id} key={item.id}>{item.name} · {item.rows.toLocaleString('ar-SA')} صف</option>)}</select></label>}<div className="workspace-grid"><div className="panel"><div className="panel-heading"><div><p className="eyebrow">ملف المصدر</p><h3>فهرس الأعمدة</h3></div><span className="status-tag success">الأصل محفوظ</span></div><div className="column-list">{dataset.columns.map((column) => <div key={column}><span className="type-badge">{dataset.summary.numeric_columns?.includes(column) ? '123' : column === 'date' ? '∕' : 'Aa'}</span><strong dir="auto">{column}</strong><small>{dataset.summary.numeric_columns?.includes(column) ? 'مقياس رقمي' : column === 'date' ? 'حقل تاريخ' : 'تصنيف'}</small></div>)}</div></div><div className="panel quality-center"><div className="panel-heading"><div><p className="eyebrow">مركز جودة البيانات</p><h3>{dataset.quality.has_blocking_issues ? 'تحتاج مراجعة قبل القرار' : dataset.quality.issue_count ? 'ملاحظات قابلة للمراجعة' : 'جاهزة للتحليل'}</h3></div><span className={`status-tag ${dataset.quality.has_blocking_issues ? 'warning' : dataset.quality.issue_count ? 'warning' : 'success'}`}>{dataset.quality.has_blocking_issues ? 'حواجز' : dataset.quality.issue_count ? 'مراجعة' : 'موثقة'}</span></div><div className="quality-meter"><span style={{ width: `${dataset.quality.has_blocking_issues ? 55 : dataset.quality.issue_count ? 82 : 100}%` }} /></div><div className="quality-issues">{dataset.quality.issues.length ? dataset.quality.issues.map((issue) => <div className={`quality-issue ${issue.severity}`} key={`${issue.type}-${issue.columns.join(',')}-${issue.count}`}><div><strong>{qualityLabels[issue.type] ?? issue.type}</strong><small>{qualitySeverityLabels[issue.severity]} · {issue.count.toLocaleString('ar-SA')} حالة</small></div><p>{issue.message}</p>{issue.columns.length > 0 && <span>الأعمدة: {issue.columns.join('، ')}</span>}{issue.rows.length > 0 && <span>الصفوف: {issue.rows.slice(0, 8).join('، ')}{issue.rows.length > 8 ? '…' : ''}</span>}</div>) : <p className="panel-copy">لم تُكتشف مشكلات جودة في الفحص الأولي.</p>}</div><p className="quality-note">المصدر الأصلي لم يتغير. لا تُطبّق أي معالجة تلقائية؛ راجع السجلات المتأثرة قبل أي تحويل مدعوم مستقبلًا.</p></div></div><div className="panel preview-panel"><div className="panel-heading"><div><p className="eyebrow">مستكشف المصدر</p><h3>معاينة الصفوف</h3></div><div className="table-tools"><label className="search-box"><span>⌕</span><input value={search} onChange={(event) => { setSearch(event.target.value); setPage(1); }} placeholder="ابحث في الصفوف" aria-label="البحث في الصفوف" /></label><span className="status-tag">{filteredRows.length} نتيجة</span></div></div><div className="table-wrap"><table><thead><tr>{dataset.columns.map((column) => <th key={column} dir="auto">{column}<small>{dataset.summary.numeric_columns?.includes(column) ? 'رقم' : column === 'date' ? 'تاريخ' : 'نص'}</small></th>)}</tr></thead><tbody>{visibleRows.map((row, index) => <tr key={`${index}-${String(row[dataset.columns[0]])}`}>{dataset.columns.map((column) => <td key={column} dir="auto">{row[column] == null ? <em>مفقود</em> : String(row[column])}</td>)}</tr>)}{!visibleRows.length && <tr><td colSpan={dataset.columns.length} className="table-empty">لا توجد صفوف مطابقة.</td></tr>}</tbody></table></div><div className="pagination"><span>عرض {visibleRows.length ? (page - 1) * 5 + 1 : 0}–{Math.min(page * 5, filteredRows.length)} من {filteredRows.length}</span><div><button onClick={() => setPage(Math.max(1, page - 1))} disabled={page === 1}>السابق</button><button onClick={() => setPage(Math.min(Math.max(1, Math.ceil(filteredRows.length / 5)), page + 1))} disabled={page >= Math.ceil(filteredRows.length / 5)}>التالي</button></div></div></div></>}
  </>;
}

function Intelligence({ dataset, analysis, questionResult, busy, onRun, onAsk, onNavigate }: { dataset: Dataset | null; analysis: Analysis | null; questionResult: QuestionResponse | null; busy: boolean; onRun: (prompt: string) => void; onAsk: (question: string) => void; onNavigate: (view: View) => void }) {
  const stages = ['المنسق', 'محلل الأعمال', 'محلل المخاطر', 'التحقق', 'التقرير التنفيذي'];
  const [question, setQuestion] = useState('');
  const [questionExportError, setQuestionExportError] = useState('');
  return <><PageIntro eyebrow="مساحة الذكاء / سير العمل" title="اسأل سؤالًا يمكن للبيانات الإجابة عنه.">ابدأ بسؤال أعمال، ثم شغّل التحليل الموثق. الإجابات الحتمية تعرض الحسابات والأدلة، ولا تنتقل بين مصادر البيانات بصمت.</PageIntro>{!dataset ? <div className="empty-panel"><span className="empty-mark small">✦</span><h2>اختر مجموعة بيانات أولًا</h2><p>يتاح التحليل بعد التحقق من صفوف المصدر.</p><button className="button primary" onClick={() => onNavigate('workspace')}>افتح مساحة البيانات ←</button></div> : <><div className="question-card panel"><label htmlFor="business-question">سؤال الأعمال</label><textarea id="business-question" value={question} onChange={(event) => setQuestion(event.target.value)} placeholder="مثل: ما التصنيف الأعلى إيرادًا؟ أو ما ملاحظات جودة البيانات؟" rows={3} /><div className="question-actions"><span>أمثلة: الإيرادات حسب التصنيف · تغير الإيرادات · جودة البيانات</span><button className="button secondary" onClick={() => onAsk(question)} disabled={busy || question.trim().length < 3}>{busy ? 'جارٍ التحليل…' : 'أجب من هذا المصدر'}</button></div></div>{questionResult && <div className={`question-result panel ${questionResult.status === 'unsupported' ? 'unsupported' : ''}`}><div className="panel-heading"><div><p className="eyebrow">نتيجة مرتبطة بالمصدر</p><h2>{questionResult.answer}</h2></div><span className={`status-tag ${questionResult.status === 'completed' ? 'success' : 'warning'}`}>{questionResult.status === 'completed' ? 'مكتملة' : 'غير مدعومة'}</span></div>{questionResult.calculations.length > 0 && <section><h3>الحساب</h3>{questionResult.calculations.map((item) => <p className="panel-copy" key={item}>{item}</p>)}</section>}<section><h3>الأدلة</h3>{questionResult.evidence.length ? questionResult.evidence.slice(0, 10).map((item) => <div className="evidence-row" key={`${item.field}-${item.row}-${item.explanation}`}><strong>{item.field}{item.row ? ` · الصف ${item.row}` : ''}</strong><span>{item.explanation} · {String(item.value ?? '—')}</span></div>) : <p className="panel-copy">لا توجد أدلة لأن هذا السؤال غير مدعوم.</p>}</section><div className="question-actions"><span>النتيجة محفوظة لهذا المصدر والسؤال.</span><button className="button secondary" onClick={() => { setQuestionExportError(''); void exportQuestion(questionResult.id).catch((reason) => setQuestionExportError(reason instanceof Error ? reason.message : 'تعذر تصدير النتيجة.')); }} disabled={busy}>تصدير النتيجة</button></div>{questionExportError && <p className="inline-error" role="alert">{questionExportError}</p>}<p className="limitation">{questionResult.limitations.join(' ')}</p></div>}<div className="run-card"><div><p className="eyebrow">تحليل شامل</p><h2>مراجعة الأداء والمخاطر</h2><p>تستخدم مؤشرات موثقة وتنبيهات جودة المصدر وطريقة القيم الشاذة 1.5×IQR.</p></div><button className="button primary" onClick={() => onRun(question.trim() || 'حلّل الأداء وجودة البيانات والمخاطر')} disabled={busy}>{busy ? 'جارٍ تشغيل التحليل…' : analysis ? 'شغّل مرة أخرى' : 'شغّل التحليل'} <span>←</span></button></div><div className="stage-list">{stages.map((stage, index) => { const execution = analysis?.executions[index]; return <div className={`stage ${execution?.status === 'completed' ? 'complete' : ''}`} key={stage}><span className="stage-number">{execution ? '✓' : `0${index + 1}`}</span><div><strong>{stage}</strong><p>{index === 0 ? 'يخطط للمراجعة المنضبطة.' : index === 1 ? 'يلخص الأداء المرصود.' : index === 2 ? 'يفحص القيم الشاذة وتنبيهات الجودة.' : index === 3 ? 'يطابق الادعاءات مع النتائج.' : 'يصوغ التقرير التنفيذي.'}</p></div><span className="stage-status">{execution ? (execution.status === 'completed' ? 'اكتمل' : 'فشل') : 'في الانتظار'}</span></div>; })}</div></>}</>;
}

function Reports({ dataset, analysis, onNavigate }: { dataset: Dataset | null; analysis: Analysis | null; onNavigate: (view: View) => void }) {
  if (!dataset || !analysis) return <><PageIntro eyebrow="مركز التقارير / الأدلة" title="تقرير يستحق الثقة.">تظهر التقارير بعد اكتمال المراجعة الذكية، مع ربط كل نتيجة بمؤشر أو إشارة من المصدر.</PageIntro><div className="empty-panel"><span className="empty-mark small">▤</span><h2>لا يوجد تقرير موثق بعد</h2><p>شغّل سير الذكاء المحلي لإنشاء تقرير قائم على الأدلة.</p><button className="button primary" onClick={() => onNavigate(dataset ? 'intelligence' : 'workspace')}>{dataset ? 'شغّل التحليل ←' : 'حمّل مجموعة بيانات ←'}</button></div></>;
  return <ReportDocument dataset={dataset} analysis={analysis} onNavigate={onNavigate} />;
}

function ReportDocument({ dataset, analysis, onNavigate }: { dataset: Dataset; analysis: Analysis; onNavigate: (view: View) => void }) {
  const [exportError, setExportError] = useState('');
  return <><PageIntro eyebrow="مركز التقارير / نتيجة موثقة" title={analysis.report.title === 'Management intelligence report' ? 'تقرير الذكاء الإداري' : analysis.report.title}><span className="verified-label">✓ تم اعتماد التحقق</span> · {analysis.simulated ? 'تحليل محلي حتمي' : 'تحليل مدعوم من Gemini'}</PageIntro><div className="report-actions"><button className="button secondary" onClick={() => { setExportError(''); void exportTask(analysis.id).catch((reason) => setExportError(reason instanceof Error ? reason.message : 'تعذر تصدير التقرير.')); }}>تنزيل تقرير HTML</button></div>{exportError && <div className="alert" role="alert"><span className="alert-icon">!</span><div><strong>فشل التصدير</strong><span>{exportError}</span></div></div>}<div className="report-layout"><article className="report-document"><div className="report-kicker">الملخص التنفيذي</div><h2>{analysis.report.summary}</h2>{analysis.report.ai_insight && <section><div className="section-title"><span>AI</span><h3>رؤية Gemini</h3></div><p className="panel-copy">{analysis.report.ai_insight}</p></section>}<div className="report-metrics"><div><span>الإيرادات</span><b>{money(dataset.kpis.total_revenue)}</b></div><div><span>نسبة الهامش</span><b>{dataset.kpis.margin_rate}٪</b></div><div><span>صفوف المصدر</span><b>{dataset.rows.toLocaleString('ar-SA')}</b></div></div><section><div className="section-title"><span>01</span><h3>النتائج المرصودة</h3></div>{analysis.report.findings.map((finding) => <div className="evidence-row" key={finding.text}><strong>{finding.text}</strong><span>الدليل · {finding.evidence.join('، ')}</span></div>)}</section><section><div className="section-title"><span>02</span><h3>التوصيات</h3></div>{(analysis.report.recommendations ?? []).map((item) => <p className="recommendation" key={item}>← {item}</p>)}</section><section><div className="section-title"><span>03</span><h3>الحدود</h3></div>{analysis.report.limitations.map((item) => <p className="limitation" key={item}>{item}</p>)}</section></article><aside className="report-aside"><div className="panel"><p className="eyebrow">سجل التحقق</p><div className="approval"><span>✓</span><div><strong>معتمد</strong><small>الادعاءات مطابقة للنتائج</small></div></div><div className="aside-line"><span>مجموعة البيانات</span><b dir="auto">{dataset.name}</b></div><div className="aside-line"><span>المنهج</span><b dir="ltr">1.5× IQR</b></div><div className="aside-line"><span>التنفيذ</span><b>{analysis.simulated ? 'محلي حتمي' : 'Google Gemini'}</b></div></div><div className="panel"><p className="eyebrow">هل تريد عرضًا مختلفًا؟</p><p className="panel-copy">عد إلى مساحة الذكاء لإعادة المراجعة بعد رفع مصدر محدث.</p><button className="text-button" onClick={() => onNavigate('intelligence')}>افتح سير العمل ←</button></div></aside></div></>;
}

function History({ history, onNavigate, onOpen }: { history: TaskSummary[]; onNavigate: (view: View) => void; onOpen: (id: string) => void }) {
  return <><PageIntro eyebrow="النظام / سجل المهام" title="سجل القرارات المنفذة.">تبقى عمليات التحليل المكتملة قابلة للبحث مع مرجع مصدر البيانات وحالة التحقق.</PageIntro>{!history.length ? <div className="empty-panel"><span className="empty-mark small">◷</span><h2>لا توجد مهام مكتملة</h2><p>شغّل مراجعة ذكية ليظهر سجل التنفيذ هنا.</p><button className="button primary" onClick={() => onNavigate('intelligence')}>افتح الذكاء ←</button></div> : <div className="history-list">{history.map((item) => <button className="history-row" key={item.id} onClick={() => onOpen(item.id)}><div className="history-icon">✓</div><div><strong>{item.report?.title ?? 'مراجعة ذكية'}</strong><p>{item.report?.summary ?? item.prompt ?? 'لا يتوفر ملخص'}</p><small>{item.simulated ? 'تحليل محلي حتمي' : 'تحليل مدعوم بنموذج'} · {item.dataset_id ?? 'مصدر غير معروف'}</small></div><span className="status-tag success">{item.status === 'completed' ? 'مكتملة · فتح التقرير' : item.status}</span></button>)}</div>}</>;
}

function Operations({ analysis, health: service, onRefresh, refreshing }: { analysis: Analysis | null; health: HealthResponse | null; onRefresh: () => void; refreshing: boolean }) { return <><PageIntro eyebrow="النظام / تشغيل الوكلاء" title="اعرف ما الذي يعمل الآن." action={<button className="button secondary" onClick={onRefresh} disabled={refreshing}>{refreshing ? 'جارٍ الفحص…' : 'تحديث الحالة ↻'}</button>}>شفافية تشغيلية لسير الذكاء المحلي. تُقرأ حالة الخدمة من الخادم بدل افتراض أنها متاحة.</PageIntro><div className="ops-grid"><div className="panel provider-card"><div className="panel-heading"><div><p className="eyebrow">حالة المزود</p><h3>محرك التحليل الحتمي</h3></div><span className={`status-tag ${service?.status === 'ok' ? 'success' : 'warning'}`}>{service?.status === 'ok' ? 'يستجيب' : 'غير مؤكد'}</span></div><p className="panel-copy">{service?.status === 'ok' ? 'الخادم يستجيب لطلب الفحص. التحليل الحسابي متاح حسب عقد الخدمة.' : 'لم يتم تأكيد اتصال حديث بالخادم. استخدم تحديث الحالة قبل بدء العرض.'}</p><div className="provider-meta"><span>الرؤى اللغوية <b>{service?.providers.gemini_configured ? 'Gemini مهيأ' : 'غير مهيأة'}</b></span><span>الإصدار <b>{service?.version ?? '—'}</b></span></div></div><div className="panel"><div className="panel-heading"><div><p className="eyebrow">آخر تنفيذ</p><h3>{analysis ? 'اكتملت المراجعة' : 'لم يُنفذ تحليل بعد'}</h3></div>{analysis && <span className="status-tag success">مكتمل</span>}</div>{analysis ? <><div className="execution-mini">{analysis.executions.map((execution) => <div key={execution.agent}><span>✓</span><b>{execution.agent}</b><small>{execution.status === 'completed' ? 'اكتمل' : 'فشل'}</small></div>)}</div><div className="tool-trace"><p className="eyebrow">أدوات التحليل الفعلية · {analysis.tool_calls?.length ?? 0}</p>{(analysis.tool_calls ?? []).map((call) => <details key={call.tool} className="tool-trace-item"><summary><span className={call.ok ? 'tool-dot success' : 'tool-dot warning'} /> <strong dir="ltr">{call.tool}</strong><small>{call.ok ? 'نجاح' : 'تعذر التنفيذ'} · {call.duration_ms.toFixed(2)} ms</small></summary><p>{call.summary}</p><pre>{JSON.stringify(call.data, null, 2)}</pre></details>)}<p className="limitation">الأدوات للقراءة فقط؛ نتائجها مشتقة من بيانات المصدر ولا تنفذ أوامر نظام أو تغييرات على الملفات.</p></div></> : <p className="panel-copy">شغّل تحليلًا لرؤية المراحل والأدوات التي نُفذت فعليًا.</p>}</div></div></>; }
function Settings({ health: service, refreshing, onRefresh }: { health: HealthResponse | null; refreshing: boolean; onRefresh: () => void }) {
  return <><PageIntro eyebrow="النظام / الإعدادات" title="إعدادات واضحة وحدود مفهومة." action={<button className="button secondary" onClick={onRefresh} disabled={refreshing}>{refreshing ? 'جارٍ الفحص…' : 'اختبر الاتصال ↻'}</button>}>تُقرأ حالة الخدمة من نقطة فحص الخادم. لا تُعرض مفاتيح API أو الأسرار في المتصفح.</PageIntro><div className="settings-list"><div className="setting-row"><div><p className="eyebrow">صحة الخدمة</p><h3>{service?.status === 'ok' ? 'الخادم يستجيب' : 'لم يتم تأكيد الاتصال'}</h3><p>{service ? `الإصدار ${service.version} · ${service.service}` : 'اضغط على اختبار الاتصال للحصول على حالة حديثة من الخادم.'}</p></div><span className={`status-tag ${service?.status === 'ok' ? 'success' : 'warning'}`}>{service?.status === 'ok' ? 'متصل' : 'غير معروف'}</span></div><div className="setting-row"><div><p className="eyebrow">وضع التطبيق</p><h3>التحليل المحلي الموثوق</h3><p>الحسابات والمؤشرات مشتقة من البيانات المحفوظة. وضع التشغيل: {service?.mode ?? 'بانتظار الفحص'}.</p></div><span className={`status-tag ${service?.capabilities.deterministic_analysis ? 'success' : 'warning'}`}>{service?.capabilities.deterministic_analysis ? 'متاح' : 'غير مؤكد'}</span></div><div className="setting-row"><div><p className="eyebrow">Google Gemini</p><h3>مزود لغوي اختياري</h3><p>{service?.providers.gemini_configured ? 'تم إعداد المزود على الخادم؛ لا يُكشف المفتاح للواجهة.' : 'لم يُكتشف مفتاح مزود على الخادم؛ سيعمل التحليل الحسابي دون رؤى توليدية.'}</p></div><span className={`status-tag ${service?.providers.gemini_configured ? 'success' : ''}`}>{service?.providers.gemini_configured ? 'مهيأ' : 'اختياري'}</span></div><div className="setting-row"><div><p className="eyebrow">قدرات النظام</p><h3>الرفع والتحليل والتصدير</h3><p>تُعرض الإمكانات التي أعلن عنها الخادم في آخر فحص صحي.</p></div><div className="capability-list">{([['رفع الملفات', service?.capabilities.file_upload], ['التحليل الحتمي', service?.capabilities.deterministic_analysis], ['تصدير التقارير', service?.capabilities.report_export]] as Array<[string, boolean | undefined]>).map(([label, enabled]) => <span key={String(label)} className={enabled ? 'capability-on' : 'capability-off'}>{enabled ? '✓' : '—'} {label}</span>)}</div></div></div></>;
}
