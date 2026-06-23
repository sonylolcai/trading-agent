import { describe, expect, it } from 'vitest';
import { parseAnalysisEvent, shouldFinalizeAnalysisStream } from '../features/analysis/analysis-event-stream';

describe('parseAnalysisEvent', () => {
  it('parses an SSE message event with JSON analysis payload', () => {
    expect(
      parseAnalysisEvent('event: message\ndata: {"type":"content_delta","stage":"stage1","text":"abc"}\n\n'),
    ).toEqual({ type: 'content_delta', stage: 'stage1', text: 'abc' });
  });

  it('ignores blank chunks', () => {
    expect(parseAnalysisEvent('\n\n')).toBeNull();
  });

  it('returns null for malformed JSON payloads', () => {
    expect(parseAnalysisEvent('event: message\ndata: {"type":\n\n')).toBeNull();
  });

  it('keeps the stream open for stage error events until task_finished', () => {
    expect(shouldFinalizeAnalysisStream({ type: 'error', stage: 'stage2', message: 'validation failed' })).toBe(false);
    expect(shouldFinalizeAnalysisStream({ type: 'task_finished', status: 'failed' })).toBe(true);
  });
});
