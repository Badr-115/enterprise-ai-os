import { afterEach, describe, expect, it, vi } from 'vitest';
import { askQuestion, createDemoDataset, health, task, upload } from './api';

describe('upload API client', () => {
  afterEach(() => vi.restoreAllMocks());

  it('sends multipart data through the same-origin proxy and returns the dataset', async () => {
    const response = { id: 'dataset-1', rows: 3 };
    const fetchMock = vi.spyOn(globalThis, 'fetch').mockResolvedValue(
      new Response(JSON.stringify(response), {
        status: 200,
        headers: { 'Content-Type': 'application/json' },
      }),
    );
    const file = new File(['date,revenue,cost,units\n2026-01-01,100,60,4'], 'sample.csv', {
      type: 'text/csv',
    });

    await expect(upload(file)).resolves.toEqual(response);

    expect(fetchMock).toHaveBeenCalledWith('/api/datasets/upload', {
      method: 'POST',
      body: expect.any(FormData),
    });
    const request = fetchMock.mock.calls[0][1];
    expect(request?.headers).toBeUndefined();
    expect((request?.body as FormData).get('file')).toBe(file);
  });

  it('reports an unavailable API as a retryable error', async () => {
    vi.spyOn(globalThis, 'fetch').mockRejectedValue(new TypeError('fetch failed'));

    await expect(
      upload(new File(['date,revenue,cost,units'], 'sample.csv', { type: 'text/csv' })),
    ).rejects.toThrow('الخدمة غير متاحة. تأكد من تشغيل الخادم ثم حاول مرة أخرى.');
  });

  it('does not describe a proxy/server failure as an upload validation failure', async () => {
    vi.spyOn(globalThis, 'fetch').mockResolvedValue(
      new Response('Internal Server Error', { status: 500 }),
    );

    await expect(
      upload(new File(['date,revenue,cost,units'], 'sample.csv', { type: 'text/csv' })),
    ).rejects.toThrow('الخدمة غير متاحة حاليًا. تأكد من تشغيل خادم التحليل ثم حاول مرة أخرى.');
  });

  it('sends a business question for the selected dataset', async () => {
    const fetchMock = vi.spyOn(globalThis, 'fetch').mockResolvedValue(
      new Response(JSON.stringify({ status: 'completed', dataset_id: 'dataset-1', answer: 'إجابة' }), { status: 200 }),
    );
    await expect(askQuestion('dataset-1', 'ما جودة البيانات؟')).resolves.toMatchObject({ dataset_id: 'dataset-1' });
    expect(fetchMock).toHaveBeenCalledWith('/api/questions', expect.objectContaining({
      method: 'POST',
      body: JSON.stringify({ dataset_id: 'dataset-1', question: 'ما جودة البيانات؟' }),
    }));
  });

  it('passes the requested analysis prompt to the backend', async () => {
    const fetchMock = vi.spyOn(globalThis, 'fetch').mockResolvedValue(
      new Response(JSON.stringify({ id: 'task-1', status: 'completed' }), { status: 200 }),
    );
    await task('dataset-1', 'attempt-2', 'Review risks and compare revenue by region');
    expect(fetchMock).toHaveBeenCalledWith('/api/tasks', expect.objectContaining({
      body: JSON.stringify({ dataset_id: 'dataset-1', prompt: 'Review risks and compare revenue by region' }),
    }));
  });

  it('localizes the standard API error envelope and preserves idempotency', async () => {
    const fetchMock = vi.spyOn(globalThis, 'fetch').mockResolvedValue(
      new Response(JSON.stringify({
        code: 'request_failed',
        message: 'Dataset not found',
        request_id: 'request-1',
      }), { status: 404, headers: { 'Content-Type': 'application/json' } }),
    );

    await expect(task('missing-dataset', 'attempt-1')).rejects.toThrow('مجموعة البيانات غير موجودة.');
    expect(fetchMock).toHaveBeenCalledWith('/api/tasks', expect.objectContaining({
      headers: expect.objectContaining({ 'Idempotency-Key': 'attempt-1' }),
    }));
  });
});


describe('service health API', () => {
  afterEach(() => vi.restoreAllMocks());

  it('returns actual backend capabilities and provider configuration', async () => {
    const payload = {
      status: 'ok', service: 'enterprise-intelligence-os', version: '0.2.0', mode: 'local-demo',
      providers: { gemini_configured: false },
      capabilities: { file_upload: true, deterministic_analysis: true, report_export: true },
    };
    const fetchMock = vi.spyOn(globalThis, 'fetch').mockResolvedValue(
      new Response(JSON.stringify(payload), { status: 200, headers: { 'Content-Type': 'application/json' } }),
    );
    await expect(health()).resolves.toEqual(payload);
    expect(fetchMock).toHaveBeenCalledWith('/api/health', { cache: 'no-store' });
  });
});


describe('demo dataset API', () => {
  afterEach(() => vi.restoreAllMocks());

  it('creates the built-in sample without accepting a client filesystem path', async () => {
    const sample = { id: 'demo-1', name: 'demo-sales.csv', rows: 25 };
    const fetchMock = vi.spyOn(globalThis, 'fetch').mockResolvedValue(
      new Response(JSON.stringify(sample), { status: 200, headers: { 'Content-Type': 'application/json' } }),
    );
    await expect(createDemoDataset()).resolves.toMatchObject(sample);
    expect(fetchMock).toHaveBeenCalledWith('/api/datasets/demo', { method: 'POST' });
  });
});
